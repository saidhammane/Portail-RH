import json
import math
import time
from pathlib import Path

from app.providers import STOP_WORDS, TOKEN_PATTERN, hashing_embeddings
from app.rag import is_payload_authorized
from app.schemas import ChatRequest


DATASET_PATH = Path(__file__).with_name("dataset.json")


def _tokens(text):
    return {
        token
        for token in TOKEN_PATTERN.findall(text.lower())
        if token not in STOP_WORDS and len(token) > 2
    }


def _cosine(left, right):
    return sum(a * b for a, b in zip(left, right, strict=True))


def _document_chunks(document):
    return [
        {
            **document,
            "text": sentence.strip() + ".",
            "chunk_index": index,
        }
        for index, sentence in enumerate(document["text"].split("."))
        if sentence.strip()
    ]


def run_evaluation(dataset_path=DATASET_PATH):
    dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    chunks = [
        chunk
        for document in dataset["documents"]
        for chunk in _document_chunks(document)
    ]
    chunk_vectors = hashing_embeddings([chunk["text"] for chunk in chunks])
    cache = {}
    latencies = []
    first_pass_results = []
    cache_hits = 0

    for pass_index in range(2):
        for item in dataset["questions"]:
            started = time.perf_counter()
            cache_key = (
                item["company_id"],
                item["department_id"],
                tuple(sorted(item["scopes"])),
                " ".join(item["question"].lower().split()),
            )
            if cache_key in cache:
                result = cache[cache_key]
                cache_hits += 1
            else:
                request = ChatRequest(
                    user_id=1,
                    employee_id=1,
                    company_id=item["company_id"],
                    department_id=item["department_id"],
                    group_scopes=item["scopes"],
                    question=item["question"],
                    conversation_id=1,
                )
                question_tokens = _tokens(item["question"])
                question_vector = hashing_embeddings([item["question"]])[0]
                candidates = []
                for chunk, vector in zip(chunks, chunk_vectors, strict=True):
                    if not is_payload_authorized(chunk, request):
                        continue
                    if not question_tokens & _tokens(chunk["text"]):
                        continue
                    candidates.append((_cosine(question_vector, vector), chunk))
                candidates.sort(key=lambda candidate: candidate[0], reverse=True)
                best = candidates[0] if candidates and candidates[0][0] >= 0.08 else None
                result = {
                    "document_id": best[1]["document_id"] if best else None,
                    "cited": bool(best),
                    "escalated": not bool(best),
                }
                cache[cache_key] = result
            latencies.append((time.perf_counter() - started) * 1000)
            if pass_index == 0:
                first_pass_results.append((item, result))

    answered = [pair for pair in first_pass_results if pair[0]["expected_document_id"]]
    refusals = [pair for pair in first_pass_results if pair[0]["expected_document_id"] is None]
    correct_citations = sum(
        result["cited"]
        and result["document_id"] == item["expected_document_id"]
        for item, result in answered
    )
    correct_refusals = sum(result["document_id"] is None for _item, result in refusals)
    correct_total = correct_citations + correct_refusals
    sorted_latencies = sorted(latencies)
    p95_index = max(0, math.ceil(len(sorted_latencies) * 0.95) - 1)
    return {
        "questions": len(dataset["questions"]),
        "citation_accuracy": round(correct_citations / len(answered), 4),
        "correct_refusal_rate": round(correct_refusals / len(refusals), 4),
        "overall_accuracy": round(correct_total / len(first_pass_results), 4),
        "average_latency_ms": round(sum(latencies) / len(latencies), 3),
        "p95_latency_ms": round(sorted_latencies[p95_index], 3),
        "cache_hit_rate": round(cache_hits / (len(dataset["questions"]) * 2), 4),
        "escalation_rate": round(
            sum(result["escalated"] for _item, result in first_pass_results)
            / len(first_pass_results),
            4,
        ),
    }


if __name__ == "__main__":
    print(json.dumps(run_evaluation(), indent=2, sort_keys=True))
