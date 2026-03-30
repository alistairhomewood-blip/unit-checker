"""Integration tests for the CLI (Checkpoint 4).

Tests:
    4.1 Basic invocation
    4.2 Terminal output
    4.3 JSON output
    4.4 Exit codes
    4.5 All 10 benchmarks (covered in test_benchmarks.py)
    4.7 Error handling
"""

import json
import subprocess
import sys
from pathlib import Path


FIXTURES = Path(__file__).parent.parent / "fixtures" / "python"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run the unit-checker CLI and capture output."""
    cmd = [sys.executable, "-m", "unit_checker.cli.main", "check"] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent.parent),
    )


class TestBasicInvocation:
    """4.1: unit-checker check file.py runs without error."""

    def test_correct_file_runs(self):
        result = _run_cli(str(FIXTURES / "correct_physics.py"))
        assert result.returncode == 0

    def test_violation_file_runs(self):
        result = _run_cli(str(FIXTURES / "velocity_acceleration.py"))
        # Exit code 1 for violations (not crashes)
        assert result.returncode == 1


class TestTerminalOutput:
    """4.2: Violations displayed with file, line, message."""

    def test_output_contains_error(self):
        result = _run_cli(str(FIXTURES / "velocity_acceleration.py"))
        assert "ERROR" in result.stdout
        assert "m/s" in result.stdout

    def test_correct_file_shows_no_violations(self):
        result = _run_cli(str(FIXTURES / "correct_physics.py"))
        assert "No unit violations found" in result.stdout

    def test_summary_shown(self):
        result = _run_cli(str(FIXTURES / "correct_physics.py"))
        assert "Summary:" in result.stdout


class TestJsonOutput:
    """4.3: --format json produces valid JSON."""

    def test_json_is_valid(self):
        result = _run_cli(str(FIXTURES / "velocity_acceleration.py"), "-f", "json")
        data = json.loads(result.stdout)
        assert "version" in data
        assert "violations" in data
        assert "summary" in data

    def test_json_has_violations(self):
        result = _run_cli(str(FIXTURES / "velocity_acceleration.py"), "-f", "json")
        data = json.loads(result.stdout)
        assert data["summary"]["errors"] >= 1
        assert len(data["violations"]) >= 1

    def test_json_correct_file_no_violations(self):
        result = _run_cli(str(FIXTURES / "correct_physics.py"), "-f", "json")
        data = json.loads(result.stdout)
        assert data["summary"]["errors"] == 0
        assert len(data["violations"]) == 0


class TestExitCodes:
    """4.4: Exit 0 for no violations, exit 1 for errors."""

    def test_exit_0_for_no_violations(self):
        result = _run_cli(str(FIXTURES / "correct_physics.py"))
        assert result.returncode == 0

    def test_exit_1_for_violations(self):
        result = _run_cli(str(FIXTURES / "velocity_acceleration.py"))
        assert result.returncode == 1


class TestErrorHandling:
    """4.7: Invalid file path produces helpful error message."""

    def test_nonexistent_file(self):
        result = _run_cli("/nonexistent/file.py")
        assert result.returncode == 2
