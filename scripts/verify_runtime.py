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

from fastapi.testclient import TestClient


def main():
    print("=======================================================")
    print("  BugScope Runtime Release Verification")
    print("=======================================================\n")

    results = {}

    try:
        print("[1/4] Loading FastAPI backend application...")
        from app.main import app
        client = TestClient(app)
        print("Backend loaded successfully with ASGI TestClient.")

        # Test Health Endpoint
        print("\n[2/4] Testing API Health & Metadata Endpoints...")
        resp = client.get("/api/health")
        code = resp.status_code
        health_data = resp.json()
        print(f"  GET /api/health -> HTTP {code}: {health_data}")
        assert code == 200 and health_data.get("status") == "healthy"
        results["health_status"] = health_data.get("status")

        # Test Sample Bugs Endpoint
        resp = client.get("/api/repositories/sample-bugs")
        code = resp.status_code
        bugs_data = resp.json()
        bug_count = len(bugs_data.get("bugs", []))
        print(f"  GET /api/repositories/sample-bugs -> HTTP {code}: {bug_count} benchmark bugs returned")
        assert code == 200 and bug_count == 24
        results["sample_bugs_count"] = bug_count

        # Test Investigations List Endpoint
        resp = client.get("/api/investigations")
        code = resp.status_code
        invs_data = resp.json()
        print(f"  GET /api/investigations -> HTTP {code}: {len(invs_data)} records returned")
        assert code == 200
        results["investigations_api"] = "healthy"

        # Test Patch Preview, Apply, Rollback Endpoints
        print("\n[3/4] Testing Patch Workflow (Preview, Apply, Rollback)...")
        temp_dir = tempfile.mkdtemp(prefix="bugscope_patch_test_")
        try:
            target_file = os.path.join(temp_dir, "calc.py")
            orig_content = "def add(a, b):\n    return a - b\n"
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(orig_content)

            diff_content = (
                "--- a/calc.py\n"
                "+++ b/calc.py\n"
                "@@ -1,2 +1,2 @@\n"
                " def add(a, b):\n"
                "-    return a - b\n"
                "+    return a + b\n"
            )

            # Preview
            prev_resp = client.post(
                "/api/patches/preview",
                json={"original_code": orig_content, "diff": diff_content},
            )
            p_code = prev_resp.status_code
            prev_res = prev_resp.json()
            print(f"  POST /api/patches/preview -> HTTP {p_code}: success={prev_res.get('success')}")
            assert p_code == 200 and prev_res.get("success") is True

            # Register mock investigation for Apply
            from app.database.db import save_investigation
            from app.schemas.failure import FailureReport
            from app.schemas.fix import FixProposal
            from app.schemas.report import InvestigationReport

            inv_id = "release_test_inv_001"
            mock_rep = InvestigationReport(
                investigation_id=inv_id,
                failure_report=FailureReport(
                    error_type="LogicError",
                    message="Subtraction instead of addition",
                    category="LogicError",
                    file="calc.py",
                    line=2,
                    function="add",
                ),
                error_type="LogicError",
                message="Subtraction instead of addition",
                verdict="validated",
                fix_proposal=FixProposal(status="proposed", diff=diff_content),
                repository_path=temp_dir,
            )
            save_investigation(mock_rep)

            # Apply
            apply_resp = client.post(
                "/api/patches/apply",
                json={"investigation_id": inv_id, "target_repo_dir": temp_dir},
            )
            a_code = apply_resp.status_code
            apply_res = apply_resp.json()
            print(f"  POST /api/patches/apply -> HTTP {a_code}: success={apply_res.get('success')}")
            with open(target_file, "r", encoding="utf-8") as f:
                applied_content = f.read()
            assert "return a + b" in applied_content
            print("  Verified file on disk was patched with 'return a + b'")

            # Rollback
            rollback_resp = client.post(
                "/api/patches/rollback",
                json={"investigation_id": inv_id, "target_repo_dir": temp_dir},
            )
            r_code = rollback_resp.status_code
            rollback_res = rollback_resp.json()
            print(f"  POST /api/patches/rollback -> HTTP {r_code}: success={rollback_res.get('success')}")
            with open(target_file, "r", encoding="utf-8") as f:
                restored_content = f.read()
            assert restored_content == orig_content
            print("  Verified file on disk was rolled back exactly to original content")
            results["patch_workflow"] = "success"

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        # Docker check
        print("\n[4/4] Checking Docker Sandbox Availability...")
        from app.services.sandbox import check_docker_available
        docker_avail = check_docker_available()
        print(f"  Docker daemon available: {docker_avail}")
        results["docker_available"] = docker_avail

        print("\n=======================================================")
        print("  Runtime Verification Summary:")
        print(json.dumps(results, indent=2))
        print("=======================================================")
        return 0

    except Exception as e:
        print(f"\nVerification FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
