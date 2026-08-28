import hashlib
import json
import time

from fastapi import HTTPException, status
from qdrant_client import models

from .config import Settings
from .providers import STOP_WORDS, TOKEN_PATTERN, embed_texts, generate_grounded_answer
from .schemas import ChatRequest, ChatResponse, ChatSource


REFUSAL_ANSWER = "Information insuffisante dans les documents autorises."


def build_access_filter(payload: ChatRequest) -> models.Filter:
    visibility_conditions = [
        models.FieldCondition(
            key="visibility",
            match=models.MatchValue(value="employee"),
        )
    ]
    if payload.department_id:
        visibility_conditions.append(
            models.Filter(
                must=[
                    models.FieldCondition(
                        key="visibility",
                        match=models.MatchValue(value="department"),
                    ),
                    models.FieldCondition(
                        key="department_id",
                        match=models.MatchValue(value=payload.department_id),
                    ),
                ]
            )
        )
    scopes = set(payload.group_scopes)
    if "hr" in scopes:
        visibility_conditions.extend(
            [
                models.FieldCondition(
                    key="visibility", match=models.MatchValue(value="manager")
                ),
                models.FieldCondition(
                    key="visibility", match=models.MatchValue(value="hr")
                ),
            ]
        )
    elif "manager" in scopes:
        manager_scope = models.Filter(
            must=[
                models.FieldCondition(
                    key="visibility", match=models.MatchValue(value="manager")
                )
            ]
        )
        if payload.department_id:
            manager_scope.should = [
                models.FieldCondition(
                    key="department_id",
                    match=models.MatchValue(value=payload.department_id),
                ),
                models.IsNullCondition(
                    is_null=models.PayloadField(key="department_id")
                ),
            ]
        visibility_conditions.append(manager_scope)
    return models.Filter(
        must=[
            models.FieldCondition(
                key="company_id",
                match=models.MatchValue(value=payload.company_id),
            )
        ],
        should=visibility_conditions,
    )


def is_payload_authorized(point_payload: dict, request_payload: ChatRequest) -> bool:
    if point_payload.get("company_id") != request_payload.company_id:
        return False
    visibility = point_payload.get("visibility")
    department_id = point_payload.get("department_id")
    scopes = set(request_payload.group_scopes)
    if visibility == "employee":
        return True
    if visibility == "department":
        return bool(
            request_payload.department_id
            and department_id == request_payload.department_id
        )
    if visibility == "manager":
        return "hr" in scopes or bool(
            "manager" in scopes
            and (department_id is None or department_id == request_payload.department_id)
        )
    return visibility == "hr" and "hr" in scopes


async def enforce_rate_limit(payload: ChatRequest, settings: Settings, redis_client) -> None:
    minute = int(time.time() // 60)
    key = "onboarding:rate:%s:%s:%s" % (payload.company_id, payload.user_id, minute)
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, 60)
    if count > settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )


async def cache_key(payload: ChatRequest, settings: Settings, redis_client) -> str:
    normalized_question = " ".join(payload.question.lower().split())
    question_hash = hashlib.sha256(normalized_question.encode("utf-8")).hexdigest()
    cache_context = "%s|%s|%s|%s" % (
        ",".join(sorted(set(payload.group_scopes))),
        settings.llm_provider,
        settings.embedding_model,
        settings.rag_min_score,
    )
    scope_hash = hashlib.sha256(cache_context.encode("utf-8")).hexdigest()[:16]
    version = await redis_client.get(
        "onboarding:documents:version:%s" % payload.company_id
    ) or "0"
    return "onboarding:cache:%s:%s:%s:%s:%s" % (
        payload.company_id,
        payload.department_id or 0,
        scope_hash,
        version,
        question_hash,
    )


async def retrieve_chunks(payload: ChatRequest, settings: Settings, qdrant_client):
    vector = (await embed_texts([payload.question], settings))[0]
    try:
        result = await qdrant_client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            query_filter=build_access_filter(payload),
            limit=settings.rag_top_k,
            score_threshold=settings.rag_min_score,
            with_payload=True,
        )
    except Exception as error:
        if "not found" in str(error).lower() or "doesn't exist" in str(error).lower():
            return []
        raise
    points = [
        point
        for point in result.points
        if is_payload_authorized(point.payload or {}, payload)
    ]
    if settings.llm_provider == "extractive":
        question_tokens = {
            token
            for token in TOKEN_PATTERN.findall(payload.question.lower())
            if token not in STOP_WORDS and len(token) > 2
        }
        points = [
            point
            for point in points
            if question_tokens
            & {
                token
                for token in TOKEN_PATTERN.findall(
                    str((point.payload or {}).get("text") or "").lower()
                )
                if token not in STOP_WORDS and len(token) > 2
            }
        ]
    return points


def build_sources(points) -> list[ChatSource]:
    sources = []
    seen = set()
    for point in points:
        payload = point.payload or {}
        key = (payload.get("document_id"), payload.get("chunk_index"))
        if not key[0] or key in seen:
            continue
        seen.add(key)
        sources.append(
            ChatSource(
                document_id=key[0],
                title=payload.get("title") or "Document",
                section=payload.get("section") or "Section",
                score=max(0.0, min(1.0, float(point.score))),
            )
        )
    return sources


async def store_session(payload: ChatRequest, settings: Settings, redis_client) -> None:
    session_key = "onboarding:session:%s:%s" % (
        payload.user_id,
        payload.conversation_id,
    )
    await redis_client.set(
        session_key,
        json.dumps(
            {
                "user_id": payload.user_id,
                "employee_id": payload.employee_id,
                "conversation_id": payload.conversation_id,
                "last_question_hash": hashlib.sha256(
                    payload.question.encode("utf-8")
                ).hexdigest(),
            }
        ),
        ex=settings.session_ttl,
    )


async def answer_chat(payload: ChatRequest, settings: Settings, redis_client, qdrant_client) -> ChatResponse:
    started = time.perf_counter()
    await enforce_rate_limit(payload, settings, redis_client)
    response_cache_key = await cache_key(payload, settings, redis_client)
    cached = await redis_client.get(response_cache_key)
    if cached:
        response = ChatResponse.model_validate_json(cached)
        response.cache_hit = True
        response.latency_ms = max(0, int((time.perf_counter() - started) * 1000))
        await store_session(payload, settings, redis_client)
        return response

    points = await retrieve_chunks(payload, settings, qdrant_client)
    sources = build_sources(points)
    if not sources:
        response = ChatResponse(
            answer=REFUSAL_ANSWER,
            sources=[],
            confidence=0.0,
            latency_ms=int((time.perf_counter() - started) * 1000),
            needs_escalation=True,
        )
    else:
        context_parts = []
        for index, point in enumerate(points, start=1):
            point_payload = point.payload or {}
            context_parts.append(
                "[%s] %s — %s\n%s"
                % (
                    index,
                    point_payload.get("title") or "Document",
                    point_payload.get("section") or "Section",
                    point_payload.get("text") or "",
                )
            )
        context = "\n\n".join(context_parts)
        answer = await generate_grounded_answer(context, payload.question, settings)
        if settings.llm_provider == "extractive":
            answer = "Selon les documents autorises :\n\n" + context
        if not any("[%s]" % index in answer for index in range(1, len(sources) + 1)):
            answer += "\n\nSource : [1]"
        response = ChatResponse(
            answer=answer,
            sources=sources,
            confidence=sources[0].score,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    await redis_client.set(
        response_cache_key,
        response.model_dump_json(),
        ex=settings.cache_ttl,
    )
    await store_session(payload, settings, redis_client)
    return response
