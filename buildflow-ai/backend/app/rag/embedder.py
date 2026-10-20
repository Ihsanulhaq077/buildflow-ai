"""
Embedding generation for RAG.

Supports:
1. Local embeddings via sentence-transformers (CPU/GPU)
2. API-based embeddings (OpenAI-compatible endpoint)
3. Deterministic fallback (hash-based embeddings for testing without models)

All embeddings use the same dimension for consistency.
"""
import hashlib
import logging
import os
from typing import Optional

import numpy as np

log = logging.getLogger("buildflow.rag.embedder")


class EmbeddingService:
    """Generate embeddings for text chunks."""

    def __init__(self):
        self._model = None
        self.model_name = "all-MiniLM-L6-v2"
        self.dimension = 384
        self.use_api = False
        self.api_url: Optional[str] = None
        self.api_key: Optional[str] = None

    def initialize(self, config: Optional[dict] = None):
        """Lazy initialization of the embedding model."""
        if config:
            self.model_name = config.get("model_name", self.model_name)
            self.dimension = config.get("dimension", self.dimension)
            self.use_api = config.get("use_api", False)
            self.api_url = config.get("api_url")
            self.api_key = config.get("api_key")

        # Try to load local model
        if not self.use_api and self._model is None:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
                self._model = SentenceTransformer(self.model_name)
                actual_dim = self._model.get_sentence_embedding_dimension()
                if actual_dim:
                    self.dimension = actual_dim
                log.info(f"Loaded local embedding model: {self.model_name}, dim={self.dimension}")
            except ImportError:
                log.warning("sentence-transformers not installed, using deterministic fallback")
                self._model = None
            except Exception as e:
                log.warning(f"Failed to load embedding model: {e}. Using deterministic fallback.")
                self._model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts into vectors."""
        if not self._model is None and not self.use_api:
            try:
                embeddings = self._model.encode(texts, convert_to_numpy=False, normalize_embeddings=True)
                return [e.tolist() for e in embeddings]
            except Exception as e:
                log.error(f"Local embedding failed: {e}. Falling back to deterministic mode.")

        if self.use_api and self.api_url:
            try:
                import httpx
                headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                payload = {"input": texts, "model": self.model_name}
                with httpx.Client(timeout=60) as client:
                    resp = client.post(f"{self.api_url}/v1/embeddings", json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    return [item["embedding"] for item in data.get("data", [])]
            except Exception as e:
                log.error(f"API embedding failed: {e}. Falling back to deterministic mode.")

        # Deterministic fallback — hash-based vectors for testing
        log.debug("Using deterministic embedding fallback")
        return [self._deterministic_embed(t) for t in texts]

    def _deterministic_embed(self, text: str) -> list[float]:
        """Deterministic hash-based embedding (for testing without real models)."""
        vectors: list[list[float]] = []
        for seed in range(self.dimension // 32 + 1):
            h = hashlib.sha512(f"{seed}:{text}".encode()).digest()
            vec = [((int.from_bytes(h[i:i + 4], "big") % 10000) / 5000) - 1.0 for i in range(0, min(len(h), self.dimension * 4), 4)]
            vectors.extend(vec[:32])
        return vectors[:self.dimension]

    def embed_single(self, text: str) -> list[float]:
        """Embed a single text."""
        return self.embed([text])[0]

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        a_np = np.array(a)
        b_np = np.array(b)
        dot = np.dot(a_np, b_np)
        norm = np.linalg.norm(a_np) * np.linalg.norm(b_np)
        if norm == 0:
            return 0.0
        return float(dot / norm)


# Singleton
embedding_service = EmbeddingService()