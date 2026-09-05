import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.providers import embed_texts
from app.rag import (
    REFUSAL_ANSWER,
    add_requested_contact_details,
    add_requested_product_names,
    answer_chat,
    build_access_filter,
    build_relevant_excerpt,
    clean_generated_answer,
    is_follow_up_question,
    is_smalltalk_question,
    meaningful_question_tokens,
    resolve_generation_question,
)
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


def test_smalltalk_is_generated_without_document_sources():
    redis = FakeRedis()
    qdrant = FakeQdrant([])
    payload = request_payload(question="hello")
    generated = AsyncMock(return_value="Bonjour ! Comment puis-je vous aider ?")
    with patch("app.rag.generate_smalltalk_answer", generated):
        response = asyncio.run(
            answer_chat(
                payload,
                settings(
                    llm_provider="ollama",
                    llm_api_url="http://ollama:11434",
                    llm_chat_model="qwen2.5:0.5b",
                ),
                redis,
                qdrant,
            )
        )
    assert is_smalltalk_question("hello")
    assert response.answer == "Bonjour ! Comment puis-je vous aider ?"
    assert response.smalltalk
    assert not response.needs_escalation
    assert response.sources == []
    assert qdrant.calls == 0


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


def test_ollama_generation_can_keep_the_existing_hashing_index():
    configured = settings(
        llm_provider="ollama",
        llm_api_url="http://ollama:11434",
        llm_chat_model="qwen2.5:1.5b",
        embedding_model="hashing-128",
    )
    vectors = asyncio.run(embed_texts(["Produits Bravico"], configured))
    assert len(vectors) == 1
    assert len(vectors[0]) == 128


def test_generative_answer_resolves_short_follow_up_without_trusting_old_answer():
    configured = settings(
        llm_provider="ollama",
        llm_api_url="http://ollama:11434",
        llm_chat_model="qwen2.5:1.5b",
        embedding_model="hashing-128",
    )
    payload = request_payload(
        question="Et le vendredi ?",
        history=[
            {"role": "user", "content": "Quels sont les horaires ?"},
            {"role": "assistant", "content": "De 09:00 a 18:00 [1]."},
        ],
    )
    generated = AsyncMock(return_value="Le vendredi suit le meme horaire [1].")
    with patch("app.rag.generate_grounded_answer", generated):
        response = asyncio.run(
            answer_chat(payload, configured, FakeRedis(), FakeQdrant([source_point()]))
        )
    assert "[1]" in response.answer
    assert generated.await_args.args[1].startswith(
        "Question precedente: Quels sont les horaires ?"
    )
    assert generated.await_args.kwargs["history"] == []


def test_generative_refusal_is_escalated_without_sources():
    configured = settings(
        llm_provider="ollama",
        llm_api_url="http://ollama:11434",
        llm_chat_model="qwen2.5:1.5b",
        embedding_model="hashing-128",
    )
    generated = AsyncMock(
        return_value="Information insuffisante dans les documents autorises."
    )
    with patch("app.rag.generate_grounded_answer", generated):
        response = asyncio.run(
            answer_chat(
                request_payload(), configured, FakeRedis(), FakeQdrant([source_point()])
            )
        )
    assert response.answer == REFUSAL_ANSWER
    assert response.sources == []
    assert response.needs_escalation


def test_requested_contact_details_are_recovered_from_authorized_source():
    point = source_point()
    point.payload["text"] = (
        "Ouvrez Bravico VPN et utilisez le MFA. "
        "En cas de probleme, contactez support@bravico.ma ou le poste 207."
    )
    answer = add_requested_contact_details(
        "Ouvrez Bravico VPN et utilisez le MFA [1].",
        [point],
        "Comment utiliser le VPN et contacter le support IT ?",
    )
    assert "support@bravico.ma" in answer
    assert "poste 207" in answer
    assert "[1]" in answer


def test_requested_product_names_are_recovered_from_authorized_source():
    point = source_point()
    point.payload["text"] = (
        "PRODUITS ET SERVICES BRAVICO Bravico Pilotage aide les managers. "
        "EFacture Express simplifie les factures electroniques."
    )
    answer = add_requested_product_names(
        "Bravico fournit des logiciels aux PME [1].",
        [point],
        "Que fait Bravico et quels sont ses produits ?",
    )
    assert "Bravico Pilotage" in answer
    assert "EFacture Express" in answer
    assert "[1]" in answer


def test_cache_is_conversation_aware_for_follow_up_questions():
    redis = FakeRedis()
    qdrant = FakeQdrant([source_point()])
    first = request_payload(
        question="Et le vendredi ?",
        history=[{"role": "user", "content": "Parlons des horaires."}]
    )
    second = request_payload(
        question="Et le vendredi ?",
        history=[{"role": "user", "content": "Parlons des avantages."}]
    )
    asyncio.run(answer_chat(first, settings(), redis, qdrant))
    asyncio.run(answer_chat(second, settings(), redis, qdrant))
    assert qdrant.calls == 2


def test_only_an_explicit_reference_is_treated_as_a_follow_up():
    assert is_follow_up_question("Et lequel concerne la facturation ?")
    assert is_follow_up_question("Cela concerne quel produit ?")
    assert not is_follow_up_question("Que fait Bravico et quels sont ses produits ?")


def test_possessive_pronouns_do_not_block_product_retrieval():
    tokens = meaningful_question_tokens(
        "Que fait Bravico et quels sont ses produits ?"
    )
    assert "ses" not in tokens
    assert {"produit", "produits", "logiciel", "logiciels"} <= tokens


def test_follow_up_pronoun_is_resolved_from_the_previous_user_question():
    payload = request_payload(
        question="Et lequel concerne la facturation electronique ?",
        history=[
            {"role": "user", "content": "Quels sont les produits Bravico ?"},
            {"role": "assistant", "content": "Une ancienne reponse non fiable."},
        ],
    )
    assert resolve_generation_question(payload) == (
        "quel produit concerne la facturation electronique ?"
    )


def test_relevant_excerpt_prioritizes_the_named_fact_over_an_orphan_reference():
    text = (
        "Bravico Pilotage aide les managers. "
        "EFacture Express prepare les factures electroniques. "
        "Le produit accompagne les PME pour la facturation electronique."
    )
    excerpt = build_relevant_excerpt(
        text, "Quel produit concerne la facturation electronique ?"
    )
    assert excerpt.startswith("EFacture Express")


def test_generated_answer_drops_an_unfinished_second_sentence():
    assert clean_generated_answer("Reponse complete. Debut coupe") == "Reponse complete."
    assert clean_generated_answer(
        "Horaires : - 09:00 a 18:00 - fragment coupe"
    ) == "Horaires : - 09:00 a 18:00"
