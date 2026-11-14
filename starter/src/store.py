"""Persistent PostgreSQL/pgvector storage with exact cosine ranking."""
import json
import math
import re
from collections import Counter
from typing import Any
from .models import Chunk


_STOP_WORDS = set("""the a an in on of to for from is are was were be do does did how what why which who when under according about across into with their its and or but that this these those than then as by at it can could would should may might must each all any one two""".split())


def _lexical_tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z]+|\d+", text.lower())
            if token not in _STOP_WORDS]


def _hybrid_rerank(query: str, hits: list[dict[str, Any]], weight: float = 0.3) -> list[dict[str, Any]]:
    """Rerank dense candidates with a small BM25 lexical signal; parameters are dev-tuned."""
    if not hits:
        return []
    query_terms = set(_lexical_tokens(query))
    token_lists = [_lexical_tokens(hit["text"]) for hit in hits]
    document_frequency = Counter(term for tokens in token_lists for term in set(tokens))
    count = len(hits)
    average_length = sum(map(len, token_lists)) / count or 1.0
    k1, b = 1.2, 0.75
    lexical = []
    for tokens in token_lists:
        frequencies = Counter(tokens)
        score = 0.0
        for term in query_terms:
            frequency = frequencies[term]
            if not frequency:
                continue
            df = document_frequency[term]
            inverse_frequency = math.log(1 + (count - df + 0.5) / (df + 0.5))
            score += inverse_frequency * frequency * (k1 + 1) / (
                frequency + k1 * (1 - b + b * len(tokens) / average_length)
            )
        lexical.append(score)

    def scale(values: list[float]) -> list[float]:
        low, high = min(values), max(values)
        span = high - low
        return [(value - low) / span if span else 0.0 for value in values]

    dense_scaled = scale([float(hit["score"]) for hit in hits])
    lexical_scaled = scale(lexical)
    for hit, dense, sparse in zip(hits, dense_scaled, lexical_scaled):
        hit["dense_score"] = hit["score"]
        hit["bm25_score"] = sparse
        hit["score"] = (1 - weight) * dense + weight * sparse
    return sorted(hits, key=lambda hit: hit["score"], reverse=True)


class ChromaStore:
    """Persistent local Chroma collections with cosine HNSW and payload filters."""

    def __init__(self, path: str, dimensions: int) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError("Install chromadb; see starter/requirements.txt") from exc
        self._client = chromadb.PersistentClient(path=path)
        self._collections = {}
        self.dimensions = dimensions

    def _collection(self, strategy: str):
        storage_strategy = "B" if strategy == "C" else strategy
        if storage_strategy not in self._collections:
            safe_name = f"day6_{storage_strategy.lower()}"
            self._collections[storage_strategy] = self._client.get_or_create_collection(
                name=safe_name, metadata={"hnsw:space": "cosine"},
                configuration={"hnsw": {"space": "cosine", "ef_search": 300}},
            )
        return self._collections[storage_strategy]

    def create_schema(self) -> None:
        """Create persistent, cosine-distance collections for the strategies."""
        for strategy in ("A", "B"):
            self._collection(strategy)

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Replace one collection's contents to remove obsolete chunks on rerun."""
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors lengths differ")
        if any(len(vector) != self.dimensions for vector in vectors):
            raise ValueError("embedding dimension mismatch")
        collection = self._collection(strategy)
        current = collection.get(include=["metadatas"]).get("ids", [])
        if current:
            collection.delete(ids=current)
        for start in range(0, len(chunks), 500):
            batch = chunks[start:start + 500]
            batch_vectors = vectors[start:start + 500]
            collection.upsert(
                ids=[chunk.chunk_id for chunk in batch],
                embeddings=batch_vectors,
                documents=[chunk.text for chunk in batch],
                metadatas=[{**chunk.metadata, "document_id": chunk.document_id,
                            "source": chunk.source, "page": chunk.page} for chunk in batch],
            )

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               query_text: str = "",
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Run cosine HNSW search, applying any payload filter before retrieval."""
        if top_k <= 0 or len(query_vector) != self.dimensions:
            raise ValueError("Invalid top_k or query vector dimension")
        candidate_k = min(50, self._collection(strategy).count())
        query = {"query_embeddings": [query_vector], "n_results": max(top_k, candidate_k),
                 "include": ["documents", "metadatas", "distances"]}
        if filters:
            query["where"] = filters
        result = self._collection(strategy).query(**query)
        hits = []
        for i, chunk_id in enumerate(result["ids"][0]):
            metadata = result["metadatas"][0][i]
            hits.append({"chunk_id": chunk_id, "document_id": metadata["document_id"],
                         "source": metadata["source"], "page": metadata["page"],
                         "text": result["documents"][0][i], "metadata": metadata,
                         "score": 1.0 - float(result["distances"][0][i])})
        if query_text:
            hits = _hybrid_rerank(query_text, hits)
        return hits[:top_k]


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.database_url = database_url
        self.dimensions = dimensions

    def _connect(self):
        try:
            import psycopg
            from pgvector.psycopg import register_vector
        except ImportError as exc:
            raise RuntimeError("Install psycopg[binary] and pgvector; see starter/requirements.txt") from exc
        conn = psycopg.connect(self.database_url)
        register_vector(conn)
        return conn

    def create_schema(self) -> None:
        """Create extension and table; vector dimension is model-specific."""
        with self._connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS day6_chunks (
                strategy TEXT NOT NULL, chunk_id TEXT NOT NULL, document_id TEXT NOT NULL,
                source TEXT NOT NULL, page INTEGER NOT NULL, text TEXT NOT NULL,
                metadata JSONB NOT NULL, embedding vector({self.dimensions}) NOT NULL,
                PRIMARY KEY (strategy, chunk_id))""")
            conn.execute("CREATE INDEX IF NOT EXISTS day6_chunks_metadata_idx ON day6_chunks USING GIN (metadata)")

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Replace one strategy atomically so reruns cannot leave stale chunks.

        When re-ingesting changed source documents, remove obsolete chunks too.
        """
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors lengths differ")
        if any(len(vector) != self.dimensions for vector in vectors):
            raise ValueError("embedding dimension mismatch")
        rows = [(strategy, chunk.chunk_id, chunk.document_id, chunk.source, chunk.page,
                 chunk.text, json.dumps(chunk.metadata), vector)
                for chunk, vector in zip(chunks, vectors)]
        with self._connect() as conn:
            with conn.transaction():
                conn.execute("DELETE FROM day6_chunks WHERE strategy = %s", (strategy,))
                if rows:
                    conn.executemany("""INSERT INTO day6_chunks
                        (strategy, chunk_id, document_id, source, page, text, metadata, embedding)
                        VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""", rows)

    def search(self, strategy: str, query_vector: list[float], top_k: int = 3,
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Filter metadata before exact cosine ranking and return traceable hits.

        Return chunk ID, text, score and metadata. Parameterize user-supplied values.
        """
        if top_k <= 0 or len(query_vector) != self.dimensions:
            raise ValueError("Invalid top_k or query vector dimension")
        with self._connect() as conn:
            rows = conn.execute("""SELECT chunk_id, document_id, source, page, text, metadata,
                1 - (embedding <=> %s) AS score
                FROM day6_chunks WHERE strategy = %s AND metadata @> %s::jsonb
                ORDER BY embedding <=> %s LIMIT %s""",
                (query_vector, strategy, json.dumps(filters or {}), query_vector, top_k)).fetchall()
        return [{"chunk_id": r[0], "document_id": r[1], "source": r[2], "page": r[3],
                 "text": r[4], "metadata": r[5], "score": float(r[6])} for r in rows]
