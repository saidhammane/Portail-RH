import base64
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.indexing import chunk_text, process_index_job
from app.main import create_app


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.queues = {}

    async def ping(self):
        return True

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key):
        return self.values.get(key)

    async def rpush(self, key, value):
        self.queues.setdefault(key, []).append(value)

    async def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    async def eval(self, script, count, key, expected):
        if self.values.get(key) == expected:
            del self.values[key]
            return 1
        return 0


class FakeQdrant:
    def __init__(self):
        self.created = False
        self.points = []
        self.upsert_calls = 0

    async def get_collections(self):
        return []

    async def collection_exists(self, name):
        return self.created

    async def create_collection(self, **kwargs):
        self.created = True

    async def create_payload_index(self, **kwargs):
        return None

    async def delete(self, **kwargs):
        self.points = []

    async def upsert(self, collection_name, points, wait):
        self.points = points
        self.upsert_calls += 1


def make_settings(tmp_path: Path):
    return Settings(service_token="x" * 32, data_dir=tmp_path)


def index_payload():
    return {
        "document_id": 42,
        "title": "Guide d'accueil",
        "filename": "guide.txt",
        "content_base64": base64.b64encode(
            "Les horaires sont de 9h a 18h. Le badge est obligatoire.".encode()
        ).decode(),
        "category": "welcome",
        "company_id": 1,
        "department_id": 3,
        "visibility": "department",
        "version": 1,
        "checksum": "a" * 64,
        "language": "fr",
    }


def test_index_job_endpoint_requires_service_authentication(tmp_path):
    redis = FakeRedis()
    app = create_app(make_settings(tmp_path), redis, FakeQdrant())
    with TestClient(app) as client:
        unauthorized = client.post("/v1/index/jobs", json=index_payload())
        accepted = client.post(
            "/v1/index/jobs",
            json=index_payload(),
            headers={"X-Service-Token": "x" * 32},
        )
    assert unauthorized.status_code == 401
    assert accepted.status_code == 202
    job_id = accepted.json()["job_id"]
    assert redis.queues["onboarding:index:queue"] == [job_id]
    assert (tmp_path / (job_id + ".txt")).exists()


def test_worker_indexes_chunks_and_skips_duplicate_checksum(tmp_path):
    redis = FakeRedis()
    qdrant = FakeQdrant()
    settings = make_settings(tmp_path)
    callbacks = []

    async def callback(_settings, payload):
        callbacks.append(payload)

    app = create_app(settings, redis, qdrant)
    with TestClient(app) as client:
        response = client.post(
            "/v1/index/jobs",
            json=index_payload(),
            headers={"X-Service-Token": "x" * 32},
        )
    job_id = response.json()["job_id"]
    from app.schemas import IndexJob

    job = IndexJob.model_validate_json(redis.values["onboarding:index:job:%s" % job_id])

    import asyncio

    first = asyncio.run(process_index_job(job, settings, redis, qdrant, callback))
    second = asyncio.run(process_index_job(job, settings, redis, qdrant, callback))

    assert first == "indexed"
    assert second == "duplicate"
    assert qdrant.upsert_calls == 1
    assert qdrant.points[0].payload["document_id"] == 42
    assert qdrant.points[0].payload["visibility"] == "department"
    assert qdrant.points[0].payload["text"]
    assert callbacks[-1]["state"] == "indexed"


def test_chunking_is_bounded_and_overlapping():
    text = " ".join("mot%s" % index for index in range(500))
    chunks = chunk_text(text, max_chars=200, overlap_chars=30)
    assert len(chunks) > 2
    assert all(0 < len(chunk) <= 200 for chunk in chunks)
