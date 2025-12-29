from qdrant_client import models, QdrantClient
from qdrant_client.conversions.common_types import Filter
from embeddings_client import EmbeddingsAPIClient
import os
from pydantic import BaseModel
from typing import Literal, Optional
import uuid


class Document(BaseModel):
    # content is the data to be vectorized
    content: str
    type: Literal["conversation_transcript"]
    # userId is used for multitenancy
    userId: str
    customerId: Optional[str] = None


class VectorDBClient:
    def __init__(self):
        self._url = os.getenv("VECTOR_DB_URL")
        self._api_key = os.getenv("VECTOR_DB_API_KEY")
        self._client = QdrantClient(url=self._url, api_key=self._api_key)
        self._collection_name = os.getenv("VECTOR_DB_COLLECTION")

    def upload_documents(self, documents: list[dict]):

        self._client.upload_points(
            collection_name=self._collection_name,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid4()), vector=EmbeddingsAPIClient().embed(doc["content"]), payload=doc
                )
                for idx, doc in enumerate(documents)
            ],
        )

    def create_collection(self, distance: models.Distance = models.Distance.COSINE):
        self._client.create_collection(
            collection_name=self._collection_name, vectors_config=models.VectorParams(
                # Vector size is defined by used model nomic-embed-text-v1.5
                size=768,
                distance=distance))

    def query(self, query: str, limit: int = 10, query_filter: Filter = None):
        response = self._client.query_points(
            collection_name=self._collection_name,
            query=EmbeddingsAPIClient().embed(query),
            limit=limit,
            query_filter=query_filter
        )
        return response.points  # Return the points list, not the response object
