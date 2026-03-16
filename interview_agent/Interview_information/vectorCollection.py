import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if QDRANT_URL:
    client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
else:
    client = QdrantClient(path="./interview_db") 

COLLECTION = "interview_questions"
_encoder = None

def get_encoder():
    global _encoder
    if _encoder is None:
        snapshot_path = "/app/model_cache/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/c9745ed1d9f207416be6d2e6f8de32d1f16199bf"
        if os.path.exists(snapshot_path):
            _encoder = SentenceTransformer(snapshot_path)
        else:
            cache_dir = os.getenv("SENTENCE_TRANSFORMERS_HOME", "./model_cache")
            _encoder = SentenceTransformer("all-MiniLM-L6-v2", cache_folder=cache_dir)
    return _encoder


def create_collection():
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION not in existing:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )

def store(documents: list[dict]):
    encoder = get_encoder()
    points = [
        PointStruct(
            id=i,
            vector=encoder.encode(d["content"]).tolist(),
            payload={"title": d["title"], "url": d["url"], "content": d["content"]}
        )
        for i, d in enumerate(documents)
    ]
    client.upsert(collection_name=COLLECTION, points=points)


