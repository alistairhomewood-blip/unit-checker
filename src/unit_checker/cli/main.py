"""Main CLI entry point for unit-checker.

Usage:
    unit-checker check <file> [options]
    unit-checker check example.py --format json
    unit-checker check example.py --verbose
"""

from __future__ import annotations

import typer

from unit_checker.cli.commands import check_command, version_callback

app = typer.Typer(
    name="unit-checker",
    help="Static unit consistency analysis for scientific code.",
    add_completion=False,
)

# Register subcommands
app.command("check", help="Analyze a source file for unit consistency violations.")(check_command)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version and exit.",
        is_eager=True,
        callback=version_callback,
    ),
) -> None:
    """Static unit consistency analysis for scientific code."""
    if ctx.invoked_subcommand is None:
        ctx.get_help()
        raise typer.Exit()


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
