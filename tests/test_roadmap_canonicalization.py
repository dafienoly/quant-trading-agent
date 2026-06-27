from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROADMAP_DIR = ROOT / "docs" / "roadmap"
CANONICAL = ROADMAP_DIR / "MASTER_ROADMAP.md"
COMPATIBILITY = ROADMAP_DIR / "MASTER_ROADMAP_AGENT_EXECUTABLE.md"
README = ROADMAP_DIR / "README.md"


def test_canonical_roadmap_entrypoint_exists():
    assert CANONICAL.exists(), "docs/roadmap/MASTER_ROADMAP.md must be the canonical entrypoint"
    text = CANONICAL.read_text(encoding="utf-8")
    assert "Canonical path" in text
    assert "docs/roadmap/MASTER_ROADMAP.md" in text
    assert "MASTER_ROADMAP_AGENT_EXECUTABLE.md" in text


def test_roadmap_directory_readme_defines_priority():
    assert README.exists(), "docs/roadmap/README.md must document roadmap priority rules"
    text = README.read_text(encoding="utf-8")
    assert "Canonical entrypoint" in text
    assert "Priority order" in text
    assert "MASTER_ROADMAP.md" in text
    assert "MASTER_ROADMAP_AGENT_EXECUTABLE.md" in text


def test_canonical_roadmap_keeps_core_constraints():
    text = CANONICAL.read_text(encoding="utf-8")
    required_terms = [
        "Streamlit",
        "/product/**",
        "AgentOps",
        "Market Data Relay",
        "Provider Test Suite",
        "Quant Tool Registry",
        "Model Gateway",
        "Decision Snapshot",
        "Position Sizing",
        "Strategy Validation",
        "Risk Sentinel",
        "Paper Trading",
        "Broker Readonly Shadow",
        "LEVEL_3_AUTO",
        "R0.1 Roadmap Canonicalization",
        "R0.3 Agent Runtime Abstraction",
        "Old-roadmap conflict handling",
    ]
    missing = [term for term in required_terms if term not in text]
    assert not missing, f"canonical roadmap missing required terms: {missing}"


def test_compatibility_roadmap_still_preserves_detailed_route():
    assert COMPATIBILITY.exists(), "historical detailed roadmap must remain available for compatibility"
    text = COMPATIBILITY.read_text(encoding="utf-8")
    required_terms = [
        "Detailed Agent-Executable Roadmap",
        "V16.1  AgentOps Control Tower Foundation",
        "V16.14 Fundamental Alpha Portfolio & Watchlist",
        "V17.3  LEVEL_3_AUTO Evaluation",
        "旧 Roadmap 冲突处理规则",
    ]
    missing = [term for term in required_terms if term not in text]
    assert not missing, f"compatibility roadmap missing detailed-route terms: {missing}"


def test_roadmap_priority_keeps_single_source_of_truth_language():
    canonical = CANONICAL.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    assert "must not become a second source of truth" in canonical
    assert "must not become a separate source of truth" in readme
