from __future__ import annotations

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
