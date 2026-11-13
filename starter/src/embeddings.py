"""Sentence Transformers local embedding adapter (real model, no mock fallback)."""
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """Load a local Sentence Transformers model and expose a small stable contract."""

    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("Install sentence-transformers as described in README.md") from exc
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)
        dimension_fn = getattr(self._model, "get_embedding_dimension", None)
        if dimension_fn is None:
            dimension_fn = self._model.get_sentence_embedding_dimension
        self.dimensions = int(dimension_fn())
        if not self.dimensions:
            raise RuntimeError(f"Model did not report embedding dimensions: {model_name}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
        return vectors.tolist()

    def embed_query(self, question: str) -> list[float]:
        vector = self._model.encode([question], normalize_embeddings=True, show_progress_bar=False)[0]
        return vector.tolist()
