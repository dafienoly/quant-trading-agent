from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from src.product_app.agentops.pipeline_contracts import (
    DocumentStatus,
)
from src.product_app.agentops.pipeline_errors import (
    PipelineStateUnavailableError,
    PipelineStateUnparsableError,
)
from src.product_app.agentops.pipeline_state_reader import (
    PipelineReadResult,
    check_doc_status_readonly,
    read_handoff_files,
    read_pipeline_state,
    resolve_target,
)


class TestResolveTarget:
    def test_by_feature_id(self):
        result = resolve_target(feature_id="test-feature")
        assert result.feature_id == "test-feature"
        assert result.issue_number is None

    def test_by_issue_number(self):
        result = resolve_target(issue_number=42)
        assert result.feature_id is None
        assert result.issue_number == 42

    def test_both_provided(self):
        result = resolve_target(feature_id="f1", issue_number=1)
        assert result.feature_id == "f1"
        assert result.issue_number == 1

    def test_neither_provided(self):
        result = resolve_target()
        assert result.feature_id is None
        assert result.issue_number is None


class TestReadPipelineState:
    def test_read_valid_state(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"feature_id": "test", "current_stage": "phase_dev"}, f)
            tmp = f.name
        try:
            result = read_pipeline_state(tmp)
            assert result.state["feature_id"] == "test"
            assert result.not_found is False
        finally:
            os.unlink(tmp)

    def test_file_not_found(self):
        result = read_pipeline_state("/tmp/nonexistent_abcdef.json", required=False)
        assert result.not_found is True

    def test_file_not_found_required_raises(self):
        with pytest.raises(PipelineStateUnavailableError):
            read_pipeline_state("/tmp/nonexistent_abcdef.json", required=True)

    def test_unparsable_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json...")
            tmp = f.name
        try:
            with pytest.raises(PipelineStateUnparsableError):
                read_pipeline_state(tmp, required=True)
        finally:
            os.unlink(tmp)

    def test_unparsable_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("key: [unclosed list")
            tmp = f.name
        try:
            with pytest.raises(PipelineStateUnparsableError):
                read_pipeline_state(tmp, required=True)
        finally:
            os.unlink(tmp)

    def test_unparsable_with_partial(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{partial")
            tmp = f.name
        try:
            result = read_pipeline_state(tmp, required=False)
            assert result.unparsable is True
            assert result.partial is True
        finally:
            os.unlink(tmp)


class TestReadHandoffFiles:
    def test_directory_not_exists(self):
        result = read_handoff_files("/tmp/nonexistent_handoff_dir_abc123")
        assert result == []

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as td:
            result = read_handoff_files(td)
            assert result == []

    def test_reads_md_files(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "stage1.md").write_text("content")
            Path(td, "stage2.md").write_text("content")
            Path(td, "notes.txt").write_text("ignore")
            result = read_handoff_files(td)
            assert len(result) == 2
            assert all(f.endswith(".md") for f in result)


class TestCheckDocStatusReadonly:
    def test_file_present(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp = f.name
        try:
            status = check_doc_status_readonly(tmp)
            assert status == DocumentStatus.PRESENT
        finally:
            os.unlink(tmp)

    def test_file_missing(self):
        status = check_doc_status_readonly("/tmp/nonexistent_doc_abc456.md")
        assert status == DocumentStatus.MISSING

    def test_file_unreadable(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp = f.name
        os.chmod(tmp, 0o000)
        try:
            status = check_doc_status_readonly(tmp)
            assert status == DocumentStatus.UNREADABLE
        finally:
            os.chmod(tmp, 0o644)
            os.unlink(tmp)

    def test_empty_path(self):
        status = check_doc_status_readonly("")
        assert status == DocumentStatus.UNKNOWN


class TestPipelineReadResult:
    def test_defaults(self):
        result = PipelineReadResult({})
        assert result.state == {}
        assert result.not_found is False
        assert result.unparsable is False
        assert result.partial is False
        assert result.errors == []

    def test_with_errors(self):
        from src.product_app.agentops.pipeline_contracts import ErrorInfo

        err = ErrorInfo(code="ERR", message="msg", source="src")
        result = PipelineReadResult({}, errors=[err])
        assert len(result.errors) == 1
