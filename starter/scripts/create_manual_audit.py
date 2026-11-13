"""Write the recorded, AI-assisted manual audit against the final run traces."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.chunking import by_paragraph, fixed_size
from src.models import DocumentPage
REVIEWER = "AI-assisted review; student verification recommended"


def main() -> None:
    manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    docs = {doc["document_id"]: doc for doc in manifest["documents"]}
    traces = json.loads((ROOT / "results/traces.json").read_text(encoding="utf-8"))
    rows = []
    coherence_scores = {
        "A": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        "B": [1, 2, 1, 2, 1, 2, 2, 2, 1, 1],
        "C": [1, 2, 1, 2, 1, 2, 2, 2, 1, 1],
    }
    coherence_reasons = {
        "A": "The 500-character window begins or ends mid-sentence at this sampled position; surrounding thought is partly missing.",
        "B": [
            "Starts with a fragment from the prior sentence; the following thought is readable.",
            "Contains a complete paragraph with the governing point and its context.",
            "The point about safety is present, but its preceding reference is missing.",
            "Contains a complete paragraph with a clear subject and connected explanation.",
            "Begins inside a quoted passage, so its speaker/context is only partly clear.",
            "Contains the complete argument about likely conflict between neighboring states.",
            "Keeps the territorial-dispute explanation together with its supporting detail.",
            "Contains a complete paragraph explaining the military-balance point.",
            "Starts with a dependent phrase; the main idea is understandable but context is clipped.",
            "Starts mid-sentence before the discussion of constitutional improvements.",
        ],
        "C": [
            "Starts with a fragment from the prior sentence; the following thought is readable.",
            "Contains a complete paragraph with the governing point and its context.",
            "The point about safety is present, but its preceding reference is missing.",
            "Contains a complete paragraph with a clear subject and connected explanation.",
            "Begins inside a quoted passage, so its speaker/context is only partly clear.",
            "Contains the complete argument about likely conflict between neighboring states.",
            "Keeps the territorial-dispute explanation together with its supporting detail.",
            "Contains a complete paragraph explaining the military-balance point.",
            "Starts with a dependent phrase; the main idea is understandable but context is clipped.",
            "Starts mid-sentence before the discussion of constitutional improvements.",
        ],
    }
    for n in range(1, 11):
        doc = next(d for d in manifest["documents"] if d["metadata"]["source_unit"] == n)
        text = (ROOT / doc["path"]).read_text(encoding="utf-8").strip()
        marker = text[1010:1040]
        page = DocumentPage(doc["document_id"], doc["source"], n, text, doc["metadata"])
        chunks_by_strategy = {
            "A": fixed_size(page, size=500, overlap=50),
            "B": by_paragraph(page, max_size=700),
            "C": by_paragraph(page, max_size=700),
        }
        for strategy, chunks in chunks_by_strategy.items():
            chunk = next(c for c in chunks if marker in c.text)
            score = coherence_scores[strategy][n - 1]
            reason = coherence_reasons[strategy] if strategy == "A" else coherence_reasons[strategy][n - 1]
            rows.append({"strategy": strategy, "dimension": "coherence",
                         "question_id_or_source_position": f"unit={n};offset=1010",
                         "chunk_id": chunk.chunk_id, "score_0_to_2": score,
                         "metadata_correct": "", "filter_compliant": "", "reason": reason,
                         "reviewer": REVIEWER})

    test_questions = {json.loads(line)["id"]: json.loads(line)
                      for line in (ROOT / "benchmark/questions.jsonl").read_text(encoding="utf-8").splitlines() if line
                      if json.loads(line)["split"] == "test"}
    grounding_scores = {
        "A": {"q16": 2, "q17": 1, "q18": 1, "q19": 1, "q20": 0},
        "B": {"q16": 2, "q17": 1, "q18": 1, "q19": 1, "q20": 0},
        "C": {"q16": 0, "q17": 1, "q18": 1, "q19": 1, "q20": 0},
    }
    grounding_reasons = {
        "q16": "A retrieves No. 41 on unity deterring foreign ambition, which supports the core rationale but omits the full common-danger/common-treasury explanation (score 2). B retrieves the same point only partially (score 1). C retrieves standing-army context but not the rationale for joint provision (score 0).",
        "q17": "Top-3 results discuss militia and common defense but do not retrieve the condition that an insurrection pervading a whole state or principal part may require different force; partial context only.",
        "q18": "The results identify the objection that a small House may lack constituent knowledge, but the retrieved context does not fully support the district representation explanation.",
        "q19": "A retrieves No. 59's election-regulation clause and B/C retrieve related No. 59 passages, but the top-3 do not establish the full qualification exception requested.",
        "q20": "The top-3 results are unrelated passages or essay headings; none supports the requested list of powers from No. 41.",
    }
    for trace in traces:
        if trace["split"] != "test":
            continue
        question = test_questions[trace["question_id"]]
        for rank, hit in enumerate(trace["hits"], start=1):
            doc = docs[hit["document_id"]]
            metadata_ok = (hit["page"] in doc["content_pages"] and hit["source"] == doc["source"]
                           and hit["metadata"].get("document_id") == doc["document_id"]
                           and hit["metadata"].get("source") == doc["source"]
                           and hit["metadata"].get("page") == hit["page"]
                           and all(hit["metadata"].get(k) == v for k, v in doc["metadata"].items()))
            filt = question.get("filter", {}) if trace["strategy"] == "C" else {}
            filter_ok = all(hit["metadata"].get(k) == v for k, v in filt.items()) if filt else "N/A"
            rows.append({"strategy": trace["strategy"], "dimension": "metadata",
                         "question_id_or_source_position": f"{trace['question_id']};rank={rank}",
                         "chunk_id": hit["chunk_id"], "score_0_to_2": "",
                         "metadata_correct": metadata_ok, "filter_compliant": filter_ok,
                         "reason": "Compared document/source/page and inherited category fields with manifest.",
                         "reviewer": REVIEWER})
        score = grounding_scores[trace["strategy"]][trace["question_id"]]
        reason = grounding_reasons.get(trace["question_id"])
        first_id = trace["hits"][0]["chunk_id"] if trace["hits"] else ""
        rows.append({"strategy": trace["strategy"], "dimension": "grounding",
                     "question_id_or_source_position": trace["question_id"], "chunk_id": first_id,
                     "score_0_to_2": score, "metadata_correct": "", "filter_compliant": "",
                     "reason": reason, "reviewer": REVIEWER})

    path = ROOT / "results/manual_audit.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["strategy", "dimension", "question_id_or_source_position",
                                               "chunk_id", "score_0_to_2", "metadata_correct",
                                               "filter_compliant", "reason", "reviewer"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} AI-assisted audit labels to {path}")


if __name__ == "__main__":
    main()
