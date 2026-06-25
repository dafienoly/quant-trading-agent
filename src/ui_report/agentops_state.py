from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests
import streamlit as st

DEFAULT_API_BASE = "http://localhost:8000"
API_TIMEOUT = 8


def _api_base() -> str:
    return st.session_state.get("api_base", DEFAULT_API_BASE).rstrip("/")


def _state() -> dict[str, Any]:
    if "_agentops_state" not in st.session_state:
        st.session_state["_agentops_state"] = {
            "view_status": None,
            "observation": None,
            "error": None,
            "last_loaded_at": None,
            "is_refreshing": False,
        }
    return st.session_state["_agentops_state"]


def _normalize_error(message: str) -> str:
    safe = message.replace("\\", "/")
    for bad in ("/mnt/", "C:\\", "D:\\", "/home/", "/root/", "/Users/"):
        safe = safe.replace(bad, "<workspace>/")
    return safe


def _fetch_and_update(url: str, cache_key: str | int | None = None) -> dict[str, Any]:
    state = _state()
    state["is_refreshing"] = True
    state["error"] = None

    try:
        response = requests.get(url, timeout=API_TIMEOUT)
        if response.status_code == 200:
            observation = response.json()
            blockers = observation.get("safety", {}).get("blockers", [])
            state["view_status"] = "blocked" if blockers else "ready"
            state["observation"] = observation
            state["error"] = None
        elif response.status_code == 404:
            state["view_status"] = "empty"
            state["observation"] = None
            try:
                body = response.json()
                err = body.get("error", body)
            except Exception:
                err = {"message": f"HTTP {response.status_code}"}
            state["error"] = _normalize_error(str(err))
        else:
            try:
                body = response.json()
                err = body.get("error", body)
            except Exception:
                err = {"message": f"HTTP {response.status_code}"}
            if state.get("observation") is not None:
                state["view_status"] = "stale"
            else:
                state["view_status"] = "error"
                state["observation"] = None
            state["error"] = _normalize_error(str(err))
    except Exception as exc:
        if state.get("observation") is not None:
            state["view_status"] = "stale"
        else:
            state["view_status"] = "error"
            state["observation"] = None
        state["error"] = _normalize_error(str(exc))

    if state["view_status"] not in ("stale",):
        state["last_loaded_at"] = datetime.now(timezone.utc).isoformat()
    state["is_refreshing"] = False
    return dict(state)


def load_by_feature_id(feature_id: str) -> dict[str, Any]:
    state = _state()
    if state.get("observation") and state.get("feature_id") == feature_id:
        return dict(state)

    state["feature_id"] = feature_id
    state["issue_number"] = None
    url = f"{_api_base()}/product/agentops/pipelines/{feature_id}"
    return _fetch_and_update(url, cache_key=feature_id)


def load_by_issue_number(issue_number: int) -> dict[str, Any]:
    state = _state()
    state["feature_id"] = None
    state["issue_number"] = issue_number
    url = f"{_api_base()}/product/agentops/pipelines/by-issue/{issue_number}"
    return _fetch_and_update(url, cache_key=issue_number)


def refresh() -> dict[str, Any]:
    state = _state()
    feature_id = state.get("feature_id")
    issue_number = state.get("issue_number")

    if not feature_id and not issue_number:
        raise RuntimeError("No previous observation to refresh")

    if feature_id:
        url = f"{_api_base()}/product/agentops/pipelines/{feature_id}"
    else:
        url = f"{_api_base()}/product/agentops/pipelines/by-issue/{issue_number}"
    return _fetch_and_update(url)


def clear() -> dict[str, Any]:
    state = _state()
    state["view_status"] = None
    state["observation"] = None
    state["error"] = None
    state["last_loaded_at"] = None
    state["is_refreshing"] = False
    state["feature_id"] = None
    state["issue_number"] = None
    return dict(state)
