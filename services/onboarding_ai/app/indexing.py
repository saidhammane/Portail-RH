import base64
import binascii
import json
import uuid
from pathlib import Path

import httpx
from docx import Document
from fastapi import HTTPException, status
from pypdf import PdfReader
from qdrant_client import models

from .config import Settings
from .providers import embed_texts
from .schemas import IndexDocumentRequest, IndexJob


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
LOCK_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


async def enqueue_index_job(payload: IndexDocumentRequest, settings: Settings, redis_client) -> IndexJob:
    suffix = Path(payload.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported document format")
    try:
        content = base64.b64decode(payload.content_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(status_code=422, detail="Invalid document encoding") from error
    if not content or len(content) > settings.max_document_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Document exceeds the configured size limit",
        )

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex
    file_path = settings.data_dir / (job_id + suffix)
    file_path.write_bytes(content)
    job = IndexJob(
        job_id=job_id,
        file_path=str(file_path),
        **payload.model_dump(exclude={"content_base64"}),
    )
    try:
        await redis_client.set(
            "onboarding:index:job:%s" % job_id,
            job.model_dump_json(),
            ex=settings.job_ttl,
        )
        await redis_client.rpush(settings.redis_queue, job_id)
    except Exception:
        file_path.unlink(missing_ok=True)
        raise
    return job


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".txt":
        text = path.read_text(encoding="utf-8-sig")
    elif suffix == ".pdf":
        text = "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    elif suffix == ".docx":
        text = "\n".join(paragraph.text for paragraph in Document(path).paragraphs)
    else:
        raise ValueError("Unsupported document format")
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not text:
        raise ValueError("No textual content found; OCR is not enabled")
    return text


def chunk_text(text: str, max_chars: int = 1200, overlap_chars: int = 200) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    chunks = []
    start = 0
    while start < len(normalized):
        end = min(start + max_chars, len(normalized))
        if end < len(normalized):
            boundary = normalized.rfind(" ", start, end)
            if boundary > start:
                end = boundary
        chunks.append(normalized[start:end].strip())
        if end >= len(normalized):
            break
        next_start = max(end - overlap_chars, start + 1)
        boundary = normalized.find(" ", next_start)
        start = boundary + 1 if boundary != -1 and boundary < end else next_start
    return [chunk for chunk in chunks if chunk]


async def ensure_collection(qdrant_client, collection: str, vector_size: int) -> None:
    if not await qdrant_client.collection_exists(collection):
        await qdrant_client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )
        for field_name, schema in (
            ("document_id", models.PayloadSchemaType.INTEGER),
            ("company_id", models.PayloadSchemaType.INTEGER),
            ("department_id", models.PayloadSchemaType.INTEGER),
            ("visibility", models.PayloadSchemaType.KEYWORD),
            ("checksum", models.PayloadSchemaType.KEYWORD),
        ):
            await qdrant_client.create_payload_index(
                collection_name=collection,
                field_name=field_name,
                field_schema=schema,
                wait=True,
            )


async def index_chunks(job: IndexJob, chunks: list[str], vectors: list[list[float]], settings: Settings, qdrant_client) -> None:
    await ensure_collection(qdrant_client, settings.qdrant_collection, len(vectors[0]))
    document_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="document_id",
                match=models.MatchValue(value=job.document_id),
            )
        ]
    )
    await qdrant_client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=models.FilterSelector(filter=document_filter),
        wait=True,
    )
    points = []
    for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
        point_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                "%s:%s:%s:%s" % (job.company_id, job.document_id, job.version, index),
            )
        )
        points.append(
            models.PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "document_id": job.document_id,
                    "title": job.title,
                    "category": job.category,
                    "company_id": job.company_id,
                    "department_id": job.department_id,
                    "visibility": job.visibility,
                    "version": job.version,
                    "checksum": job.checksum,
                    "chunk_index": index,
                    "section": "Chunk %s" % (index + 1),
                    "text": chunk,
                    "language": job.language,
                },
            )
        )
    await qdrant_client.upsert(
        collection_name=settings.qdrant_collection,
        points=points,
        wait=True,
    )


async def notify_odoo(settings: Settings, payload: dict) -> None:
    if not settings.odoo_callback_url:
        return
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            settings.odoo_callback_url,
            headers={"X-Service-Token": settings.service_token.get_secret_value()},
            json=payload,
        )
        response.raise_for_status()


async def process_index_job(
    job: IndexJob,
    settings: Settings,
    redis_client,
    qdrant_client,
    callback=notify_odoo,
) -> str:
    lock_key = "onboarding:index:lock:%s:%s" % (job.company_id, job.checksum)
    marker_key = "onboarding:indexed:%s:%s:%s:%s" % (
        job.company_id,
        job.document_id,
        job.version,
        job.checksum,
    )
    if await redis_client.get(marker_key):
        await callback(
            settings,
            {"document_id": job.document_id, "checksum": job.checksum, "state": "indexed"},
        )
        return "duplicate"
    acquired = await redis_client.set(
        lock_key,
        job.job_id,
        ex=settings.index_lock_ttl,
        nx=True,
    )
    if not acquired:
        return "locked"
    try:
        await callback(
            settings,
            {"document_id": job.document_id, "checksum": job.checksum, "state": "processing"},
        )
        chunks = chunk_text(extract_text(job.file_path))
        vectors = await embed_texts(chunks, settings)
        await index_chunks(job, chunks, vectors, settings, qdrant_client)
        await redis_client.set(marker_key, "1")
        await redis_client.incr("onboarding:documents:version:%s" % job.company_id)
        await callback(
            settings,
            {"document_id": job.document_id, "checksum": job.checksum, "state": "indexed"},
        )
        return "indexed"
    except Exception as error:
        await callback(
            settings,
            {
                "document_id": job.document_id,
                "checksum": job.checksum,
                "state": "error",
                "error_message": str(error)[:500],
            },
        )
        raise
    finally:
        await redis_client.eval(LOCK_RELEASE_SCRIPT, 1, lock_key, job.job_id)
