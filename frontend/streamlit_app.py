"""Streamlit dashboard for BugScope.

Provides interactive UI for evidence-checked Python debugging:
- Page 1: New Investigation (pasted error, optional ZIP upload, live execution, 6 tabs)
- Page 2: History (past investigation records loaded from SQLite)
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# Add project root to path so Streamlit can import app modules directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app.database.db import get_investigation, list_investigations, save_investigation
from app.schemas.report import InvestigationReport
from app.services.zip_handler import create_temp_repo_from_zip, ZipSecurityError
from app.workflow.graph import create_bugscope_graph


st.set_page_config(
    page_title="BugScope — Evidence-Checked Debugger",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom badge styling
st.markdown(
    """
    <style>
    .verdict-badge {
        display: inline-block;
        padding: 6px 14px;
        font-weight: 700;
        font-size: 1.1rem;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    .verdict-validated { background-color: #d1fae5; color: #065f46; border: 1px solid #10b981; }
    .verdict-partially_validated { background-color: #fef3c7; color: #92400e; border: 1px solid #f59e0b; }
    .verdict-not_validated { background-color: #fee2e2; color: #991b1b; border: 1px solid #ef4444; }
    .verdict-could_not_reproduce { background-color: #ede9fe; color: #5b21b6; border: 1px solid #8b5cf6; }
    .verdict-needs_human_decision { background-color: #e0f2fe; color: #075985; border: 1px solid #0284c7; }
    .metric-box {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_verdict_badge(verdict: str):
    """Render colored verdict badge."""
    classes = {
        "validated": "verdict-validated",
        "partially_validated": "verdict-partially_validated",
        "not_validated": "verdict-not_validated",
        "could_not_reproduce": "verdict-could_not_reproduce",
        "needs_human_decision": "verdict-needs_human_decision",
    }
    cls = classes.get(verdict, "verdict-not_validated")
    label = verdict.replace("_", " ").upper()
    st.markdown(f'<div class="verdict-badge {cls}">VERDICT: {label}</div>', unsafe_allow_html=True)


def display_investigation_report(report: InvestigationReport):
    """Render full investigation report across 6 structured tabs."""
    render_verdict_badge(report.verdict)

    if report.validation_report and report.validation_report.limitations:
        for lim in report.validation_report.limitations:
            st.warning(f"⚠️ **Limitation**: {lim}")

    # Top summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Duration", f"{report.total_duration_seconds}s")
    with col2:
        st.metric("Total Cost (USD)", f"${report.total_cost_usd:.5f}")
    with col3:
        st.metric("Tokens In / Out", f"{report.total_tokens_in} / {report.total_tokens_out}")
    with col4:
        supp_count = sum(h.verified_support_count for h in report.hypotheses)
        st.metric("Verified Quotes", f"{supp_count} items")

    st.divider()

    tabs = st.tabs([
        "📋 Overview",
        "🔬 Hypotheses & Evidence",
        "💻 Code Context",
        "🛠️ Fix (diff)",
        "🧪 Tests",
        "📊 Telemetry Trace",
    ])

    # Tab 1: Overview
    with tabs[0]:
        st.subheader("Failure Summary")
        f = report.failure_report
        st.write(f"**Error Type**: `{f.error_type}` ({f.category})")
        st.write(f"**Message**: `{f.message}`")
        st.write(f"**Location**: `{f.file}:{f.line}` in `{f.function}()`")

        if f.call_chain:
            with st.expander("Call Chain (Frames)", expanded=False):
                for idx, frame in enumerate(f.call_chain):
                    st.write(f"{idx+1}. `{frame.file}:{frame.line}` in `{frame.function}`")

        if report.reproduction_result:
            st.subheader("Baseline Sandbox Reproduction")
            rep = report.reproduction_result
            st.write(f"**Reproduced Before Fix**: `{'YES' if rep.reproduced else 'NO'}`")
            st.write(f"**Command**: `{rep.command}`")
            st.write(f"**Exit Code**: `{rep.exit_code}` | **Trust Level**: `{rep.trust_level}`")
            if rep.stdout:
                with st.expander("Reproduction Output (stdout)", expanded=False):
                    st.code(rep.stdout)

    # Tab 2: Hypotheses & Evidence
    with tabs[1]:
        st.subheader("Mechanically Ranked Root-Cause Hypotheses")
        st.caption(
            "Every quote is checked against disk lines. Hallucinated quotes are discarded. "
            "Score = Verified Supports - Verified Contradicts. No fake percentages."
        )

        for h in report.hypotheses:
            is_top = report.top_hypothesis and report.top_hypothesis.id == h.id
            tag = "🌟 TOP RANKED" if is_top else f"Rank #{h.rank}"
            upstream_tag = " [UPSTREAM CAUSE]" if h.is_upstream else ""
            label_color = "🟢" if h.label == "supported" else "🔴"

            with st.expander(f"{tag}: {h.title}{upstream_tag} — Score: {h.score} ({label_color} {h.label})", expanded=is_top):
                st.write(f"**Explanation**: {h.explanation}")
                st.write(
                    f"**Evidence Counts**: `{h.verified_support_count} verified supports` | "
                    f"`{h.verified_contradict_count} verified contradicts` | "
                    f"`{h.discarded_evidence_count} discarded hallucinations`"
                )

                if h.discarded_evidence_count > 0:
                    st.info(f"🛡️ Note: {h.discarded_evidence_count} code quotes hallucinated by the LLM were mechanically discarded.")

                if h.evidence:
                    st.write("#### Verified Code Evidence:")
                    for idx, ev in enumerate(h.evidence, start=1):
                        stance_badge = "🟩 SUPPORTS" if ev.stance == "supports" else "🟥 CONTRADICTS"
                        st.markdown(f"**{idx}. `{ev.file}:{ev.line_start}-{ev.line_end}`** — {stance_badge}")
                        st.write(f"*Reason*: {ev.reason}")
                        st.code(ev.quote, language="python")
                else:
                    st.warning("No verified code evidence exists for this hypothesis.")

    # Tab 3: Code Context
    with tabs[2]:
        st.subheader("Repository Context Slices")
        if report.context_bundle:
            cb = report.context_bundle
            st.write(f"**Failing File**: `{cb.failing_file}` | **Failing Symbol**: `{cb.failing_symbol}`")
            if cb.callers:
                st.write(f"**Callers**: {', '.join(f'`{c}`' for c in cb.callers)}")
            if cb.callees:
                st.write(f"**Callees**: {', '.join(f'`{c}`' for c in cb.callees)}")
            if cb.related_tests:
                st.write(f"**Related Tests**: {', '.join(f'`{t}`' for t in cb.related_tests)}")

            st.write("#### Numbered Code Snippets:")
            for snip in cb.snippets:
                badge = "🔴 [CRASH LOCATION]" if snip.is_target else "📄 [CONTEXT]"
                st.markdown(f"**{snip.file}** (Lines {snip.line_start}-{snip.line_end}) {badge}")
                st.code(snip.code, language="python")
        else:
            st.info("No repository context was attached.")

    # Tab 4: Fix (diff)
    with tabs[3]:
        st.subheader("Proposed Fix Patch")
        if report.fix_proposal:
            fp = report.fix_proposal
            if fp.status == "needs_human_decision":
                st.warning("⚠️ **Status: Needs Human Decision** — Intended behavior is ambiguous.")
                if fp.options_if_ambiguous:
                    st.write("#### Options for Consideration:")
                    for opt in fp.options_if_ambiguous:
                        st.markdown(f"- {opt}")
            else:
                st.success("✅ **Status: Proposed Patch**")
                if fp.diff:
                    st.code(fp.diff, language="diff")
                else:
                    st.info("No unified diff generated.")

                if fp.assumptions:
                    st.write("#### Behavioral Assumptions:")
                    for asm in fp.assumptions:
                        st.markdown(f"- {asm}")

                if fp.side_effects:
                    st.write("#### Potential Side Effects:")
                    for se in fp.side_effects:
                        st.markdown(f"- {se}")
        else:
            st.info("No fix was proposed.")

    # Tab 5: Tests
    with tabs[4]:
        st.subheader("Synthesized Regression Test & Validation")
        if report.regression_test:
            rt = report.regression_test
            st.write(f"**Target Path**: `{rt.target_path}`")
            if rt.description:
                st.write(f"**Description**: {rt.description}")
            st.code(rt.test_code, language="python")

        if report.validation_report:
            vr = report.validation_report
            st.write("#### 3-Phase Verification Matrix:")
            col_v1, col_v2, col_v3 = st.columns(3)
            with col_v1:
                st.metric("1. Fails Before Patch", "YES" if vr.regression_fails_before else "NO")
            with col_v2:
                st.metric("2. Passes After Patch", "YES" if vr.regression_passes_after else "NO")
            with col_v3:
                st.metric("3. Existing Suite Pass", vr.existing_suite_result.upper())

            st.write(f"**Retries Used**: `{vr.retries_used}` | **Validation Duration**: `{vr.duration_seconds}s`")
            if vr.failure_log:
                with st.expander("Validation Failure Log", expanded=False):
                    st.code(vr.failure_log)
        else:
            st.info("Validation was not performed.")

    # Tab 6: Trace
    with tabs[5]:
        st.subheader("Execution Telemetry & Cost Breakdown")
        if report.traces:
            trace_data = []
            for tr in report.traces:
                trace_data.append({
                    "Node": tr.node,
                    "Duration (ms)": tr.duration_ms,
                    "Tokens In": tr.tokens_in,
                    "Tokens Out": tr.tokens_out,
                    "Cost (USD)": f"${tr.cost_usd:.6f}",
                    "Output Summary": tr.output_summary,
                })
            st.dataframe(trace_data, use_container_width=True)
        else:
            st.info("No traces recorded.")


# ==============================================================================
# Main Streamlit Application
# ==============================================================================

def main():
    st.sidebar.title("🔬 BugScope")
    st.sidebar.caption("Evidence-checked debugging agent for Python 3.11")

    page = st.sidebar.radio("Navigation", ["🔬 New Investigation", "📜 History"])

    st.sidebar.divider()
    st.sidebar.write("### System Architecture")
    st.sidebar.markdown(
        """
        - **Deterministic**: Traceback regex, AST slicer, mechanical quote check, 3-phase sandbox tests
        - **LLM**: 3 hypotheses, minimal diff, pytest regression test
        - **Sandbox**: Docker container (no network, 512MB RAM, 1 CPU, 30s timeout)
        """
    )

    if page == "🔬 New Investigation":
        st.title("🔬 New Debugging Investigation")
        st.write(
            "Paste an error message or stack trace, optionally upload a project ZIP (max 20 MB), "
            "and BugScope will mechanically investigate root causes, verify code evidence, and validate patches."
        )

        trace_input = st.text_area(
            "Pasted Error Message or Python Traceback:",
            height=180,
            placeholder="Traceback (most recent call last):\n  File 'app/pricing.py', line 15, in calc\n    return price * (1 - rate)\nTypeError: unsupported operand type(s) for -: 'int' and 'str'",
        )

        zip_file = st.file_uploader(
            "Upload Project ZIP archive (optional, max 20 MB):",
            type=["zip"],
            help="Zip file will be strictly inspected, sanitized, and unpacked into an isolated temporary folder.",
        )

        run_btn = st.button("🚀 Start Evidence-Checked Investigation", type="primary", use_container_width=True)

        if run_btn:
            if not trace_input.strip():
                st.error("Please paste an error message or traceback before starting.")
                return

            repo_dir = None
            if zip_file:
                try:
                    with st.spinner("Extracting and sanitizing ZIP archive..."):
                        zip_bytes = zip_file.read()
                        repo_dir = create_temp_repo_from_zip(zip_bytes)
                        st.success("ZIP archive safely verified and extracted.")
                except ZipSecurityError as z_err:
                    st.error(f"ZIP Security Error: {z_err}")
                    return
                except Exception as exc:
                    st.error(f"Failed to extract ZIP: {exc}")
                    return
            else:
                # Default to current directory if no zip uploaded
                repo_dir = str(Path.cwd())

            with st.spinner("Running BugScope LangGraph evidence-checking pipeline..."):
                try:
                    graph = create_bugscope_graph()
                    initial_state = {
                        "raw_trace": trace_input,
                        "repo_dir": repo_dir,
                        "traces": [],
                        "retries_used": 0,
                        "max_retries": 2,
                    }
                    final_state = graph.invoke(initial_state)
                    report = final_state.get("investigation_report")

                    if report:
                        st.session_state["current_report"] = report
                        st.success(f"Investigation complete! Verdict: {report.verdict.upper()}")
                    else:
                        st.error("Workflow completed without generating an investigation report.")
                except Exception as exc:
                    st.error(f"Investigation failed: {exc}")

        # Render current investigation if present in session state
        if "current_report" in st.session_state:
            st.divider()
            display_investigation_report(st.session_state["current_report"])

    elif page == "📜 History":
        st.title("📜 Investigation History")
        st.write("Browse past investigations persisted in SQLite.")

        history_items = list_investigations(limit=50)
        if not history_items:
            st.info("No past investigations found in the database. Run a new investigation first!")
            return

        st.dataframe(history_items, use_container_width=True)

        st.subheader("Inspect Investigation Details")
        inv_ids = [h["id"] for h in history_items]
        selected_id = st.selectbox("Select Investigation ID to inspect:", inv_ids)

        if selected_id:
            report = get_investigation(selected_id)
            if report:
                st.divider()
                display_investigation_report(report)
            else:
                st.error("Failed to load investigation details.")


if __name__ == "__main__":
    main()
