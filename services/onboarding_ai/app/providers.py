import hashlib
import math
import re

import httpx

from .config import Settings


TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
HASHING_DIMENSION = 128
STOP_WORDS = {
    "a", "au", "aux", "avec", "ce", "ces", "dans", "de", "des", "du", "en",
    "et", "est", "la", "le", "les", "ou", "par", "pour", "que", "qui", "sur",
    "un", "une", "the", "a", "an", "and", "in", "is", "of", "on", "to",
}


def hashing_embeddings(texts: list[str], dimension: int = HASHING_DIMENSION) -> list[list[float]]:
    vectors = []
    for text in texts:
        vector = [0.0] * dimension
        for token in TOKEN_PATTERN.findall(text.lower()):
            if token in STOP_WORDS:
                continue
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % dimension
            vector[bucket] += 1.0 if digest[4] & 1 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        vectors.append([value / norm for value in vector])
    return vectors


def _provider_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1") and path.startswith("/v1/"):
        return base + path[3:]
    return base + path


async def embed_texts(texts: list[str], settings: Settings) -> list[list[float]]:
    if settings.llm_provider == "extractive":
        return hashing_embeddings(texts)

    timeout = httpx.Timeout(60.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        if settings.llm_provider == "ollama":
            response = await client.post(
                _provider_url(settings.llm_api_url, "/api/embed"),
                json={"model": settings.embedding_model, "input": texts},
            )
            response.raise_for_status()
            return response.json()["embeddings"]

        response = await client.post(
            _provider_url(settings.llm_api_url, "/v1/embeddings"),
            headers={
                "Authorization": "Bearer %s"
                % settings.llm_api_key.get_secret_value(),
            },
            json={"model": settings.embedding_model, "input": texts},
        )
        response.raise_for_status()
        return [item["embedding"] for item in response.json()["data"]]


async def generate_grounded_answer(context: str, question: str, settings: Settings) -> str:
    if settings.llm_provider == "extractive":
        return context

    system_prompt = (
        "Tu es un assistant d'integration RH. Reponds uniquement avec les faits du "
        "CONTEXTE. Cite chaque affirmation avec [n]. Si le contexte est insuffisant, "
        "reponds exactement: Information insuffisante dans les documents autorises."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "CONTEXTE:\n%s\n\nQUESTION:\n%s" % (context, question)},
    ]
    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
        if settings.llm_provider == "ollama":
            response = await client.post(
                _provider_url(settings.llm_api_url, "/api/chat"),
                json={"model": settings.llm_chat_model, "messages": messages, "stream": False},
            )
            response.raise_for_status()
            return response.json()["message"]["content"].strip()
        response = await client.post(
            _provider_url(settings.llm_api_url, "/v1/chat/completions"),
            headers={
                "Authorization": "Bearer %s" % settings.llm_api_key.get_secret_value(),
            },
            json={
                "model": settings.llm_chat_model,
                "messages": messages,
                "temperature": 0,
            },
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
