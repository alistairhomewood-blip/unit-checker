"""Integration tests for Phase 3 CLI features.

Tests:
    - C++ file analysis via CLI
    - Fortran file analysis via CLI
    - SARIF output format
    - Language auto-detection from file extension
    - --language flag
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

PYTHON_FIXTURES = Path(__file__).parent.parent / "fixtures" / "python"
CPP_FIXTURES = Path(__file__).parent.parent / "fixtures" / "cpp"
FORTRAN_FIXTURES = Path(__file__).parent.parent / "fixtures" / "fortran"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run the unit-checker CLI and capture output."""
    cmd = [sys.executable, "-m", "unit_checker.cli.main", "check"] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent.parent),
    )


# --- C++ via CLI ---

class TestCppCli:
    def test_correct_cpp_file(self):
        fixture = CPP_FIXTURES / "correct_physics.cpp"
        if not fixture.exists():
            pytest.skip("Fixture not found")
        result = _run_cli(str(fixture))
        assert result.returncode == 0

    def test_violation_cpp_file(self):
        fixture = CPP_FIXTURES / "velocity_acceleration.cpp"
        if not fixture.exists():
            pytest.skip("Fixture not found")
        result = _run_cli(str(fixture))
        assert result.returncode == 1

    def test_cpp_json_output(self):
        fixture = CPP_FIXTURES / "velocity_acceleration.cpp"
        if not fixture.exists():
            pytest.skip("Fixture not found")
        result = _run_cli(str(fixture), "-f", "json")
        data = json.loads(result.stdout)
        assert data["summary"]["errors"] >= 1


# --- Fortran via CLI ---

class TestFortranCli:
    def test_correct_fortran_file(self):
        fixture = FORTRAN_FIXTURES / "correct_physics.f90"
        if not fixture.exists():
            pytest.skip("Fixture not found")
        result = _run_cli(str(fixture))
        assert result.returncode == 0

    def test_violation_fortran_file(self):
        fixture = FORTRAN_FIXTURES / "velocity_acceleration.f90"
        if not fixture.exists():
            pytest.skip("Fixture not found")
        result = _run_cli(str(fixture))
        assert result.returncode == 1

    def test_fortran_json_output(self):
        fixture = FORTRAN_FIXTURES / "velocity_acceleration.f90"
        if not fixture.exists():
            pytest.skip("Fixture not found")
        result = _run_cli(str(fixture), "-f", "json")
        data = json.loads(result.stdout)
        assert data["summary"]["errors"] >= 1

    def test_fortran_energy_violation(self):
        fixture = FORTRAN_FIXTURES / "energy_conservation.f90"
        if not fixture.exists():
            pytest.skip("Fixture not found")
        result = _run_cli(str(fixture), "-f", "json")
        data = json.loads(result.stdout)
        assert data["summary"]["errors"] >= 1


# --- SARIF Output ---

class TestSarifCli:
    def test_sarif_output_is_valid_json(self):
        fixture = PYTHON_FIXTURES / "velocity_acceleration.py"
        result = _run_cli(str(fixture), "-f", "sarif")
        data = json.loads(result.stdout)
        assert data["version"] == "2.1.0"

    def test_sarif_has_results(self):
        fixture = PYTHON_FIXTURES / "velocity_acceleration.py"
        result = _run_cli(str(fixture), "-f", "sarif")
        data = json.loads(result.stdout)
        results = data["runs"][0]["results"]
        assert len(results) >= 1

    def test_sarif_correct_file_empty_results(self):
        fixture = PYTHON_FIXTURES / "correct_physics.py"
        result = _run_cli(str(fixture), "-f", "sarif")
        data = json.loads(result.stdout)
        results = data["runs"][0]["results"]
        assert len(results) == 0

    def test_sarif_cpp_file(self):
        fixture = CPP_FIXTURES / "velocity_acceleration.cpp"
        if not fixture.exists():
            pytest.skip("Fixture not found")
        result = _run_cli(str(fixture), "-f", "sarif")
        data = json.loads(result.stdout)
        results = data["runs"][0]["results"]
        assert len(results) >= 1

    def test_sarif_fortran_file(self):
        fixture = FORTRAN_FIXTURES / "velocity_acceleration.f90"
        if not fixture.exists():
            pytest.skip("Fixture not found")
        result = _run_cli(str(fixture), "-f", "sarif")
        data = json.loads(result.stdout)
        results = data["runs"][0]["results"]
        assert len(results) >= 1


# --- Language Detection ---

class TestLanguageDetection:
    def test_auto_detect_python(self):
        fixture = PYTHON_FIXTURES / "correct_physics.py"
        result = _run_cli(str(fixture))
        assert result.returncode == 0

    def test_auto_detect_cpp(self):
        fixture = CPP_FIXTURES / "correct_physics.cpp"
        if not fixture.exists():
            pytest.skip("Fixture not found")
        result = _run_cli(str(fixture))
        assert result.returncode == 0

    def test_auto_detect_fortran(self):
        fixture = FORTRAN_FIXTURES / "correct_physics.f90"
        if not fixture.exists():
            pytest.skip("Fixture not found")
        result = _run_cli(str(fixture))
        assert result.returncode == 0

    def test_explicit_language_flag(self):
        fixture = PYTHON_FIXTURES / "correct_physics.py"
        result = _run_cli(str(fixture), "--language", "python")
        assert result.returncode == 0


# --- Cross-Language Benchmarks via CLI ---

class TestCrossLanguageBenchmarks:
    """Verify that the same physics error is caught in all three languages."""

    def test_velocity_acceleration_all_languages(self):
        for lang, fixtures_dir in [
            ("python", PYTHON_FIXTURES),
            ("cpp", CPP_FIXTURES),
            ("fortran", FORTRAN_FIXTURES),
        ]:
            fixture = fixtures_dir / "velocity_acceleration"
            if lang == "python":
                fixture = fixture.with_suffix(".py")
            elif lang == "cpp":
                fixture = fixture.with_suffix(".cpp")
            else:
                fixture = fixture.with_suffix(".f90")

            if not fixture.exists():
                continue

            result = _run_cli(str(fixture), "-f", "json")
            data = json.loads(result.stdout)
            assert data["summary"]["errors"] >= 1, (
                f"{lang}: expected at least 1 error in {fixture.name}"
            )
