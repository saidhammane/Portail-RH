import json
from pathlib import Path

from evaluation.run_evaluation import run_evaluation


def test_evaluation_dataset_has_at_least_thirty_questions():
    dataset = json.loads(
        (Path(__file__).parents[1] / "evaluation" / "dataset.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(dataset["questions"]) >= 30


def test_evaluation_measures_security_and_quality_metrics():
    metrics = run_evaluation()
    assert metrics["questions"] >= 30
    assert metrics["citation_accuracy"] >= 0.9
    assert metrics["correct_refusal_rate"] >= 0.9
    assert metrics["overall_accuracy"] >= 0.9
    assert metrics["cache_hit_rate"] == 0.5
    assert 0.0 <= metrics["escalation_rate"] <= 1.0
