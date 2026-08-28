from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from qdrant_client import AsyncQdrantClient
from redis import asyncio as redis

from .config import Settings, get_settings
from .indexing import enqueue_index_job
from .rag import answer_chat
from .schemas import ChatRequest, ChatResponse, IndexDocumentRequest, IndexQueuedResponse
from .security import require_service_token


def create_app(
    settings: Settings | None = None,
    redis_client=None,
    qdrant_client=None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings or get_settings()
        owns_redis = redis_client is None
        owns_qdrant = qdrant_client is None
        app.state.redis = redis_client or redis.from_url(
            app.state.settings.redis_url,
            decode_responses=True,
        )
        app.state.qdrant = qdrant_client or AsyncQdrantClient(
            url=app.state.settings.qdrant_url,
        )
        try:
            yield
        finally:
            if owns_redis:
                await app.state.redis.aclose()
            if owns_qdrant:
                await app.state.qdrant.close()

    app = FastAPI(
        title="Portail RH Onboarding AI",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    @app.get("/health", tags=["operations"])
    async def health():
        return {"status": "ok", "service": "onboarding-ai"}

    @app.get("/ready", tags=["operations"])
    async def ready():
        checks = {"redis": False, "qdrant": False}
        try:
            checks["redis"] = bool(await app.state.redis.ping())
        except Exception:
            pass
        try:
            await app.state.qdrant.get_collections()
            checks["qdrant"] = True
        except Exception:
            pass
        status = "ready" if all(checks.values()) else "unavailable"
        payload = {"status": status, "checks": checks}
        if status != "ready":
            return JSONResponse(status_code=503, content=payload)
        return payload

    @app.post(
        "/v1/index/jobs",
        response_model=IndexQueuedResponse,
        status_code=status.HTTP_202_ACCEPTED,
        dependencies=[Depends(require_service_token)],
        tags=["indexing"],
    )
    async def create_index_job(payload: IndexDocumentRequest, request: Request):
        job = await enqueue_index_job(payload, request.app.state.settings, request.app.state.redis)
        return IndexQueuedResponse(job_id=job.job_id)

    @app.post(
        "/v1/chat",
        response_model=ChatResponse,
        dependencies=[Depends(require_service_token)],
        tags=["chat"],
    )
    async def chat(payload: ChatRequest, request: Request):
        return await answer_chat(
            payload,
            request.app.state.settings,
            request.app.state.redis,
            request.app.state.qdrant,
        )

    return app


app = create_app()
