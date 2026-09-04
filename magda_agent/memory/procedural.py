"""
MemGPT Procedural Memory Manager.

Manages reusable code snippets, algorithmic templates, and procedural workflows
in a separate procedural memory database, isolated and retrieved separately
from conversational/episodic records.
"""

import hashlib
import json
import logging
import math
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Union

try:
    import chromadb
except ImportError:
    chromadb = None

logger = logging.getLogger(__name__)


def _cosine_sim(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (norm_a * norm_b)))


def _local_hash_embed(text: str, dim: int = 64) -> List[float]:
    words = [w.lower() for w in text.split() if w.isalnum()]
    if not words:
        words = [text.lower()]
    vec = [0.0] * dim
    for word in words:
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h % 2 == 0) else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


class InMemoryProceduralCollection:
    """In-memory collection mimicking ChromaDB interface for test isolation and fallback."""

    def __init__(self, name: str = "procedural_memory") -> None:
        self.name = name
        self._entries: Dict[str, Dict[str, Any]] = {}

    def add(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> None:
        for doc, meta, doc_id in zip(documents, metadatas, ids):
            self._entries[doc_id] = {
                "id": doc_id,
                "document": doc,
                "metadata": meta,
                "embedding": _local_hash_embed(doc),
            }

    def query(
        self,
        query_texts: List[str],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, List[Any]]:
        if not self._entries or not query_texts:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]]}

        query_vec = _local_hash_embed(query_texts[0])
        candidates = list(self._entries.values())

        # Filter by where clause
        if where:
            filtered = []
            for item in candidates:
                meta = item["metadata"]
                match = True
                for k, v in where.items():
                    if k == "$and" and isinstance(v, list):
                        for sub_clause in v:
                            for sk, sv in sub_clause.items():
                                if meta.get(sk) != sv:
                                    match = False
                                    break
                    elif meta.get(k) != v:
                        match = False
                        break
                if match:
                    filtered.append(item)
            candidates = filtered

        # Score by cosine similarity
        scored = []
        for item in candidates:
            sim = _cosine_sim(query_vec, item["embedding"])
            scored.append((sim, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [item for sim, item in scored[:n_results]]

        return {
            "ids": [[it["id"] for it in top]],
            "documents": [[it["document"] for it in top]],
            "metadatas": [[it["metadata"] for it in top]],
        }

    def get(self, where: Optional[Dict[str, Any]] = None) -> Dict[str, List[Any]]:
        candidates = list(self._entries.values())
        if where:
            filtered = []
            for item in candidates:
                meta = item["metadata"]
                match = True
                for k, v in where.items():
                    if k == "$and" and isinstance(v, list):
                        for sub_clause in v:
                            for sk, sv in sub_clause.items():
                                if meta.get(sk) != sv:
                                    match = False
                                    break
                    elif meta.get(k) != v:
                        match = False
                        break
                if match:
                    filtered.append(item)
            candidates = filtered

        return {
            "ids": [it["id"] for it in candidates],
            "documents": [it["document"] for it in candidates],
            "metadatas": [it["metadata"] for it in candidates],
        }

    def delete(self, ids: Optional[List[str]] = None, where: Optional[Dict[str, Any]] = None) -> None:
        if ids:
            for doc_id in ids:
                self._entries.pop(doc_id, None)
        elif where:
            matched = self.get(where=where)
            for doc_id in matched.get("ids", []):
                self._entries.pop(doc_id, None)
    def update(
        self,
        ids: List[str],
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        for idx, doc_id in enumerate(ids):
            if doc_id in self._entries:
                if documents and idx < len(documents):
                    self._entries[doc_id]["document"] = documents[idx]
                    self._entries[doc_id]["embedding"] = _local_hash_embed(documents[idx])
                if metadatas and idx < len(metadatas):
                    self._entries[doc_id]["metadata"].update(metadatas[idx])

    def upsert(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str],
    ) -> None:
        for doc, meta, doc_id in zip(documents, metadatas, ids):
            self._entries[doc_id] = {
                "id": doc_id,
                "document": doc,
                "metadata": meta,
                "embedding": _local_hash_embed(doc),
            }


class ProceduralMemory:
    """
    Procedural memory stores reusable successful methods, code snippets, and procedures.
    Operates a distinct memory partition isolated from episodic conversational logs.
    """

    def __init__(
        self,
        persist_directory: str = ":memory:",
        client: Optional[Any] = None,
    ) -> None:
        """Initialize ProceduralMemory with ChromaDB or In-Memory fallback."""
        self.persist_directory = persist_directory

        if client is not None:
            self.client = client
            if hasattr(self.client, "get_or_create_collection"):
                self.collection = self.client.get_or_create_collection(name="procedural_memory")
            else:
                self.collection = self.client
        elif chromadb is not None and persist_directory != ":memory:":
            try:
                self.client = chromadb.PersistentClient(path=persist_directory)
                self.collection = self.client.get_or_create_collection(name="procedural_memory")
                logger.info(f"Initialized ProceduralMemory with persistent directory: {persist_directory}")
            except Exception as e:
                logger.warning(f"Failed to initialize ChromaDB PersistentClient: {e}. Using fallback.")
                self.collection = InMemoryProceduralCollection(name="procedural_memory")
        elif chromadb is not None and persist_directory == ":memory:":
            try:
                self.client = chromadb.EphemeralClient()
                self.collection = self.client.get_or_create_collection(name="procedural_memory")
                logger.info("Initialized ProceduralMemory with EphemeralClient")
            except Exception as e:
                logger.warning(f"Failed to initialize ChromaDB EphemeralClient: {e}. Using fallback.")
                self.collection = InMemoryProceduralCollection(name="procedural_memory")
        else:
            logger.info("Initialized ProceduralMemory with InMemoryProceduralCollection fallback")
            self.collection = InMemoryProceduralCollection(name="procedural_memory")

    def store_procedure(
        self,
        name: str,
        procedure: str,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        language: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        Store a procedural memory (e.g., a code snippet, method, or steps) with metadata.
        Returns the unique memory_id.
        """
        try:
            memory_id = str(uuid.uuid4())
            meta = metadata.copy() if metadata else {}
            meta["name"] = name
            if user_id is not None:
                meta["user_id"] = user_id
            if language is not None:
                meta["language"] = language
            if tags:
                meta["tags"] = ",".join(tags)
            meta["created_at"] = time.time()

            content = f"Procedure Name: {name}\nProcedure: {procedure}"
            if language:
                content = f"Language: {language}\n" + content

            self.collection.add(
                documents=[content],
                metadatas=[meta],
                ids=[memory_id],
            )
            logger.debug(f"Stored procedure: {name} (ID: {memory_id})")
            return memory_id
        except Exception as e:
            logger.error(f"Failed to store procedure: {e}")
            raise

    def recall_procedure(
        self,
        query: str,
        top_k: int = 5,
        user_id: Optional[int] = None,
        language: Optional[str] = None,
    ) -> List[str]:
        """
        Recalls relevant procedures based on semantic similarity to query.
        Returns matching procedural document texts.
        """
        try:
            query_kwargs: Dict[str, Any] = {
                "query_texts": [query],
                "n_results": top_k,
            }
            where_clauses: List[Dict[str, Any]] = []
            if user_id is not None:
                where_clauses.append({"user_id": user_id})
            if language is not None:
                where_clauses.append({"language": language})

            if len(where_clauses) == 1:
                query_kwargs["where"] = where_clauses[0]
            elif len(where_clauses) > 1:
                query_kwargs["where"] = {"$and": where_clauses}

            results = self.collection.query(**query_kwargs)
            if results and results.get("documents") and len(results["documents"]) > 0:
                return results["documents"][0]
            return []
        except Exception as e:
            logger.error(f"Failed to recall procedures: {e}")
            return []

    def get_procedure_versions(self, name: str, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieves all versions/instances of a skill procedure by name.
        """
        try:
            where_clause: Dict[str, Any] = {"name": name}
            if user_id is not None:
                where_clause = {"$and": [{"name": name}, {"user_id": user_id}]}

            results = self.collection.get(where=where_clause)
            return results
        except Exception as e:
            logger.error(f"Failed to get procedure versions: {e}")
            return {}

    def delete_procedure(self, procedure_id: str) -> bool:
        """Deletes a procedure by its memory ID."""
        try:
            self.collection.delete(ids=[procedure_id])
            logger.info(f"Deleted procedure ID {procedure_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete procedure: {e}")
            return False

    def list_all_procedures(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Lists all stored procedures with metadata."""
        try:
            where = {"user_id": user_id} if user_id is not None else None
            res = self.collection.get(where=where)
            items = []
            ids = res.get("ids", [])
            docs = res.get("documents", [])
            metas = res.get("metadatas", [])
            for i, d, m in zip(ids, docs, metas):
                items.append({"id": i, "document": d, "metadata": m})
            return items
        except Exception as e:
            logger.error(f"Failed to list procedures: {e}")
            return []
