import hashlib
import json
import re
import time

from fastapi import HTTPException, status
from qdrant_client import models

from .config import Settings
from .providers import (
    STOP_WORDS,
    TOKEN_PATTERN,
    embed_texts,
    generate_grounded_answer,
    generate_smalltalk_answer,
)
from .schemas import ChatRequest, ChatResponse, ChatSource


CACHE_VERSION = "rag-v5"
CONTACT_QUERY_TOKENS = {
    "contact",
    "contacter",
    "email",
    "mail",
    "poste",
    "support",
    "telephone",
    "téléphone",
}
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
EXTENSION_PATTERN = re.compile(r"\bposte\s+\d{2,6}\b", re.I)
PRODUCT_QUERY_TOKENS = {"logiciel", "logiciels", "produit", "produits"}
PRODUCT_NAME_TOKEN = r"[A-ZÉÈÀ][A-Za-zÀ-ÿ0-9]*[a-zà-ÿ][A-Za-zÀ-ÿ0-9]*"
PRODUCT_NAME_PATTERN = re.compile(
    r"\b(%s(?:\s+%s){1,3})\s+(?:aide|automatise|offre|permet|simplifie)\b"
    % (PRODUCT_NAME_TOKEN, PRODUCT_NAME_TOKEN)
)
REFUSAL_ANSWER = (
    "Je n'ai pas trouve d'information verifiee sur ce sujet dans les documents "
    "auxquels vous avez acces. Reformulez la question ou transmettez-la a RH."
)
GENERIC_QUERY_TOKENS = {
    "avoir",
    "comment",
    "deux",
    "faire",
    "jour",
    "jours",
    "mes",
    "mon",
    "ma",
    "notre",
    "nos",
    "possible",
    "puis",
    "quelle",
    "quels",
    "semaine",
    "sont",
    "travail",
    "bravico",
    "fait",
    "elle",
    "elles",
    "il",
    "ils",
    "lui",
    "leur",
    "leurs",
    "sa",
    "ses",
    "son",
    "vos",
    "votre",
    "lequel",
    "laquelle",
}
SYNONYM_GROUPS = (
    {"distance", "remote", "teletravail", "vpn"},
    {"absence", "conge", "conges", "leave", "vacances"},
    {"heure", "heures", "horaire", "horaires", "schedule", "working"},
    {"avantage", "avantages", "benefit", "benefits", "assurance"},
    {"attestation", "certificate", "certificat", "salaire"},
    {"informatique", "it", "support", "ordinateur", "laptop"},
    {"facture", "factures", "facturation", "electronique", "electroniques"},
    {"logiciel", "logiciels", "produit", "produits", "service", "services"},
)
FOLLOW_UP_PREFIXES = ("et ", "mais ", "sinon ", "aussi ")
FOLLOW_UP_REFERENCES = {
    "cela",
    "ca",
    "ça",
    "celui",
    "celle",
    "ceux",
    "celles",
    "precedent",
    "précédent",
}
SMALLTALK_PATTERN = re.compile(
    r"^\s*(?:hello|hi|hey|bonjour|bonsoir|salut|coucou|merci|thanks)[\s!?.]*$",
    re.I,
)


def meaningful_question_tokens(question: str) -> set[str]:
    tokens = {
        token
        for token in TOKEN_PATTERN.findall(question.lower())
        if token not in STOP_WORDS
        and token not in GENERIC_QUERY_TOKENS
        and len(token) > 2
    }
    for synonym_group in SYNONYM_GROUPS:
        if tokens & synonym_group:
            tokens |= synonym_group
    return tokens


def is_follow_up_question(question: str) -> bool:
    normalized = " ".join(question.lower().split())
    raw_tokens = set(TOKEN_PATTERN.findall(normalized))
    return normalized.startswith(FOLLOW_UP_PREFIXES) or bool(
        raw_tokens & FOLLOW_UP_REFERENCES
    )


def is_smalltalk_question(question: str) -> bool:
    return bool(SMALLTALK_PATTERN.fullmatch(question))


def resolve_generation_question(payload: ChatRequest) -> str:
    """Turn a short conversational reference into a clear model question."""
    if not is_follow_up_question(payload.question):
        return payload.question
    question = re.sub(
        r"^(?:et|mais|sinon|aussi)\s+", "", payload.question.strip(), flags=re.I
    )
    previous_questions = [
        message.content for message in payload.history if message.role == "user"
    ]
    previous = previous_questions[-1] if previous_questions else ""
    previous_tokens = meaningful_question_tokens(previous)
    reference_noun = "element"
    for candidates, noun in (
        ({"produit", "produits"}, "produit"),
        ({"contact", "contacts"}, "contact"),
        ({"avantage", "avantages"}, "avantage"),
        ({"document", "documents"}, "document"),
    ):
        if previous_tokens & candidates:
            reference_noun = noun
            break
    question = re.sub(r"\blequel\b", "quel %s" % reference_noun, question, flags=re.I)
    question = re.sub(
        r"\blaquelle\b", "quelle %s" % reference_noun, question, flags=re.I
    )
    if len(meaningful_question_tokens(question)) <= 1 and previous:
        return "Question precedente: %s\nQuestion actuelle: %s" % (
            previous[:400],
            question,
        )
    return question


def build_extractive_answer(points, question: str) -> str:
    """Return a short, readable answer while keeping each statement cited."""
    question_tokens = meaningful_question_tokens(question)
    asks_for_hours = bool(
        question_tokens & {"heure", "heures", "horaire", "horaires", "schedule", "working"}
    )
    statements = []
    for source_index, point in enumerate(points, start=1):
        text = str((point.payload or {}).get("text") or "").strip()
        sentences = [
            sentence.strip(" -\t")
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", text)
            if len(sentence.strip()) >= 20
        ]
        ranked = sorted(
            sentences,
            key=lambda sentence: (
                len(
                    question_tokens
                    & {
                        token
                        for token in TOKEN_PATTERN.findall(sentence.lower())
                        if token not in STOP_WORDS and len(token) > 2
                    }
                )
                + (2 if asks_for_hours and re.search(r"\b\d{1,2}[:h]\d{2}\b", sentence) else 0)
            ),
            reverse=True,
        )
        best_overlap = (
            len(
                question_tokens
                & {
                    token
                    for token in TOKEN_PATTERN.findall(ranked[0].lower())
                    if token not in STOP_WORDS and len(token) > 2
                }
            )
            if ranked
            else 0
        )
        if ranked and best_overlap:
            statements.append("%s [%s]" % (ranked[0][:500], source_index))
        if len(statements) == 3:
            break
    return "Voici ce que disent les documents internes :\n\n" + "\n\n".join(
        "- " + statement for statement in statements
    )


def build_relevant_excerpt(text: str, question: str, limit: int = 420) -> str:
    """Keep the sentences most relevant to the question inside the model context."""
    clean_text = str(text or "").strip()
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", clean_text)
        if sentence.strip()
    ]
    question_tokens = meaningful_question_tokens(question)

    def overlap(sentence):
        sentence_tokens = {
            token
            for token in TOKEN_PATTERN.findall(sentence.lower())
            if token not in STOP_WORDS and len(token) > 2
        }
        score = len(question_tokens & sentence_tokens)
        if re.match(r"^(?:le produit|il|elle|cela|ca|Ã§a)\b", sentence.lower()):
            score -= 2
        return score

    ranked = sorted(enumerate(sentences), key=lambda item: (-overlap(item[1]), item[0]))
    selected = []
    size = 0
    for _, sentence in ranked:
        if selected and size + len(sentence) + 1 > limit:
            continue
        selected.append(sentence)
        size += len(sentence) + 1
        if size >= limit:
            break
    return " ".join(selected)[:limit] or clean_text[:limit]


def clean_generated_answer(answer: str) -> str:
    """Keep the compact model's response complete when it starts a second sentence."""
    clean_answer = " ".join(str(answer or "").split())
    list_parts = clean_answer.split(" - ")
    if len(list_parts) > 1 and not re.search(r"[.!?]$", list_parts[-1]):
        clean_answer = " - ".join(list_parts[:-1]).rstrip(" ,;:-")
    sentences = re.split(r"(?<=[.!?])\s+", clean_answer)
    if len(sentences) > 1:
        return sentences[0]
    return clean_answer


def add_requested_contact_details(answer: str, points, question: str) -> str:
    """Append exact contact details when the compact model omits a requested value."""
    question_tokens = set(TOKEN_PATTERN.findall(question.lower()))
    if not question_tokens & CONTACT_QUERY_TOKENS:
        return answer
    if EMAIL_PATTERN.search(answer) or EXTENSION_PATTERN.search(answer):
        return answer
    for source_index, point in enumerate(points, start=1):
        text = str((point.payload or {}).get("text") or "")
        details = []
        for value in EMAIL_PATTERN.findall(text) + EXTENSION_PATTERN.findall(text):
            if value.lower() not in {item.lower() for item in details}:
                details.append(value)
        if details:
            base_answer = answer.rstrip().rstrip(".")
            return "%s. Contact : %s [%s]." % (
                base_answer,
                " ou ".join(details),
                source_index,
            )
    return answer


def add_requested_product_names(answer: str, points, question: str) -> str:
    """Append product names parsed from authorized sources when the model omits them."""
    question_tokens = set(TOKEN_PATTERN.findall(question.lower()))
    if not question_tokens & PRODUCT_QUERY_TOKENS:
        return answer
    products = []
    citations = []
    for source_index, point in enumerate(points, start=1):
        text = str((point.payload or {}).get("text") or "")
        for product in PRODUCT_NAME_PATTERN.findall(text):
            if product.lower() not in {item.lower() for item in products}:
                products.append(product)
                citations.append(source_index)
    missing = [product for product in products if product.lower() not in answer.lower()]
    if not missing:
        return answer
    source_index = citations[products.index(missing[0])]
    base_answer = answer.rstrip().rstrip(".")
    return "%s. Produits : %s [%s]." % (
        base_answer,
        " et ".join(products),
        source_index,
    )


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
    relevant_history = (
        payload.history[-6:] if is_follow_up_question(payload.question) else []
    )
    normalized_history = "|".join(
        "%s:%s" % (message.role, " ".join(message.content.lower().split()))
        for message in relevant_history
    )
    question_hash = hashlib.sha256(
        (normalized_history + "|" + normalized_question).encode("utf-8")
    ).hexdigest()
    cache_context = "%s|%s|%s|%s|%s|%s" % (
        CACHE_VERSION,
        ",".join(sorted(set(payload.group_scopes))),
        settings.llm_provider,
        settings.llm_chat_model or "",
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
    retrieval_question = resolve_generation_question(payload)
    vector = (await embed_texts([retrieval_question], settings))[0]
    uses_hashing_index = settings.embedding_model.startswith("hashing-")
    try:
        result = await qdrant_client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            query_filter=build_access_filter(payload),
            # Hashing vectors are intentionally lightweight and can rank lexical
            # collisions highly. Fetch a wider candidate set, then apply the exact
            # token-overlap guard below before giving anything to the model.
            limit=max(20, settings.rag_top_k * 5) if uses_hashing_index else settings.rag_top_k,
            score_threshold=None if uses_hashing_index else settings.rag_min_score,
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
    if uses_hashing_index:
        retrieval_tokens = meaningful_question_tokens(retrieval_question)
        raw_retrieval_tokens = {
            token
            for token in TOKEN_PATTERN.findall(retrieval_question.lower())
            if token not in STOP_WORDS
            and token not in GENERIC_QUERY_TOKENS
            and len(token) > 2
        }

        def overlap_count(point):
            point_tokens = {
                token
                for token in TOKEN_PATTERN.findall(
                    str((point.payload or {}).get("text") or "").lower()
                )
                if token not in STOP_WORDS and len(token) > 2
            }
            return len(retrieval_tokens & point_tokens)

        matches_known_topic = any(
            raw_retrieval_tokens & synonym_group
            for synonym_group in SYNONYM_GROUPS
        )
        minimum_overlap = (
            1 if matches_known_topic or len(raw_retrieval_tokens) < 2 else 2
        )
        points = [
            point for point in points if overlap_count(point) >= minimum_overlap
        ]
        points.sort(key=lambda point: (overlap_count(point), point.score), reverse=True)
        points = points[: settings.rag_top_k]
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

    if is_smalltalk_question(payload.question):
        answer = await generate_smalltalk_answer(payload.question, settings)
        answer = " ".join(str(answer or "").split())
        response = ChatResponse(
            answer=answer,
            sources=[],
            confidence=1.0,
            latency_ms=int((time.perf_counter() - started) * 1000),
            needs_escalation=False,
            smalltalk=True,
        )
        await redis_client.set(
            response_cache_key,
            response.model_dump_json(),
            ex=settings.cache_ttl,
        )
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
        generation_question = resolve_generation_question(payload)
        context_parts = []
        for index, point in enumerate(points, start=1):
            point_payload = point.payload or {}
            context_parts.append(
                "[%s] %s — %s\n%s"
                % (
                    index,
                    point_payload.get("title") or "Document",
                    point_payload.get("section") or "Section",
                    build_relevant_excerpt(
                        point_payload.get("text") or "", generation_question
                    ),
                )
            )
        context = "\n\n".join(context_parts)
        answer = await generate_grounded_answer(
            context, generation_question, settings, history=[]
        )
        if settings.llm_provider == "extractive":
            answer = build_extractive_answer(points, payload.question)
        else:
            answer = clean_generated_answer(answer)
        answer = add_requested_contact_details(answer, points, generation_question)
        answer = add_requested_product_names(answer, points, generation_question)
        refused = answer.strip().lower().startswith("information insuffisante")
        if not refused and not any(
            "[%s]" % index in answer for index in range(1, len(sources) + 1)
        ):
            answer += "\n\nSource : [1]"
        response = ChatResponse(
            answer=REFUSAL_ANSWER if refused else answer,
            sources=[] if refused else sources,
            confidence=0.0 if refused else sources[0].score,
            latency_ms=int((time.perf_counter() - started) * 1000),
            needs_escalation=refused,
        )

    await redis_client.set(
        response_cache_key,
        response.model_dump_json(),
        ex=settings.cache_ttl,
    )
    await store_session(payload, settings, redis_client)
    return response
