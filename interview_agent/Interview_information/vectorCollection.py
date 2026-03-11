from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

client = QdrantClient(path="./interview_db")
COLLECTION = "interview_questions"
_encoder = None

def get_encoder():
    global _encoder
    if _encoder is None:
        _encoder = SentenceTransformer("all-MiniLM-L6-v2")
    return _encoder

def create_collection():
    client.recreate_collection(
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


