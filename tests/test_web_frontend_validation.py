from __future__ import annotations

import json
from pathlib import Path


def test_web_workspace_has_required_files() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    required_paths = [
        "apps/web/package.json",
        "apps/web/tsconfig.json",
        "apps/web/vite.config.ts",
        "apps/web/src/App.tsx",
        "apps/web/src/api/agentops.ts",
        "apps/web/src/api/context.ts",
        "apps/web/src/api/contextSelectors.ts",
        "apps/web/src/components/AdapterStatusCard.tsx",
        "apps/web/src/components/AdapterStatusPanel.tsx",
        "apps/web/src/components/AgentOpsCards.tsx",
    ]

    missing = [path for path in required_paths if not (repo_root / path).exists()]
    assert missing == []


def test_web_package_exposes_validation_scripts() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    package_json = json.loads((repo_root / "apps/web/package.json").read_text(encoding="utf-8"))
    scripts = package_json.get("scripts", {})

    assert "test" in scripts
    assert "build" in scripts
    assert "vitest" in scripts["test"]
    assert "tsc" in scripts["build"]
    assert "vite build" in scripts["build"]


def test_web_workspace_does_not_commit_node_modules() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    assert not (repo_root / "apps/web/node_modules").exists()
