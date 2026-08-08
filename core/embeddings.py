"""
embeddings.py — Vector store interface.

Wraps ChromaDB. Enforces the invariant that the same embedding model is used
at ingest and query time, since mismatched models cause silent retrieval failure.
"""

from pathlib import Path
from typing import Dict, List, Optional

import chromadb

from core.models import OllamaClient

# Setting key that records which embed model built each collection
MODEL_META_KEY = "_embed_model"


class VectorStore:
    """ChromaDB wrapper with embedding-model tracking."""

    def __init__(self, chroma_dir: str, ollama: OllamaClient, embed_model: str):
        self.chroma_dir = chroma_dir
        self.ollama = ollama
        self.embed_model = embed_model
        self.client = chromadb.PersistentClient(path=chroma_dir)

    def list_collections(self) -> List[str]:
        """Names of all collections."""
        return [c.name for c in self.client.list_collections()]

    def collection_counts(self) -> Dict[str, int]:
        """Chunk count per collection."""
        return {
            name: self.client.get_collection(name).count()
            for name in self.list_collections()
        }

    @staticmethod
    def validate_name(name: str) -> tuple[bool, str]:
        """
        Check a collection name against ChromaDB's rules.
        Returns (is_valid, message). Message is empty when valid.
        """
        import re
        if not name:
            return False, "Name cannot be empty."
        if len(name) < 3 or len(name) > 512:
            return False, "Name must be 3-512 characters."
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]", name):
            return False, (
                "Use only letters, numbers, dots, underscores and hyphens. "
                "Must start and end with a letter or number."
            )
        return True, ""

    def get_or_create(self, name: str):
        """Get a collection, creating it if needed. Records the embed model."""
        col = self.client.get_or_create_collection(
            name=name, metadata={MODEL_META_KEY: self.embed_model}
        )
        return col

    def collection_embed_model(self, name: str) -> Optional[str]:
        """Which embed model built this collection, if recorded."""
        try:
            col = self.client.get_collection(name)
            return (col.metadata or {}).get(MODEL_META_KEY)
        except Exception:
            return None

    def check_model_match(self, name: str) -> tuple[bool, Optional[str]]:
        """
        Verify the configured embed model matches the collection's.
        Returns (matches, recorded_model). Unrecorded collections return (True, None)
        since we cannot tell — legacy collections predate this metadata.
        """
        recorded = self.collection_embed_model(name)
        if recorded is None:
            return True, None
        return recorded == self.embed_model, recorded

    def add_chunks(
        self,
        collection: str,
        chunks: List[str],
        source: str,
        extra_metadata: Optional[dict] = None,
        on_progress=None,
    ) -> int:
        """Embed and store chunks. Returns the number added."""
        col = self.get_or_create(collection)
        added = 0
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            vec = self.ollama.embed(self.embed_model, chunk)
            meta = {"source": source, "chunk_index": i}
            if extra_metadata:
                meta.update(extra_metadata)
            col.add(
                ids=[f"{source}_chunk_{i}"],
                documents=[chunk],
                embeddings=[vec],
                metadatas=[meta],
            )
            added += 1
            if on_progress:
                on_progress(i + 1, len(chunks))
        return added

    def query(
        self,
        collection: str,
        text: str,
        top_k: int = 15,
        where: Optional[dict] = None,
    ) -> dict:
        """Semantic search. Returns ChromaDB's result dict."""
        col = self.client.get_collection(collection)
        vec = self.ollama.embed(self.embed_model, text)
        kwargs = {"query_embeddings": [vec], "n_results": top_k}
        if where:
            kwargs["where"] = where
        return col.query(**kwargs)

    def sources_in(self, collection: str, limit: int = 5000) -> List[str]:
        """Distinct source filenames in a collection."""
        try:
            col = self.client.get_collection(collection)
            sample = col.get(limit=limit, include=["metadatas"])
            return sorted({m["source"] for m in sample["metadatas"] if "source" in m})
        except Exception:
            return []

    def chunks_from_source(self, collection: str, source: str, limit: int = 200) -> List[str]:
        """All chunks belonging to one source document, in order."""
        col = self.client.get_collection(collection)
        result = col.get(
            where={"source": source}, limit=limit, include=["documents", "metadatas"]
        )
        pairs = list(zip(result["documents"], result["metadatas"]))
        pairs.sort(key=lambda p: p[1].get("chunk_index", 0))
        return [doc for doc, _ in pairs]

    def delete_source(self, collection: str, source: str) -> int:
        """
        Remove every passage belonging to one document. Returns how many went.

        Used when a document is uploaded again. Without this a second upload
        leaves both versions in place and retrieval may answer from the older
        one, which is worse than either replacing or refusing outright.
        """
        try:
            col = self.client.get_collection(collection)
            existing = col.get(where={"source": source}, include=[])
            ids = existing.get("ids", [])
            if ids:
                col.delete(ids=ids)
            return len(ids)
        except Exception:
            return 0

    def delete_collection(self, name: str) -> None:
        self.client.delete_collection(name)
