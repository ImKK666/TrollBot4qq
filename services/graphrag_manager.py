"""GraphRAG integration layer for TrollBot."""

from __future__ import annotations

import asyncio
import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

from trollbot_graphrag.config import ConfigManager, DatasetConfig
from trollbot_graphrag.models.constructor import kt_gen
from trollbot_graphrag.models.retriever import enhanced_kt_retriever


@dataclass
class GraphDocument:
    """Representation of a conversational artifact stored in GraphRAG."""

    doc_id: str
    title: str
    text: str
    metadata: Dict[str, object]

    def to_record(self) -> Dict[str, object]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "text": self.text,
            "metadata": self.metadata,
        }


class GraphRAGManager:
    """Centralised manager that orchestrates GraphRAG ingestion and retrieval."""

    _instance: Optional["GraphRAGManager"] = None
    _instance_lock = threading.Lock()

    DATASET_NAME = "trollbot"
    _DOC_ID_PATTERN = re.compile(r"\[Doc (?P<doc_id>[^\]]+)\]")

    def __init__(self) -> None:
        self.base_dir = Path("data/graphrag")
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.output_dir = self.base_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.chunks_dir = self.output_dir / "chunks"
        self.chunks_dir.mkdir(exist_ok=True)
        self.graphs_dir = self.output_dir / "graphs"
        self.graphs_dir.mkdir(exist_ok=True)
        self.logs_dir = self.output_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)

        self.corpus_path = self.base_dir / "corpus.json"
        self.qa_placeholder_path = self.base_dir / "qa_placeholder.json"
        self.schema_path = self.base_dir / "schema.json"
        self.graph_output_path = self.graphs_dir / f"{self.DATASET_NAME}.json"
        self.chunk_index_path = self.chunks_dir / f"{self.DATASET_NAME}.txt"

        self._ensure_files_initialised()
        self.config = self._build_config()

        self._graph_lock = threading.Lock()
        self._retriever_lock = threading.Lock()
        self._chunk_to_doc: Dict[str, str] = {}
        self._doc_index: Dict[str, GraphDocument] = {}
        self._retriever: Optional[enhanced_kt_retriever.KTRetriever] = None

        self._load_corpus()

    @classmethod
    def instance(cls) -> "GraphRAGManager":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    # ------------------------------------------------------------------
    # Configuration & bootstrap helpers
    # ------------------------------------------------------------------
    def _ensure_files_initialised(self) -> None:
        if not self.corpus_path.exists():
            self.corpus_path.write_text("[]", encoding="utf-8")
        if not self.qa_placeholder_path.exists():
            self.qa_placeholder_path.write_text("[]", encoding="utf-8")
        if not self.schema_path.exists():
            self._write_default_schema()

    def _write_default_schema(self) -> None:
        """Persist a lightweight default schema tailored for QQ conversations."""
        schema = {
            "nodes": {
                "user": {
                    "description": "QQ user who participates in group chats",
                    "key_properties": ["user_id", "nickname", "aliases"],
                },
                "conversation": {
                    "description": "Aggregated conversation segment summarising group interactions",
                    "key_properties": ["group_id", "time_window", "topic"],
                },
                "attitude": {
                    "description": "A stance or opinion expressed by one user about another",
                    "key_properties": ["source_user", "target_user", "sentiment"],
                },
                "memory": {
                    "description": "Memorable event, quote or behaviour extracted from conversations",
                    "key_properties": ["summary", "troll_potential"],
                },
            },
            "relations": {
                "participated_in": {
                    "description": "User participates in a conversation segment",
                    "domain": ["user"],
                    "range": ["conversation"],
                },
                "expressed": {
                    "description": "User expresses an attitude",
                    "domain": ["user"],
                    "range": ["attitude"],
                },
                "targets": {
                    "description": "Attitude targets another user",
                    "domain": ["attitude"],
                    "range": ["user"],
                },
                "records": {
                    "description": "Conversation records a memory",
                    "domain": ["conversation"],
                    "range": ["memory"],
                },
                "associated_with": {
                    "description": "Memory associated with a user",
                    "domain": ["memory"],
                    "range": ["user"],
                },
            },
            "attributes": {
                "user": ["nickname", "alias", "reputation"],
                "conversation": ["topic", "time_window", "group_id"],
                "attitude": ["description", "sentiment"],
                "memory": ["summary", "troll_potential", "timestamp"],
            },
        }
        self.schema_path.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _build_config(self) -> ConfigManager:
        config = ConfigManager()

        dataset_config = DatasetConfig(
            corpus_path=str(self.corpus_path),
            qa_path=str(self.qa_placeholder_path),
            schema_path=str(self.schema_path),
            graph_output=str(self.graph_output_path),
        )
        config.datasets[self.DATASET_NAME] = dataset_config
        config.config_data.setdefault("datasets", {})[self.DATASET_NAME] = {
            "corpus_path": str(self.corpus_path),
            "qa_path": str(self.qa_placeholder_path),
            "schema_path": str(self.schema_path),
            "graph_output": str(self.graph_output_path),
        }

        if self.DATASET_NAME not in config.construction.datasets_no_chunk:
            config.construction.datasets_no_chunk.append(self.DATASET_NAME)

        # Tweak output + retrieval directories to live under data/graphrag
        config.output.base_dir = str(self.output_dir)
        config.output.chunks_dir = str(self.chunks_dir)
        config.output.graphs_dir = str(self.graphs_dir)
        config.output.logs_dir = str(self.logs_dir)
        config.config_data.setdefault("output", {})
        config.config_data["output"].update(
            {
                "base_dir": str(self.output_dir),
                "chunks_dir": str(self.chunks_dir),
                "graphs_dir": str(self.graphs_dir),
                "logs_dir": str(self.logs_dir),
            }
        )

        config.retrieval.cache_dir = str(self.base_dir / "retriever_cache")
        config.config_data.setdefault("retrieval", {})
        config.config_data["retrieval"]["cache_dir"] = config.retrieval.cache_dir
        config.retrieval.faiss.device = "cpu"
        config.embeddings.device = "cpu"
        config.nlp.spacy_model = "en_core_web_sm"
        config.config_data.setdefault("nlp", {})["spacy_model"] = "en_core_web_sm"

        config.create_output_directories()
        return config

    # ------------------------------------------------------------------
    # Corpus management helpers
    # ------------------------------------------------------------------
    def _load_corpus(self) -> None:
        data = json.loads(self.corpus_path.read_text(encoding="utf-8"))
        self._doc_index = {}
        for raw in data:
            doc = GraphDocument(
                doc_id=raw["doc_id"],
                title=raw["title"],
                text=raw["text"],
                metadata=raw.get("metadata", {}),
            )
            self._doc_index[doc.doc_id] = doc
        self._refresh_chunk_mappings()

    def _persist_corpus(self) -> None:
        payload = [doc.to_record() for doc in self._doc_index.values()]
        self.corpus_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ------------------------------------------------------------------
    # Graph construction + retrieval
    # ------------------------------------------------------------------
    def _refresh_chunk_mappings(self) -> None:
        self._chunk_to_doc.clear()
        if not self.chunk_index_path.exists():
            return

        for line in self.chunk_index_path.read_text(encoding="utf-8").splitlines():
            if not line or "\t" not in line:
                continue
            try:
                chunk_id_part, chunk_text_part = line.split("\t", 1)
                chunk_id = chunk_id_part.replace("id: ", "").strip()
                chunk_text = chunk_text_part.replace("Chunk: ", "").strip()
            except ValueError:
                continue

            match = self._DOC_ID_PATTERN.search(chunk_text)
            if match:
                doc_id = match.group("doc_id")
                self._chunk_to_doc[chunk_id] = doc_id

    def _rebuild_graph_sync(self) -> None:
        builder = kt_gen.KTBuilder(
            self.DATASET_NAME,
            schema_path=str(self.schema_path),
            mode=self.config.construction.mode,
            config=self.config,
        )
        builder.build_knowledge_graph(str(self.corpus_path))
        self._refresh_chunk_mappings()
        self._retriever = None  # Force lazy recreation

    def _ensure_retriever(self) -> enhanced_kt_retriever.KTRetriever:
        with self._retriever_lock:
            if self._retriever is None:
                retriever = enhanced_kt_retriever.KTRetriever(
                    self.DATASET_NAME,
                    json_path=str(self.graph_output_path),
                    schema_path=str(self.schema_path),
                    config=self.config,
                    device="cpu",
                )
                retriever.build_indices()
                self._retriever = retriever
            return self._retriever

    # ------------------------------------------------------------------
    # Public APIs
    # ------------------------------------------------------------------
    def add_documents(self, docs: Iterable[GraphDocument]) -> None:
        with self._graph_lock:
            updated = False
            for doc in docs:
                if doc.doc_id not in self._doc_index:
                    self._doc_index[doc.doc_id] = doc
                    updated = True
                else:
                    self._doc_index[doc.doc_id] = doc
                    updated = True
            if not updated:
                return
            self._persist_corpus()
            self._rebuild_graph_sync()

    async def add_documents_async(self, docs: Iterable[GraphDocument]) -> None:
        docs_list = list(docs)
        if not docs_list:
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.add_documents, docs_list)

    def search(
        self, query: str, user_id: Optional[int] = None, limit: int = 5
    ) -> List[Dict[str, object]]:
        if not self.graph_output_path.exists():
            return []
        retriever = self._ensure_retriever()
        _, result = retriever.retrieve(query)
        chunk_ids = result.get("chunk_ids", []) if isinstance(result, dict) else []

        ranked: List[Dict[str, object]] = []
        for chunk_id in chunk_ids:
            doc_id = self._chunk_to_doc.get(chunk_id)
            if not doc_id:
                continue
            doc = self._doc_index.get(doc_id)
            if not doc:
                continue
            if user_id is not None:
                related_users = doc.metadata.get("related_users") or []
                if user_id not in related_users and str(user_id) not in related_users:
                    continue
            ranked.append(
                {
                    "doc_id": doc.doc_id,
                    "title": doc.title,
                    "text": doc.text,
                    "metadata": doc.metadata,
                }
            )
            if len(ranked) >= limit:
                break

        return ranked

    def summarise_user(self, user_id: int) -> Dict[str, object]:
        query = f"Summarise the personality, aliases and social attitudes of user {user_id}."
        memories = self.search(query, user_id=user_id, limit=10)
        combined = "\n".join(entry["text"] for entry in memories)
        aliases = []
        attitudes = []
        for entry in memories:
            aliases.extend(entry["metadata"].get("aliases", []))
            attitudes.extend(entry["metadata"].get("attitudes", []))

        return {
            "user_id": user_id,
            "memories": memories,
            "combined_text": combined,
            "aliases": sorted(set(map(str, aliases))),
            "attitudes": attitudes,
        }

    def reset(self) -> None:
        with self._graph_lock:
            self._doc_index.clear()
            self._chunk_to_doc.clear()
            self._retriever = None
            self._persist_corpus()
            if self.chunk_index_path.exists():
                self.chunk_index_path.unlink()
            if self.graph_output_path.exists():
                self.graph_output_path.unlink()


def create_conversation_document(
    group_id: int,
    start_time: int,
    end_time: int,
    summary: str,
    participants: Dict[int, str],
) -> GraphDocument:
    doc_id = str(uuid4())
    window = f"{start_time}-{end_time}"
    title = f"[Doc {doc_id}] Conversation in group {group_id} during {window}"
    participants_text = "\n".join(
        f"User {uid}: {viewpoint}" for uid, viewpoint in participants.items()
    )
    text = (
        f"Topic summary: {summary}\n"
        f"Participants and viewpoints:\n{participants_text if participants_text else 'N/A'}"
    )
    metadata = {
        "group_id": group_id,
        "time_window": window,
        "related_users": list(participants.keys()),
    }
    return GraphDocument(doc_id=doc_id, title=title, text=text, metadata=metadata)


def create_memory_document(
    user_id: int,
    message_id: int,
    original_text: str,
    summary_text: str,
    troll_potential: int,
    timestamp: int,
) -> GraphDocument:
    doc_id = str(message_id)
    title = f"[Doc {doc_id}] Memory of user {user_id}"
    text = f"Original quote: {original_text}\nSummary: {summary_text}\nTroll potential: {troll_potential}"
    metadata = {
        "related_users": [user_id],
        "timestamp": timestamp,
        "troll_potential": troll_potential,
    }
    return GraphDocument(doc_id=doc_id, title=title, text=text, metadata=metadata)


def create_attitude_document(
    source_user: int,
    target_user: int,
    attitude_desc: str,
    timestamp: Optional[int] = None,
) -> GraphDocument:
    doc_id = str(uuid4())
    title = f"[Doc {doc_id}] Attitude from {source_user} to {target_user}"
    text = (
        f"User {source_user} expresses attitude towards {target_user}: {attitude_desc}"
    )
    metadata = {
        "related_users": [source_user, target_user],
        "attitudes": [
            {
                "source": source_user,
                "target": target_user,
                "description": attitude_desc,
                "timestamp": timestamp,
            }
        ],
    }
    return GraphDocument(doc_id=doc_id, title=title, text=text, metadata=metadata)


async def store_documents(docs: Iterable[GraphDocument]) -> None:
    manager = GraphRAGManager.instance()
    await manager.add_documents_async(list(docs))


async def search_documents(
    query: str, user_id: Optional[int] = None, limit: int = 5
) -> List[Dict[str, object]]:
    manager = GraphRAGManager.instance()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, manager.search, query, user_id, limit)


async def summarise_user(user_id: int) -> Dict[str, object]:
    manager = GraphRAGManager.instance()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, manager.summarise_user, user_id)


def reset_graphrag() -> None:
    manager = GraphRAGManager.instance()
    manager.reset()
