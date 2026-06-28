from __future__ import annotations

from src.product_app.agentops.remote_context import build_remote_context_snapshot


def test_remote_context_empty_by_default():
    snapshot = build_remote_context_snapshot()
    assert snapshot.contract_version == "agentops.remote_context.v1"
    assert snapshot.readonly is True
    assert snapshot.status == "empty"
    assert snapshot.sources[0].configured is False
    assert snapshot.sources[0].observed_context == {}


def test_remote_context_accepts_public_metadata_only():
    snapshot = build_remote_context_snapshot(
        {
            "repository": "owner/repo",
            "run_id": "123",
            "workflow": "validation",
            "branch": "main",
            "commit": "1234567890abcdef",
            "ignored": "value",
        }
    )
    body = snapshot.model_dump(mode="json")
    assert body["status"] == "ready"
    observed = body["sources"][0]["observed_context"]
    assert observed["repository"] == "owner/repo"
    assert observed["commit"] == "1234567890ab"
    assert "ignored" not in observed
