"""Persistent PostgreSQL/pgvector storage with exact cosine ranking."""
import json
from typing import Any
from .models import Chunk


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
        if strategy not in self._collections:
            safe_name = f"day6_{strategy.lower()}"
            self._collections[strategy] = self._client.get_or_create_collection(
                name=safe_name, metadata={"hnsw:space": "cosine"}
            )
        return self._collections[strategy]

    def create_schema(self) -> None:
        """Create persistent, cosine-distance collections for the strategies."""
        for strategy in ("A", "B", "C"):
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
               filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Run cosine HNSW search, applying any payload filter before retrieval."""
        if top_k <= 0 or len(query_vector) != self.dimensions:
            raise ValueError("Invalid top_k or query vector dimension")
        query = {"query_embeddings": [query_vector], "n_results": top_k,
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
        return hits


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
