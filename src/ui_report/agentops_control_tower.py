from __future__ import annotations

from typing import Any

import streamlit as st

from src.ui_report.i18n import t

_PAGE_CSS = """
<style>
.ct-card {
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  padding: 14px 16px;
  background: #ffffff;
  margin-bottom: 12px;
}
.ct-label {
  font-size: 0.78rem;
  color: #62748e;
  margin-bottom: 4px;
}
.ct-value {
  font-size: 1.0rem;
  font-weight: 600;
  color: #102a43;
}
.ct-status-passed {
  color: #0f766e;
  font-weight: 600;
}
.ct-status-failed {
  color: #b91c1c;
  font-weight: 600;
}
.ct-status-in_progress {
  color: #2563eb;
  font-weight: 600;
}
.ct-status-pending {
  color: #9ca3af;
  font-weight: 600;
}
.ct-status-blocked {
  color: #b45309;
  font-weight: 600;
}
.ct-status-skipped {
  color: #6b7280;
  font-weight: 600;
}
.ct-status-unknown {
  color: #9ca3af;
  font-weight: 600;
}
.ct-doc-present {
  color: #0f766e;
}
.ct-doc-missing {
  color: #b91c1c;
}
.ct-doc-stale {
  color: #b45309;
}
.ct-doc-unreadable {
  color: #b91c1c;
}
.ct-section-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: #102a43;
  margin-top: 16px;
  margin-bottom: 8px;
}
</style>
"""


def _status_class(status: str) -> str:
    return f"ct-status-{status}"


def _doc_status_class(status: str) -> str:
    return f"ct-doc-{status}"


def _render_feature_summary(observation: dict[str, Any]) -> None:
    feat = observation.get("feature", {})
    issue = observation.get("issue", {})
    branch = observation.get("branch", {})

    st.markdown(f'<div class="ct-section-title">{t("feature_summary")}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="ct-card">'
        f'<div><span class="ct-label">{t("feature_id")}:</span> <span class="ct-value">{feat.get("feature_id", "?")}</span></div>'
        f'<div><span class="ct-label">{t("risk_level")}:</span> {feat.get("risk_level", "?")}</div>'
        f'<div><span class="ct-label">{t("current_stage")}:</span> {feat.get("current_stage", "?")}</div>'
        f'<div><span class="ct-label">{t("issue_number")}:</span> #{issue.get("number", "?")}</div>'
        f'<div><span class="ct-label">{t("epic_branch")}:</span> {branch.get("epic_branch", "?")}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if feat.get("title"):
        st.markdown(f"**{feat['title']}**")


def _render_stage_status_list(observation: dict[str, Any]) -> None:
    stages = observation.get("stages", [])
    if not stages:
        st.markdown(f'<div class="ct-section-title">{t("stage_status_list")}</div>', unsafe_allow_html=True)
        st.caption("—")
        return

    lines = [f'<div class="ct-section-title">{t("stage_status_list")}</div>']
    for s in stages:
        name = s.get("name", "?")
        status = s.get("status", "unknown")
        cls = _status_class(status)
        lines.append(
            f'<div style="display:flex;justify-content:space-between;padding:4px 0;">'
            f'<span>{name}</span>'
            f'<span class="{cls}">{status}</span>'
            f'</div>'
        )
    st.markdown("".join(lines), unsafe_allow_html=True)


def _render_required_docs(observation: dict[str, Any]) -> None:
    docs = observation.get("required_docs", [])
    st.markdown(f'<div class="ct-section-title">{t("required_docs")}</div>', unsafe_allow_html=True)
    if not docs:
        st.caption(t("no_docs"))
        return

    for d in docs:
        kind = d.get("kind", "?")
        path = d.get("path", "?")
        status = d.get("status", "unknown")
        cls = _doc_status_class(status)
        st.markdown(
            f'<div>'
            f'<span class="ct-label">{kind}:</span> '
            f'<code>{path}</code> '
            f'<span class="{cls}">[{status}]</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_safety_blockers(observation: dict[str, Any]) -> None:
    safety = observation.get("safety", {})
    blockers = safety.get("blockers", [])
    warnings = safety.get("warnings", [])
    st.markdown(f'<div class="ct-section-title">{t("safety_blockers")}</div>', unsafe_allow_html=True)

    if blockers:
        for b in blockers:
            st.error(b)
    if warnings:
        for w in warnings:
            st.warning(w)
    if not blockers and not warnings:
        st.success(t("no_blockers"))


def _render_data_quality(observation: dict[str, Any]) -> None:
    dq = observation.get("data_quality", {})
    st.markdown(f'<div class="ct-section-title">{t("data_quality")}</div>', unsafe_allow_html=True)
    status = dq.get("status", "unknown")
    st.markdown(
        f'<div><span class="ct-label">{t("data_quality_status")}:</span> '
        f'<span class="{_status_class(status)}">{status}</span></div>',
        unsafe_allow_html=True,
    )
    missing = dq.get("missing_sources", [])
    unparsable = dq.get("unparsable_sources", [])
    stale = dq.get("stale_sources", [])
    if missing:
        st.markdown(f'<div class="ct-label">{t("missing_sources")}: {", ".join(missing)}</div>', unsafe_allow_html=True)
    if unparsable:
        st.markdown(f'<div class="ct-label">{t("unparsable_sources")}: {", ".join(unparsable)}</div>', unsafe_allow_html=True)
    if stale:
        st.markdown(f'<div class="ct-label">{t("stale_sources")}: {", ".join(stale)}</div>', unsafe_allow_html=True)


def _render_errors(observation: dict[str, Any]) -> None:
    errors = observation.get("errors", [])
    st.markdown(f'<div class="ct-section-title">{t("pipeline_errors")}</div>', unsafe_allow_html=True)
    if not errors:
        st.caption(t("no_errors"))
        return
    for err in errors:
        code = err.get("code", "")
        msg = err.get("message", "")
        source = err.get("source", "")
        parts = [
            '<div style="color:#b91c1c;">',
            f'<span class="ct-label">{t("error_code")}:</span> {code} | ',
            f'<span class="ct-label">{t("error_message")}:</span> {msg}',
        ]
        if source:
            parts.append(
                f' | <span class="ct-label">{t("error_source")}:</span> {source}'
            )
        parts.append("</div>")
        st.markdown("".join(parts), unsafe_allow_html=True)


def render_control_tower_page(state: dict[str, Any]) -> None:
    st.markdown(_PAGE_CSS, unsafe_allow_html=True)
    st.subheader(t("agentops_control_tower"))
    st.caption(t("control_tower_caption"))

    view_status = state.get("view_status")

    if view_status is None:
        st.info(t("feature_not_selected"))
        return

    if view_status == "empty":
        st.warning(t("control_tower_empty"))
        error = state.get("error")
        if error:
            st.caption(str(error))
        return

    if view_status == "error":
        st.error(t("control_tower_error"))
        error = state.get("error")
        if error:
            st.caption(str(error))
        return

    if view_status == "stale":
        st.warning(t("control_tower_stale"))

    observation = state.get("observation")
    if not observation:
        st.error(t("control_tower_unavailable"))
        return

    _render_feature_summary(observation)
    _render_stage_status_list(observation)
    _render_required_docs(observation)
    _render_data_quality(observation)
    _render_safety_blockers(observation)
    _render_errors(observation)
