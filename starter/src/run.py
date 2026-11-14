"""Run the three ingestion strategies against one corpus and benchmark."""
import json
import os
import platform
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_pdf, normalize_text
from .store import ChromaStore

HERE = Path(__file__).resolve().parents[1]


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    """Run retrieval and write actual metrics/traces; never substitutes fake outputs."""
    try:
        from dotenv import load_dotenv
        load_dotenv(HERE / ".env")
    except ImportError:
        pass
    manifest_path = Path(os.environ.get("DAY6_MANIFEST", HERE / "data/manifest.json"))
    questions_path = Path(os.environ.get("DAY6_QUESTIONS", HERE / "benchmark/questions.jsonl"))
    manifest = _read_json(manifest_path)
    questions = [json.loads(line) for line in questions_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(questions) < 20 or sum(q.get("split") == "dev" for q in questions) < 15 or sum(q.get("split") == "test" for q in questions) < 5:
        raise ValueError("Benchmark needs at least 20 questions, including 15 dev and 5 test")
    if sum(bool(q.get("filter")) for q in questions) < 3:
        raise ValueError("At least three questions must exercise a metadata filter")
    if not any(q.get("filter") for q in questions if q.get("split") == "test"):
        raise ValueError("At least one test question must exercise a metadata filter")
    split_filter = os.environ.get("DAY6_EVAL_SPLIT")
    if split_filter not in (None, "dev", "test"):
        raise ValueError("DAY6_EVAL_SPLIT must be 'dev', 'test', or unset")
    evaluation_questions = [q for q in questions if split_filter is None or q["split"] == split_filter]

    pages = []
    errors = []
    eligible = 0
    for doc in manifest["documents"]:
        pdf_path = (HERE / doc["path"]).resolve()
        if not pdf_path.is_file():
            errors.append({"source": doc.get("source", doc["path"]), "error": "file not found", "path": str(pdf_path)})
            continue
        if doc.get("format") == "text":
            from .models import DocumentPage
            extracted = [DocumentPage(doc["document_id"], doc.get("source", doc["path"]),
                                      int(doc["content_pages"][0]),
                                      normalize_text(pdf_path.read_text(encoding="utf-8")), {})]
        else:
            extracted = load_pdf(pdf_path, doc["document_id"], doc.get("source", doc["path"]))
        content_pages = set(doc.get("content_pages", []))
        for page in extracted:
            page.metadata.update(doc.get("metadata", {}))
            pages.append(page)
            if page.page in content_pages and len(page.text) >= 80:
                eligible += 1
            if not page.text:
                errors.append({"source": page.source, "page": page.page, "error": "no extractable text"})
    if eligible < 30:
        raise ValueError(f"Manifest identifies only {eligible} readable content pages; at least 30 are required")
    # Always write the log so an empty list records that the ingestion pass found no errors.
    _write_json(HERE / "results/ingestion_errors.json", errors)

    model_name = os.environ.get("DAY6_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    model_started = perf_counter()
    embedder = MyEmbedder(model_name)
    model_load_seconds = perf_counter() - model_started
    vector_path = os.environ.get("DAY6_VECTOR_DIR", str(HERE / "data/chroma"))
    store = ChromaStore(vector_path, embedder.dimensions)
    store.create_schema()
    all_traces = []
    resource_rows = []
    configurations = {
        "A": lambda page: fixed_size(page, size=500, overlap=50),
        "B": lambda page: by_paragraph(page, max_size=700),
        "C": lambda page: by_paragraph(page, max_size=700),
    }
    paragraph_chunks = None
    for strategy, chunk_fn in configurations.items():
        started = perf_counter()
        if strategy == "C":
            chunks = paragraph_chunks
        else:
            chunks = [chunk for page in pages for chunk in chunk_fn(page)]
        chunk_lengths = sorted(len(chunk.text) for chunk in chunks)

        def percentile(p: float) -> int:
            if not chunk_lengths:
                return 0
            return chunk_lengths[round((len(chunk_lengths) - 1) * p)]

        if strategy != "C":
            vectors = embedder.embed_documents([chunk.text for chunk in chunks])
            store.upsert(strategy, chunks, vectors)
            ingest_seconds = perf_counter() - started
            if strategy == "B":
                paragraph_chunks = chunks
        else:
            ingest_seconds = 0.0
        resource_rows.append({"strategy": strategy, "chunk_count": len(chunks),
                              "total_chunk_chars": sum(len(c.text) for c in chunks),
                              "mean_chunk_chars": round(sum(len(c.text) for c in chunks)/max(len(chunks), 1), 2),
                              "chunk_length_distribution_chars": {
                                  "min": chunk_lengths[0] if chunk_lengths else 0,
                                  "p25": percentile(0.25),
                                  "median": percentile(0.50),
                                  "p75": percentile(0.75),
                                  "max": chunk_lengths[-1] if chunk_lengths else 0,
                              },
                              "ingest_seconds_including_embeddings": round(ingest_seconds, 3), "api_cost": 0,
                              "embedding_model": model_name, "dimensions": embedder.dimensions,
                              "model_load_seconds_this_run": round(model_load_seconds, 3),
                              "embedding_library_version": version("sentence-transformers"),
                              "torch_version": version("torch"), "vector_store_version": version("chromadb"),
                              "python_version": platform.python_version()})
        resource_rows[-1]["retrieval_candidates"] = 50
        resource_rows[-1]["hnsw_ef_search"] = 300
        resource_rows[-1]["reranker"] = "BM25 + cosine similarity (lexical weight 0.30)"
        if strategy == "C":
            resource_rows[-1]["index_reused_from"] = "B"
        retrieval_started = perf_counter()
        for question in evaluation_questions:
            filters = question.get("filter", {}) if strategy == "C" else {}
            hits = store.search(strategy, embedder.embed_query(question["question"]), top_k=3,
                                query_text=question["question"], filters=filters)
            trace = evaluate_query(question, hits)
            trace.update({"strategy": strategy, "question": question["question"], "filter_applied": filters})
            all_traces.append(trace)
        resource_rows[-1]["query_and_search_seconds"] = round(perf_counter() - retrieval_started, 3)

    _write_json(HERE / "results/traces.json", all_traces)
    _write_json(HERE / "results/retrieval_metrics.json", summarize(all_traces))
    _write_json(HERE / "results/resource_metrics.json", resource_rows)
    print(f"Wrote {len(all_traces)} retrieval traces for {len(evaluation_questions)} evaluated questions to results/.")
    print("Manual coherence, metadata correctness and grounding labels are intentionally not fabricated; record them in results/manual_audit.csv.")


if __name__ == "__main__":
    main()
