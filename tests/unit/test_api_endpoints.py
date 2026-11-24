"""Direct verification tests for all REST API endpoint handlers.
Tests schemas, validations, database interactions, and business logic.
"""

import os
import shutil
import tempfile
import pytest

from app.main import health_check, analyze_failure_endpoint, AnalyzeFailureRequest, serve_dashboard_ui
from app.api.repositories import (
    list_repositories,
    get_repository_tree,
    get_file,
    search_repository_code,
    CodeSearchRequest,
)
from app.api.evaluation import list_benchmarks, get_evaluation_results
from app.api.investigations import get_all_investigations
from app.api.patches import (
    preview_patch,
    apply_patch_endpoint,
    rollback_patch_endpoint,
    PatchPreviewRequest,
    ApplyPatchRequest,
    RollbackPatchRequest,
    _ROLLBACK_REGISTRY,
)
from app.schemas.fix import FixProposal
from app.schemas.report import InvestigationReport
from app.database.db import save_investigation


def test_health_check_handler():
    res = health_check()
    assert res["status"] == "ok"
    assert res["app"] == "BugScope"
    assert len(res["endpoints"]) >= 8

    # Verify dashboard root UI
    dash = serve_dashboard_ui()
    assert os.path.exists(dash.path)
    assert str(dash.path).endswith("index.html")


def test_analyze_failure_handler():
    trace = (
        "Traceback (most recent call last):\n"
        "  File \"app/calc.py\", line 10, in compute\n"
        "    val = data[\"price\"]\n"
        "KeyError: 'price'\n"
    )
    req = AnalyzeFailureRequest(raw_trace=trace)
    rep = analyze_failure_endpoint(req)
    assert rep.error_type == "KeyError"
    assert rep.file == "app/calc.py"
    assert rep.line == 10
    assert rep.function == "compute"


def test_repositories_endpoints():
    res = list_repositories()
    assert "repositories" in res
    assert len(res["repositories"]) >= 20

    first_repo_path = res["repositories"][0]["path"]
    tree_res = get_repository_tree(path=first_repo_path)
    assert "tree" in tree_res
    assert len(tree_res["tree"]) > 0

    file_res = get_file(repo_path=first_repo_path, file_path="app/user.py")
    assert "content" in file_res
    assert len(file_res["content"]) > 0

    search_res = search_repository_code(
        CodeSearchRequest(repo_path=first_repo_path, query="def ")
    )
    assert search_res["matches_count"] > 0

    # Security test: reject path traversal to system directories outside workspace
    from fastapi import HTTPException
    bad_system_path = "C:\\Windows" if os.name == "nt" else "/etc"
    with pytest.raises(HTTPException) as exc_info:
        get_repository_tree(path=bad_system_path)
    assert exc_info.value.status_code in (403, 404)


def test_evaluation_endpoints():
    bms = list_benchmarks()
    assert "cases" in bms
    assert len(bms["cases"]) >= 20

    res = get_evaluation_results()
    assert "bugscope" in res or "bugscope_results" in res


def test_investigations_list_endpoint():
    invs = get_all_investigations(limit=10)
    assert isinstance(invs, list)


def test_patch_endpoints_workflow():
    orig_code = "def foo():\n    return 'old'\n"
    diff_content = (
        "--- a/sample.py\n"
        "+++ b/sample.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def foo():\n"
        "-    return 'old'\n"
        "+    return 'new'\n"
    )
    # 1. Preview
    prev = preview_patch(PatchPreviewRequest(original_code=orig_code, diff=diff_content))
    assert prev["success"] is True
    assert "return 'new'" in prev["patched_code"]

    # 2. Setup mock investigation report in DB for apply endpoint
    d = tempfile.mkdtemp()
    try:
        sf = os.path.join(d, "sample.py")
        with open(sf, "w") as f:
            f.write(orig_code)

        from app.schemas.failure import FailureReport
        mock_report = InvestigationReport(
            investigation_id="test_inv_patch_123",
            failure_report=FailureReport(
                error_type="KeyError",
                message="test error",
                category="KeyError",
                file="sample.py",
                line=1,
                function="foo",
            ),
            error_type="KeyError",
            message="test error",
            verdict="validated",
            fix_proposal=FixProposal(status="proposed", diff=diff_content),
        )
        save_investigation(mock_report)

        # Apply
        app_res = apply_patch_endpoint(
            ApplyPatchRequest(
                investigation_id="test_inv_patch_123",
                target_repo_dir=d,
                user_approved=True,
            )
        )
        assert app_res["status"] == "applied"
        with open(sf, "r") as f:
            assert f.read() == "def foo():\n    return 'new'\n"

        # Rollback
        roll_res = rollback_patch_endpoint(
            RollbackPatchRequest(
                investigation_id="test_inv_patch_123",
                target_repo_dir=d,
            )
        )
        assert roll_res["status"] == "rolled_back"
        with open(sf, "r") as f:
            assert f.read() == orig_code
    finally:
        shutil.rmtree(d, ignore_errors=True)
