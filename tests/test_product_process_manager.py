from __future__ import annotations

import json
import subprocess

from scripts import start_product


def test_popen_kwargs_are_platform_compatible(monkeypatch):
    monkeypatch.setattr(start_product.os, "name", "posix")

    kwargs = start_product._popen_kwargs()

    assert kwargs == {"start_new_session": True}


def test_popen_kwargs_support_windows(monkeypatch):
    monkeypatch.setattr(start_product.os, "name", "nt")
    monkeypatch.setattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 512, raising=False)

    kwargs = start_product._popen_kwargs()

    assert kwargs == {"creationflags": 512}


def test_build_commands_use_forward_slash_paths():
    commands = start_product._build_service_commands(
        python_executable="./.venv/bin/python",
        api_port=8000,
        aktools_port=8080,
        streamlit_port=8771,
    )

    assert commands["aktools"] == [
        "./.venv/bin/python",
        "-m",
        "uvicorn",
        "src.integrations.aktools_compat_app:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8080",
    ]
    assert commands["api"][2:5] == ["uvicorn", "src.api.app:app", "--host"]
    assert "src/ui_report/product_dashboard.py" in commands["streamlit"]


# ============================================================
# Startup Mode Tests
# ============================================================

class _MockPopen:
    """Mock subprocess.Popen that captures args and returns a fake process."""

    def __init__(self, cmd, **kwargs):
        self.cmd = cmd
        self.args = kwargs
        self.pid = 99999
        self.stdout = None
        self.stderr = None

    def terminate(self):
        pass

    def wait(self, timeout=5):
        pass

    def poll(self):
        pass


def _patch_env(monkeypatch):
    """Common monkeypatches to run start_product.main() safely."""
    import tempfile
    from pathlib import Path

    # Avoid real process launches
    monkeypatch.setattr(start_product.subprocess, "Popen", _MockPopen)
    monkeypatch.setattr(start_product, "_wait_http_ok", lambda *a, **kw: True)
    # No live trading
    monkeypatch.setattr(start_product, "_check_live_trading_safety", lambda: True)
    # Bootstrap passes
    monkeypatch.setattr(start_product.subprocess, "run", lambda *a, **kw: type("R", (), {"returncode": 0})())
    # Ports free
    monkeypatch.setattr(start_product, "_port_in_use", lambda p: False)
    # No real sleep
    monkeypatch.setattr(start_product.time, "sleep", lambda s: None)
    # Writeable temp dir for PID
    tmpdir = tempfile.mkdtemp()
    monkeypatch.setattr(start_product, "PID_FILE", Path(tmpdir) / "product.pid.json")
    # Prevent main() exit
    monkeypatch.setattr(start_product.sys, "exit", lambda code: None)


class TestStartupModes:
    """Default startup includes AkTools; --no-aktools skips it; --full adds BugFix."""

    def test_default_startup_includes_aktools(self, monkeypatch):
        """Default ``bash scripts/start.sh`` starts AkTools + FastAPI + Streamlit."""
        _patch_env(monkeypatch)
        monkeypatch.setattr(start_product.sys, "argv", ["start_product.py"])
        start_product.main()
        pid_data = json.loads(start_product.PID_FILE.read_text())
        assert pid_data["aktools_pid"] == 99999, "AkTools should be started by default"

    def test_no_aktools_skips_aktools(self, monkeypatch):
        """--no-aktools skips AkTools."""
        _patch_env(monkeypatch)
        monkeypatch.setattr(start_product.sys, "argv", ["start_product.py", "--no-aktools"])
        start_product.main()
        pid_data = json.loads(start_product.PID_FILE.read_text())
        assert pid_data["aktools_pid"] is None, "AkTools should not be started with --no-aktools"

    def test_full_implies_aktools_and_bugfix(self, monkeypatch):
        """--full starts AkTools and requests BugFixAgent."""
        _patch_env(monkeypatch)
        monkeypatch.setattr(start_product.sys, "argv", ["start_product.py", "--full"])
        start_product.main()
        pid_data = json.loads(start_product.PID_FILE.read_text())
        assert pid_data["aktools_pid"] == 99999, "--full should start AkTools"
        assert pid_data["bug_fix_agent_requested"] is True, "--full should request BugFixAgent"

    def test_with_aktools_backward_compat(self, monkeypatch):
        """--with-aktools still works (backward compat)."""
        _patch_env(monkeypatch)
        monkeypatch.setattr(start_product.sys, "argv", ["start_product.py", "--with-aktools"])
        start_product.main()
        pid_data = json.loads(start_product.PID_FILE.read_text())
        assert pid_data["aktools_pid"] == 99999, "--with-aktools should start AkTools"

    def test_dry_run_default_lists_aktools(self, monkeypatch, capsys):
        """--dry-run lists AkTools in planned services."""
        _patch_env(monkeypatch)
        monkeypatch.setattr(start_product.sys, "argv", ["start_product.py", "--dry-run"])
        start_product.main()
        captured = capsys.readouterr()
        assert "FastAPI" in captured.out
        assert "AkTools" in captured.out, "Default dry-run should list AkTools"

    def test_dry_run_no_aktools_omits_aktools(self, monkeypatch, capsys):
        """--dry-run --no-aktools lists only FastAPI + Streamlit."""
        _patch_env(monkeypatch)
        monkeypatch.setattr(start_product.sys, "argv", ["start_product.py", "--dry-run", "--no-aktools"])
        start_product.main()
        captured = capsys.readouterr()
        assert "FastAPI" in captured.out
        assert "AkTools" not in captured.out, "--no-aktools dry-run should NOT list AkTools"

    def test_dry_run_full_lists_bugfix(self, monkeypatch, capsys):
        """--dry-run --full lists BugFixAgent."""
        _patch_env(monkeypatch)
        monkeypatch.setattr(start_product.sys, "argv", ["start_product.py", "--dry-run", "--full"])
        start_product.main()
        captured = capsys.readouterr()
        assert "AkTools" in captured.out
        assert "BugFix" in captured.out or "bugfix" in captured.out.lower()

    def test_pid_metadata_aktools_only_when_started(self, monkeypatch):
        """PID file records aktools_pid only when AkTools is started."""
        _patch_env(monkeypatch)

        # Without AkTools
        monkeypatch.setattr(start_product.sys, "argv", ["start_product.py", "--no-aktools"])
        start_product.main()
        pid_no = json.loads(start_product.PID_FILE.read_text())
        assert pid_no["aktools_pid"] is None
        assert pid_no["aktools_port"] is None

        # With AkTools (default)
        monkeypatch.setattr(start_product.sys, "argv", ["start_product.py"])
        start_product.main()
        pid_yes = json.loads(start_product.PID_FILE.read_text())
        assert pid_yes["aktools_pid"] == 99999
        assert pid_yes["aktools_port"] == start_product.DEFAULT_AKTOOLS_PORT
