"""Verification script for BugScope backend startup, API endpoints, patch workflow, and runtime checks."""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from app.main import app, health_check, serve_dashboard_ui
from app.api.repositories import list_repositories
from app.api.investigations import get_all_investigations
from app.api.patches import (
    preview_patch,
    apply_patch_endpoint,
    rollback_patch_endpoint,
    PatchPreviewRequest,
    ApplyPatchRequest,
    RollbackPatchRequest,
)
from app.database.db import save_investigation
from app.schemas.failure import FailureReport
from app.schemas.fix import FixProposal
from app.schemas.report import InvestigationReport
from app.services.sandbox import is_docker_available


def main():
    print("=======================================================")
    print("  BugScope Runtime Release Verification")
    print("=======================================================\n")

    results = {}

    try:
        # 1. Health & Dashboard verification
        print("[1/5] Verifying Health and Dashboard Endpoints...")
        h_data = health_check()
        print(f"  Health check: status={h_data['status']}, app={h_data['app']}, endpoints={len(h_data['endpoints'])}")
        assert h_data["status"] == "ok"
        results["health_status"] = h_data["status"]

        dash = serve_dashboard_ui()
        dash_path = Path(dash.path)
        print(f"  Dashboard static HTML: path={dash_path}, exists={dash_path.is_file()}, size={dash_path.stat().st_size} bytes")
        assert dash_path.is_file()
        results["dashboard_ui_file"] = str(dash_path.name)

        # 2. Benchmark repositories
        print("\n[2/5] Verifying Sample Bugs Repository Endpoint...")
        bugs_res = list_repositories()
        bug_count = len(bugs_res.get("bugs", []))
        print(f"  Sample bugs: {bug_count} benchmark cases discovered")
        assert bug_count == 24
        results["benchmark_cases_count"] = bug_count

        # 3. Investigations API
        print("\n[3/5] Verifying Investigations API...")
        invs = get_all_investigations(limit=10)
        print(f"  Investigations records query: {len(invs)} existing records returned")
        results["investigations_api"] = "ok"

        # 4. Patch Preview, Apply, and Rollback
        print("\n[4/5] Verifying Patch Preview, Apply, and Rollback Workflow...")
        temp_dir = tempfile.mkdtemp(prefix="bugscope_release_verify_")
        try:
            target_file = os.path.join(temp_dir, "calc.py")
            orig_code = "def compute(a, b):\n    return a - b\n"
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(orig_code)

            diff_code = (
                "--- a/calc.py\n"
                "+++ b/calc.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def compute(a, b):\n"
                "-    return a - b\n"
                "+    return a + b\n"
            )

            # Preview
            prev = preview_patch(PatchPreviewRequest(original_code=orig_code, diff=diff_code))
            print(f"  Patch preview: success={prev.get('success')}")
            assert prev.get("success") is True
            assert "return a + b" in prev.get("patched_code", "")

            # Register mock report in DB
            inv_id = "verify_patch_inv_001"
            mock_rep = InvestigationReport(
                investigation_id=inv_id,
                failure_report=FailureReport(
                    error_type="LogicError",
                    message="Subtraction instead of addition",
                    category="LogicError",
                    file="calc.py",
                    line=2,
                    function="compute",
                ),
                error_type="LogicError",
                message="Subtraction instead of addition",
                verdict="validated",
                fix_proposal=FixProposal(status="proposed", diff=diff_code),
                repository_path=temp_dir,
            )
            save_investigation(mock_rep)

            # Apply
            apply_res = apply_patch_endpoint(ApplyPatchRequest(investigation_id=inv_id, target_repo_dir=temp_dir, user_approved=True))
            print(f"  Patch apply: status={apply_res.get('status')}, modified={apply_res.get('modified_files')}")
            assert apply_res.get("status") == "applied"
            with open(target_file, "r", encoding="utf-8") as f:
                patched_on_disk = f.read()
            assert "return a + b" in patched_on_disk
            print("  Verified disk content was successfully patched.")

            # Rollback
            rollback_res = rollback_patch_endpoint(RollbackPatchRequest(investigation_id=inv_id, target_repo_dir=temp_dir))
            print(f"  Patch rollback: status={rollback_res.get('status')}, restored={rollback_res.get('restored_files')}")
            assert rollback_res.get("status") == "rolled_back"
            with open(target_file, "r", encoding="utf-8") as f:
                restored_on_disk = f.read()
            assert restored_on_disk == orig_code
            print("  Verified disk content was perfectly rolled back to original content.")
            results["patch_workflow"] = "validated"

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        # 5. Docker sandbox status
        print("\n[5/5] Checking Docker Sandbox Availability...")
        d_avail = is_docker_available()
        print(f"  Docker daemon available: {d_avail}")
        results["docker_available"] = d_avail

        print("\n=======================================================")
        print("  Runtime Verification Summary:")
        print(json.dumps(results, indent=2))
        print("=======================================================\n")
        return 0

    except Exception as exc:
        print(f"\nVerification FAILED: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
