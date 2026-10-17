"""Classifier contract tests: no checkpoint downloads or external services required."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import label_store
import laya_classifier as classifier


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setenv("LABEL_DB_PATH", str(tmp_path / "labels.sqlite3"))
    monkeypatch.setenv("LAYA_MODE", "review")
    monkeypatch.delenv("LAYA_LABEL_THRESHOLD", raising=False)


def document(text="Portrait with a high slit", **extra):
    return {"id": "prompt", "type": "image_prompt", "all_user_prompts": text, **extra}


def analyze(doc, monkeypatch, scores=None):
    predict = Mock(return_value=scores or {"is_xx": 0.98, "is_xxx": 0.01})
    monkeypatch.setattr(classifier, "evaluate", predict)
    label_store.seed(doc)
    classifier.classify(doc)
    return predict, label_store.project(doc)


def test_review_does_not_change_labels_and_reuses_cache(monkeypatch):
    predict, doc = analyze(document(), monkeypatch)
    assert not doc["is_xx"]
    assert doc["label_analysis"]["suggestions"] == {"is_xx": True, "is_xxx": False}
    classifier.classify(doc)
    assert predict.call_count == 1
    doc["all_user_prompts"] += " with curves"
    classifier.classify(doc)
    assert predict.call_count == 2


def test_apply_requires_explicit_threshold(monkeypatch):
    monkeypatch.setenv("LAYA_MODE", "apply")
    predict, doc = analyze(document(), monkeypatch)
    predict.assert_not_called()
    assert doc["label_analysis"]["status"] == "error"
    assert not doc["is_xx"]


def test_manual_true_false_win_and_reset_restores_automatic(monkeypatch):
    monkeypatch.setenv("LAYA_MODE", "apply")
    monkeypatch.setenv("LAYA_LABEL_THRESHOLD", "0.9")
    _, doc = analyze(document(), monkeypatch)
    assert doc["is_xx"] and not doc["is_xxx"]
    label_store.set_override(doc["id"], "is_xx", False)
    label_store.set_override(doc["id"], "is_xxx", True)
    assert not label_store.project(doc)["is_xx"]
    assert label_store.project(doc)["is_xxx"]
    label_store.set_override(doc["id"], "is_xx", None)
    assert label_store.project(doc)["is_xx"]
    rebuilt = document()
    label_store.seed(rebuilt)
    assert label_store.project(rebuilt)["is_xxx"]


def test_uncertain_label_does_not_clear_existing_value(monkeypatch):
    monkeypatch.setenv("LAYA_MODE", "apply")
    monkeypatch.setenv("LAYA_LABEL_THRESHOLD", "0.9")
    _, doc = analyze(document(), monkeypatch)
    doc["all_user_prompts"] += " changed"
    _, doc = analyze(doc, monkeypatch, {"is_xx": 0.6, "is_xxx": 0.99})
    assert doc["is_xx"] and doc["is_xxx"]
    assert doc["label_analysis"]["status"] == "needs_review"


def test_failure_keeps_last_applied_values_and_marks_stale(monkeypatch):
    monkeypatch.setenv("LAYA_MODE", "apply")
    monkeypatch.setenv("LAYA_LABEL_THRESHOLD", "0.9")
    predict, doc = analyze(document(), monkeypatch)
    doc["all_user_prompts"] = "Changed text"
    predict.side_effect = RuntimeError("do not expose prompt text")
    classifier.classify(doc)
    assert label_store.project(doc)["is_xx"]
    assert doc["label_analysis"]["stale"]
    assert "expose" not in doc["label_analysis"]["error"]


@pytest.mark.parametrize("value", [True, "0.9", float("nan"), float("inf"), -0.1, 1.1])
def test_malformed_probabilities_are_rejected(monkeypatch, value):
    fake = SimpleNamespace(predict_long=lambda *a, **k: {
        "usage": {"windows": 1}, "answers": {"is_xx": {"noul": value}, "is_xxx": {"noul": 0.1}}})
    monkeypatch.setattr(classifier, "agent", lambda *a: fake)
    with pytest.raises(ValueError):
        classifier.evaluate("prompt", classifier.MODEL, classifier.REVISION)


@pytest.mark.parametrize("usage", [{}, {"truncated": 1}, {"state_tokens_dropped": 2}])
def test_truncated_or_unverifiable_input_is_rejected(monkeypatch, usage):
    fake = SimpleNamespace(predict_long=lambda *a, **k: {"usage": usage})
    monkeypatch.setattr(classifier, "agent", lambda *a: fake)
    with pytest.raises(ValueError):
        classifier.evaluate("long prompt", classifier.MODEL, classifier.REVISION)


def test_only_user_turns_are_sent_to_model(monkeypatch):
    predict, _ = analyze(document(turns=[{"speaker": "You", "text": "Create a portrait"},
                                       {"speaker": "Grok", "text": "Refusal mentioning nipples"}]), monkeypatch)
    assert predict.call_args.args[0] == "Create a portrait"


def test_legacy_positives_and_concurrent_overrides_survive():
    doc = document(is_xx=True)
    label_store.seed(doc)
    assert label_store.read(doc["id"])["manual"]["is_xx"] is True
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda field: label_store.set_override(doc["id"], field, False), label_store.FIELDS))
    assert label_store.read(doc["id"])["manual"] == {"is_xx": False, "is_xxx": False}
    label_store.delete(doc["id"])
    assert label_store.read(doc["id"]) is None


def test_evaluation_metrics():
    from evaluate_laya import metrics
    rows = [{"is_xx": True, "is_xxx": False}, {"is_xx": False, "is_xxx": True}]
    predicted = [{"is_xx": True, "is_xxx": True}, {"is_xx": True, "is_xxx": False}]
    report = metrics(rows, predicted)
    assert report["is_xx"]["precision"] == 0.5
    assert report["is_xx"]["recall"] == 1
    assert report["is_xxx"]["false_negative"] == 1


@pytest.mark.parametrize("mode,threshold", [("off", ""), ("apply", "nan"), ("apply", "bad"), ("apply", "0.4")])
def test_disabled_and_invalid_configuration_skip_inference(monkeypatch, mode, threshold):
    monkeypatch.setenv("LAYA_MODE", mode)
    monkeypatch.setenv("LAYA_LABEL_THRESHOLD", threshold)
    predict, doc = analyze(document(), monkeypatch)
    predict.assert_not_called()
    assert doc["label_analysis"]["status"] == ("disabled" if mode == "off" else "error")
