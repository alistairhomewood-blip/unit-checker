"""Terminal output formatter.

Uses Rich library for colored, structured output showing:
    - File path and line number
    - Violation type and severity
    - Physics-language error messages
    - Code snippet with unit annotations
    - Inference chain (in verbose mode)
    - Summary statistics
"""

from __future__ import annotations

from typing import Optional

from rich.console import Console

from unit_checker import __version__
from unit_checker.core.unit_algebra import UnitVector
from unit_checker.core.unit_registry import UnitRegistry, default_registry
from unit_checker.models.violations import Violation, ViolationSeverity, ViolationType
from unit_checker.inference.propagator import PropagationResult


class TerminalFormatter:
    """Formats analysis results for terminal display using Rich."""

    def __init__(
        self,
        console: Optional[Console] = None,
        verbose: bool = False,
        registry: Optional[UnitRegistry] = None,
    ) -> None:
        self.console = console or Console()
        self.verbose = verbose
        self.registry = registry or default_registry
        self._source_cache: dict[str, list[str]] = {}

    def format_result(
        self,
        result: PropagationResult,
        file_path: str,
        source: Optional[str] = None,
    ) -> None:
        """Format and print the full analysis result."""
        if source:
            self._source_cache[file_path] = source.splitlines()

        # Header
        self.console.print()
        self.console.print(
            f"[bold]unit-checker v{__version__}[/bold] -- analyzing [cyan]{file_path}[/cyan]"
        )
        self.console.print()

        if not result.violations:
            self.console.print("[bold green]No unit violations found.[/bold green]")
        else:
            for violation in result.violations:
                self._format_violation(violation)

        # Summary
        self._format_summary(result, file_path)

    def _format_violation(self, violation: Violation) -> None:
        """Format a single violation."""
        # Severity badge
        if violation.severity == ViolationSeverity.ERROR:
            badge = "[bold red]  ERROR [/bold red]"
        elif violation.severity == ViolationSeverity.WARNING:
            badge = "[bold yellow]WARNING[/bold yellow]"
        else:
            badge = "[bold blue]  INFO [/bold blue]"

        # Location
        loc_str = str(violation.location)

        self.console.print(f"  {badge} [dim]{loc_str}[/dim]")

        # Violation type description
        type_desc = _violation_type_description(violation.violation_type)
        self.console.print(f"  [bold]{type_desc}[/bold]")
        self.console.print()

        # Source code context
        from rich.markup import escape
        if violation.source_line:
            line_num = violation.location.line
            self.console.print(f"    [dim]{line_num:>4}[/dim] | {escape(violation.source_line)}")
        elif violation.location.file in self._source_cache:
            lines = self._source_cache[violation.location.file]
            line_idx = violation.location.line - 1
            # Show context: 1 line before, the violation line, 0 after
            start = max(0, line_idx - 1)
            end = min(len(lines), line_idx + 1)
            for i in range(start, end):
                prefix = ">>>" if i == line_idx else "   "
                self.console.print(f"    {prefix} [dim]{i+1:>4}[/dim] | {escape(lines[i])}")

        self.console.print()

        # Expected vs actual
        if violation.expected_unit and violation.actual_unit:
            expected_str = self._format_unit_display(violation.expected_unit)
            actual_str = self._format_unit_display(violation.actual_unit)
            self.console.print(f"  Expected: [green]{expected_str}[/green]")
            self.console.print(f"  Got:      [red]{actual_str}[/red]")
            self.console.print()

        # Physics-language message (escape Rich markup in unit strings)
        from rich.markup import escape
        self.console.print(f"  {escape(violation.message)}")
        self.console.print()

        # Inference chain (verbose mode)
        if self.verbose and (violation.inference_chain_expected or violation.inference_chain_actual):
            self._format_inference_chains(violation)

        self.console.print("  " + "-" * 50)
        self.console.print()

    def _format_inference_chains(self, violation: Violation) -> None:
        """Format the inference chains that led to the violation."""
        from rich.markup import escape

        if violation.inference_chain_expected:
            self.console.print("  [dim]Inference chain (expected):[/dim]")
            for step in violation.inference_chain_expected:
                unit_str = self._format_unit_display(step.unit)
                var_display = _clean_var_name(step.variable)
                reason = escape(step.reason)
                self.console.print(
                    f"    [dim]{step.location}[/dim]: "
                    f"'{var_display}' is \\[{escape(unit_str)}] -- {reason}"
                )
            self.console.print()

        if violation.inference_chain_actual:
            self.console.print("  [dim]Inference chain (actual):[/dim]")
            for step in violation.inference_chain_actual:
                unit_str = self._format_unit_display(step.unit)
                var_display = _clean_var_name(step.variable)
                reason = escape(step.reason)
                self.console.print(
                    f"    [dim]{step.location}[/dim]: "
                    f"'{var_display}' is \\[{escape(unit_str)}] -- {reason}"
                )
            self.console.print()

    def _format_summary(self, result: PropagationResult, file_path: str) -> None:
        """Print summary statistics."""
        self.console.print()
        self.console.print("  " + "=" * 50)

        num_errors = sum(1 for v in result.violations if v.severity == ViolationSeverity.ERROR)
        num_warnings = sum(1 for v in result.violations if v.severity == ViolationSeverity.WARNING)
        num_inferred = len(result.inferred_units)
        num_unknown = len(result.unknown_variables)
        total_vars = num_inferred + num_unknown

        parts = []
        if num_errors:
            parts.append(f"[bold red]{num_errors} error{'s' if num_errors != 1 else ''}[/bold red]")
        if num_warnings:
            parts.append(f"[bold yellow]{num_warnings} warning{'s' if num_warnings != 1 else ''}[/bold yellow]")
        if not parts:
            parts.append("[bold green]0 errors[/bold green]")

        summary_parts = ", ".join(parts)
        self.console.print(
            f"\n  Summary: {summary_parts}, "
            f"{total_vars} variables analyzed, "
            f"{num_inferred} units inferred."
        )

        if self.verbose and result.unknown_variables:
            # Filter out temp variables for display
            user_unknowns = [
                v for v in result.unknown_variables
                if "__temp_" not in v and "__return_" not in v and "__attr_" not in v
            ]
            if user_unknowns:
                self.console.print(f"\n  [dim]Variables with unknown units: {len(user_unknowns)}[/dim]")
                for var in sorted(user_unknowns)[:10]:
                    self.console.print(f"    [dim]- {_clean_var_name(var)}[/dim]")
                if len(user_unknowns) > 10:
                    self.console.print(f"    [dim]... and {len(user_unknowns) - 10} more[/dim]")

        self.console.print()

    def _format_unit_display(self, unit: UnitVector) -> str:
        """Format a unit for display, using named units when possible."""
        name = self.registry.get_name(unit)
        base_str = unit.to_unit_string()
        if name and name != base_str:
            return f"{name} = {base_str}"
        return base_str


def _violation_type_description(vtype: ViolationType) -> str:
    """Get a human-readable description of a violation type."""
    descriptions = {
        ViolationType.ADDITION_MISMATCH: "Unit mismatch in addition/subtraction",
        ViolationType.ASSIGNMENT_MISMATCH: "Conflicting units in assignment",
        ViolationType.FUNCTION_ARG_MISMATCH: "Unit mismatch in function argument",
        ViolationType.RETURN_MISMATCH: "Unit mismatch in return value",
        ViolationType.COMPARISON_MISMATCH: "Unit mismatch in comparison",
        ViolationType.CONFLICTING_CONSTRAINTS: "Conflicting unit constraints",
    }
    return descriptions.get(vtype, "Unit violation")


def _clean_var_name(qualified: str) -> str:
    """Clean up a qualified variable name for display."""
    if "::" in qualified:
        parts = qualified.split("::")
        name = parts[-1]
        scope = parts[0]
    else:
        name = qualified
        scope = ""

    # Clean up internal names
    if name.startswith("__temp_"):
        return "<expression>"
    if name.startswith("__return_"):
        func = name[9:].rstrip("_")
        return f"return value of {func}"
    if name.startswith("__attr_"):
        return "<attribute>"

    if scope and scope != "global":
        scope_clean = scope.replace("local:", "").replace("param:", "")
        return f"{name} (in {scope_clean})"
    return name
