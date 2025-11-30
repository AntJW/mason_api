from qdrant_client import models, QdrantClient
from qdrant_client.conversions.common_types import Filter
from sentence_transformers import SentenceTransformer
import os


class VectorDBClient:
    def __init__(self, url: str = os.getenv("VECTOR_DB_URL"), embeddings_model: str = os.getenv("EMBEDDINGS_MODEL"), collection_name: str = os.getenv("VECTOR_DB_COLLECTION")):
        self.client = QdrantClient(url=url)
        self._embeddings_model = embeddings_model
        self._encoder = None
        self._collection_name = collection_name

    @property
    def encoder(self):
        """Lazy load the encoder on first access"""
        if self._encoder is None:
            self._encoder = SentenceTransformer(
                self._embeddings_model, device="cpu", trust_remote_code=True)
        return self._encoder

    def upload_documents(self, documents: list[dict]):
        self.client.upload_points(
            collection_name=self._collection_name,
            points=[
                models.PointStruct(
                    id=idx, vector=self.encoder.encode(doc["description"]).tolist(), payload=doc
                )
                for idx, doc in enumerate(documents)
            ],
        )

    def create_collection(self, collection_name: str, vectors_config: models.VectorParams):
        self.client.create_collection(
            collection_name=collection_name, vectors_config=vectors_config)

    def query(self, query: str, limit: int = 10, query_filter: Filter = None):
        return self.client.query_points(
            collection_name=self._collection_name,
            query=self.encoder.encode(query).tolist(),
            limit=limit,
            query_filter=query_filter
        )
