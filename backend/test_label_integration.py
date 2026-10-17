"""Ingestion and API regressions with an isolated metadata store and fake search."""
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
import ingestor
import label_store
import main


@pytest.fixture
def search(tmp_path, monkeypatch):
    monkeypatch.setenv("LABEL_DB_PATH", str(tmp_path / "labels.sqlite3"))
    monkeypatch.setenv("LAYA_MODE", "off")
    monkeypatch.setattr(main, "SOURCE_DIR", tmp_path)
    monkeypatch.setattr(main, "start_watcher", lambda *args: Mock())
    monkeypatch.setattr(main, "ingest_all", lambda *args: 0)
    index = Mock()
    index.get_document.return_value = {"id": "prompt", "type": "image_prompt", "is_xx": False, "is_xxx": False}
    index.update_documents.return_value = SimpleNamespace(task_uid=1)
    index.delete_document.return_value = SimpleNamespace(task_uid=1)
    index.add_documents.return_value = SimpleNamespace(task_uid=1)
    client = Mock()
    client.get_index.return_value = index
    client.wait_for_task.return_value = SimpleNamespace(status="succeeded")
    monkeypatch.setattr(main, "get_client", lambda: client)
    monkeypatch.setattr(main, "setup_index", lambda _: index)
    monkeypatch.setattr(ingestor, "setup_index", lambda _: index)
    return client, index


def test_patch_preserves_api_and_null_resets_override(search):
    with TestClient(main.app) as api:
        response = api.patch("/conversation/prompt/xx", json={"is_xx": True})
        assert response.status_code == 200
        assert response.json()["is_xx"] is True
        assert api.patch("/conversation/prompt/xx", json={"is_xx": False}).json()["is_xx"] is False
        assert api.patch("/conversation/prompt/xx", json={"is_xx": None}).status_code == 200
        assert label_store.read("prompt")["manual"]["is_xx"] is None
        for invalid in ({}, {"is_xx": "false"}, {"is_xx": 1}):
            assert api.patch("/conversation/prompt/xx", json=invalid).status_code == 422


def test_failed_projection_is_saved_and_visible_on_detail(search):
    client, index = search
    client.wait_for_task.return_value = SimpleNamespace(status="failed")
    with TestClient(main.app) as api:
        response = api.patch("/conversation/prompt/xxx", json={"is_xxx": True})
        assert response.status_code == 503
        detail = api.get("/conversation/prompt").json()
        assert detail["is_xxx"] is True
        assert detail["label_analysis"]["projection_pending"] is True
    assert label_store.read("prompt")["manual"]["is_xxx"] is True


def test_successful_delete_removes_metadata(search):
    label_store.seed({"id": "prompt", "is_xx": True})
    with TestClient(main.app) as api:
        assert api.delete("/conversation/prompt").status_code == 200
    assert label_store.read("prompt") is None


def test_preservation_uses_every_id_and_keeps_custom_tags(search, monkeypatch):
    client, index = search
    documents = [{"id": str(i), "type": "image_prompt", "all_user_prompts": "portrait",
                  "detected_categories": {"style": ["portrait"]}} for i in range(1005)]
    monkeypatch.setattr(ingestor, "parse_user_prompts_file", lambda _: documents)
    monkeypatch.setattr(ingestor, "classify_document", lambda doc: doc)
    requested = []
    def get_documents(params):
        ids = json.loads(params["filter"].split(" IN ", 1)[1])
        requested.extend(ids)
        return SimpleNamespace(results=[{"id": key, "is_xx": key == "1004", "custom_tags": ["kept"],
                                         "is_favorite": True} for key in ids])
    index.get_documents.side_effect = get_documents
    assert ingestor.ingest_file("user-prompts.json", client) == 1005
    assert requested == [str(i) for i in range(1005)]
    last = index.add_documents.call_args.args[0][-1]
    assert last["is_xx"] and last["is_favorite"]
    assert last["tags"] == ["portrait", "kept"]
    assert label_store.read("1004")["manual"]["is_xx"] is True


def test_override_during_inference_wins(search, monkeypatch):
    client, index = search
    monkeypatch.setattr(ingestor, "parse_user_prompts_file", lambda _: [
        {"id": "prompt", "type": "image_prompt", "all_user_prompts": "portrait"}])
    monkeypatch.setattr(ingestor, "classify_document", lambda doc: doc)
    index.get_documents.return_value = SimpleNamespace(results=[])
    monkeypatch.setattr(ingestor, "classify_labels", lambda doc: label_store.set_override(doc["id"], "is_xx", False))
    ingestor.ingest_file("user-prompts.json", client)
    assert index.add_documents.call_args.args[0][0]["is_xx"] is False


def test_concurrent_custom_creation_preserves_both_prompts(search, monkeypatch, tmp_path):
    monkeypatch.setattr(main, "ingest_file", lambda *args: 0)
    bodies = [main.CustomPromptRequest(prompt=f"Portrait {i}") for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        created = list(pool.map(main.create_custom_prompt, bodies))
    saved = json.loads((tmp_path / "user-prompts.json").read_text())
    assert len(saved) == 2
    assert {doc["id"] for doc in saved} == {doc["id"] for doc in created}


def test_console_reports_inference_cache_and_manual_override(search, monkeypatch, caplog):
    import laya_classifier
    monkeypatch.setenv("LAYA_MODE", "apply")
    monkeypatch.setenv("LAYA_LABEL_THRESHOLD", "0.9")
    monkeypatch.setattr(laya_classifier, "evaluate", Mock(return_value={"is_xx": 0.98, "is_xxx": 0.01}))
    doc = {"id": "console-test", "type": "image_prompt", "all_user_prompts": "Private prompt text"}
    label_store.seed(doc)
    label_store.set_override(doc["id"], "is_xx", False)
    with caplog.at_level("INFO", logger="laya_classifier"):
        laya_classifier.classify(doc)
        laya_classifier.classify(doc)
    assert "source=inference" in caplog.text and "source=cache" in caplog.text
    assert "XX=True score=0.9800" in caplog.text
    assert "effective_XX=False" in caplog.text
    assert "Private prompt text" not in caplog.text
