import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.rag import REFUSAL_ANSWER, answer_chat, build_access_filter
from app.schemas import ChatRequest


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    async def expire(self, key, seconds):
        return True

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None, nx=False):
        self.values[key] = value
        return True


class FakeQdrant:
    def __init__(self, points):
        self.points = points
        self.calls = 0
        self.last_filter = None

    async def query_points(self, **kwargs):
        self.calls += 1
        self.last_filter = kwargs["query_filter"]
        return SimpleNamespace(points=self.points)


def request_payload(**values):
    payload = {
        "user_id": 10,
        "employee_id": 20,
        "company_id": 1,
        "department_id": 3,
        "group_scopes": ["employee"],
        "question": "Quels sont les horaires de travail ?",
        "conversation_id": 30,
    }
    payload.update(values)
    return ChatRequest(**payload)


def source_point(visibility="department", department_id=3, company_id=1):
    return SimpleNamespace(
        score=0.82,
        payload={
            "document_id": 42,
            "title": "Guide d'accueil",
            "section": "Chunk 1",
            "chunk_index": 0,
            "text": "Les horaires de travail sont de 09:00 a 18:00.",
            "visibility": visibility,
            "department_id": department_id,
            "company_id": company_id,
        },
    )


def settings(**values):
    return Settings(service_token="x" * 32, **values)


def test_answer_contains_citation_and_cache_is_context_bound():
    redis = FakeRedis()
    qdrant = FakeQdrant([source_point()])
    payload = request_payload()

    first = asyncio.run(answer_chat(payload, settings(), redis, qdrant))
    second = asyncio.run(answer_chat(payload, settings(), redis, qdrant))

    assert first.sources[0].document_id == 42
    assert "[1]" in first.answer
    assert first.confidence == 0.82
    assert not first.cache_hit
    assert second.cache_hit
    assert qdrant.calls == 1
    assert "onboarding:session:10:30" in redis.values


def test_question_without_authorized_source_refuses_and_escalates():
    response = asyncio.run(
        answer_chat(request_payload(), settings(), FakeRedis(), FakeQdrant([]))
    )
    assert response.answer == REFUSAL_ANSWER
    assert response.sources == []
    assert response.needs_escalation
    assert response.confidence == 0.0


def test_extractive_fallback_rejects_vector_hash_collision():
    response = asyncio.run(
        answer_chat(
            request_payload(question="Quel budget pour une navette vers Mars ?"),
            settings(),
            FakeRedis(),
            FakeQdrant([source_point()]),
        )
    )
    assert response.answer == REFUSAL_ANSWER
    assert response.needs_escalation


def test_rate_limit_is_enforced_before_cache():
    redis = FakeRedis()
    qdrant = FakeQdrant([])
    configured = settings(rate_limit_per_minute=1)
    asyncio.run(answer_chat(request_payload(), configured, redis, qdrant))
    with pytest.raises(HTTPException) as error:
        asyncio.run(answer_chat(request_payload(), configured, redis, qdrant))
    assert error.value.status_code == 429


def test_qdrant_filter_contains_company_department_and_visibility_scope():
    employee_filter = build_access_filter(request_payload()).model_dump(
        mode="json", exclude_none=True
    )
    serialized = str(employee_filter)
    assert "company_id" in serialized and "department_id" in serialized
    assert "employee" in serialized and "department" in serialized
    assert "'hr'" not in serialized

    hr_filter = build_access_filter(
        request_payload(group_scopes=["employee", "manager", "hr"])
    ).model_dump(mode="json", exclude_none=True)
    assert "'hr'" in str(hr_filter)


def test_returned_points_are_post_filtered_for_department_company_and_hr_scope():
    forbidden_points = [
        source_point(visibility="department", department_id=99),
        source_point(visibility="employee", company_id=2),
        source_point(visibility="hr", department_id=None),
    ]
    response = asyncio.run(
        answer_chat(
            request_payload(),
            settings(),
            FakeRedis(),
            FakeQdrant(forbidden_points),
        )
    )
    assert response.needs_escalation
    assert response.sources == []


def test_cache_reuse_keeps_user_sessions_isolated():
    redis = FakeRedis()
    qdrant = FakeQdrant([source_point()])
    first = request_payload(user_id=10, employee_id=20, conversation_id=30)
    second = request_payload(user_id=11, employee_id=21, conversation_id=31)
    asyncio.run(answer_chat(first, settings(), redis, qdrant))
    cached = asyncio.run(answer_chat(second, settings(), redis, qdrant))
    assert cached.cache_hit
    assert "onboarding:session:10:30" in redis.values
    assert "onboarding:session:11:31" in redis.values
