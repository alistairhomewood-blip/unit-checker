"""CLI subcommands for unit-checker.

The main command is `check`, which analyzes a source file for unit violations.
Supports Python, C++, and Fortran.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from unit_checker.core.unit_registry import default_registry
from unit_checker.parsers.common.ir import IRModule
from unit_checker.inference.constraint_builder import ConstraintBuilder
from unit_checker.inference.propagator import ConstraintPropagator
from unit_checker.inference.conflict_resolver import enrich_violation
from unit_checker.output.terminal import TerminalFormatter
from unit_checker.output.json_output import format_json
from unit_checker.output.sarif import format_sarif
from unit_checker.config.loader import load_config


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        from unit_checker import __version__
        import typer
        typer.echo(f"unit-checker v{__version__}")
        raise typer.Exit()


class OutputFormat(str, Enum):
    """Output format for the analysis report."""
    terminal = "terminal"
    json = "json"
    sarif = "sarif"


class Language(str, Enum):
    """Source language for analysis."""
    auto = "auto"
    python = "python"
    cpp = "cpp"
    fortran = "fortran"


# File extension to language mapping
_EXTENSION_MAP: dict[str, Language] = {
    ".py": Language.python,
    ".pyw": Language.python,
    ".cpp": Language.cpp,
    ".cxx": Language.cpp,
    ".cc": Language.cpp,
    ".c": Language.cpp,
    ".hpp": Language.cpp,
    ".hxx": Language.cpp,
    ".h": Language.cpp,
    ".f90": Language.fortran,
    ".f95": Language.fortran,
    ".f03": Language.fortran,
    ".f08": Language.fortran,
    ".f": Language.fortran,
    ".for": Language.fortran,
    ".fpp": Language.fortran,
}


def _detect_language(file_path: Path) -> Language:
    """Detect language from file extension."""
    suffix = file_path.suffix.lower()
    return _EXTENSION_MAP.get(suffix, Language.python)


def _parse_source(source: str, file_path: str, language: Language) -> IRModule:
    """Parse source code using the appropriate parser."""
    if language == Language.python:
        from unit_checker.parsers.python_parser.parser import parse_python
        return parse_python(source, file_path)
    elif language == Language.cpp:
        from unit_checker.parsers.cpp_parser.parser import parse_cpp
        return parse_cpp(source, file_path)
    elif language == Language.fortran:
        from unit_checker.parsers.fortran_parser.parser import parse_fortran
        return parse_fortran(source, file_path)
    else:
        from unit_checker.parsers.python_parser.parser import parse_python
        return parse_python(source, file_path)


def check_command(
    file: Path = typer.Argument(
        ...,
        help="Source file to analyze (Python, C++, or Fortran).",
        exists=True,
        readable=True,
    ),
    format: OutputFormat = typer.Option(
        OutputFormat.terminal,
        "--format", "-f",
        help="Output format (terminal, json, sarif).",
    ),
    language: Language = typer.Option(
        Language.auto,
        "--language", "-l",
        help="Source language (auto-detect from extension if not specified).",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show full inference chains.",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Treat warnings as errors.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet", "-q",
        help="Only show errors, no warnings.",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config", "-c",
        help="Path to configuration file (.unit-checker.yaml or .unit-checker.toml).",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Write output to file instead of stdout.",
    ),
) -> None:
    """Analyze a source file for unit consistency violations."""
    console = Console(stderr=True)

    # Load configuration
    config_path = str(config) if config else None
    project_root = str(file.parent)
    cfg = load_config(config_path=config_path, project_root=project_root)

    # Override strict from config if not set on CLI
    if cfg.strict and not strict:
        strict = True

    try:
        source = file.read_text(encoding="utf-8")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] Cannot read file: {e}")
        raise typer.Exit(code=2)

    file_path = str(file)

    # Detect language
    if language == Language.auto:
        language = _detect_language(file)

    # Stage 1: Parse source to IR
    try:
        ir_module = _parse_source(source, file_path, language)
    except SyntaxError as e:
        console.print(f"[bold red]Syntax error:[/bold red] {e}")
        raise typer.Exit(code=2)
    except Exception as e:
        console.print(f"[bold red]Parse error:[/bold red] {e}")
        raise typer.Exit(code=2)

    # Stage 2: Build constraints from IR
    builder = ConstraintBuilder(registry=default_registry)
    constraints, known_units = builder.build(ir_module, source=source)

    # Stage 3: Propagate constraints
    propagator = ConstraintPropagator()
    result = propagator.propagate(constraints, known_units)

    # Merge builder-level violations (conflicting annotations, unparseable units)
    result.violations = builder.violations + result.violations

    # Filter by quiet mode
    if quiet:
        from unit_checker.models.violations import ViolationSeverity
        result.violations = [v for v in result.violations if v.severity == ViolationSeverity.ERROR]

    # Promote warnings to errors in strict mode
    if strict:
        from unit_checker.models.violations import ViolationSeverity
        for v in result.violations:
            if v.severity == ViolationSeverity.WARNING:
                v.severity = ViolationSeverity.ERROR

    # Stage 4: Enrich violations with context
    source_lines = {file_path: source.splitlines()}
    for violation in result.violations:
        enrich_violation(violation, result, registry=default_registry, source_lines=source_lines)

    # Stage 5: Output results
    output_text = ""
    if format == OutputFormat.json:
        output_text = format_json(result, file_path, registry=default_registry)
    elif format == OutputFormat.sarif:
        output_text = format_sarif(result, file_path, registry=default_registry)

    if output_text:
        if output:
            output.write_text(output_text, encoding="utf-8")
        else:
            print(output_text)
    else:
        # Terminal format
        formatter = TerminalFormatter(
            console=Console(),
            verbose=verbose,
            registry=default_registry,
        )
        formatter.format_result(result, file_path, source=source)

    # Exit code: 0 for no violations, 1 for errors
    has_errors = any(
        v.severity.value == "error" for v in result.violations
    )
    if has_errors:
        raise typer.Exit(code=1)
