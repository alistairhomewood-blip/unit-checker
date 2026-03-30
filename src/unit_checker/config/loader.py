"""Configuration loader.

Reads .unit-checker.yaml or .unit-checker.toml from the project root.
Falls back to hardcoded SI defaults if no config file is found.

Config file search order:
    1. Explicit path passed via --config CLI option
    2. .unit-checker.yaml in the current directory or ancestors
    3. .unit-checker.toml in the current directory or ancestors
    4. pyproject.toml [tool.unit-checker] section
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class UnitCheckerConfig:
    """Configuration for unit-checker analysis.

    Attributes:
        unit_system: Default unit system (SI, CGS, natural, custom).
        annotation_format: How annotations are specified (comment, type_hint, decorator).
        strict: Whether to treat warnings as errors.
        ignore_paths: File/directory paths to skip during analysis.
        ignore_functions: Function names to skip during analysis.
        aliases: Custom unit aliases (e.g., velocity_units -> m/s).
        custom_units: Custom unit definitions mapping name to dimension string.
    """
    unit_system: str = "SI"
    annotation_format: str = "comment"
    strict: bool = False
    ignore_paths: list[str] = field(default_factory=list)
    ignore_functions: list[str] = field(default_factory=lambda: ["__repr__", "__str__"])
    aliases: dict[str, str] = field(default_factory=dict)
    custom_units: dict[str, str] = field(default_factory=dict)


def load_config(
    config_path: Optional[str] = None,
    project_root: Optional[str] = None,
) -> UnitCheckerConfig:
    """Load configuration from a config file or return defaults.

    Args:
        config_path: Explicit path to a config file.
        project_root: Directory to search for config files.
            Defaults to the current working directory.

    Returns:
        UnitCheckerConfig with loaded or default values.
    """
    if config_path:
        path = Path(config_path)
        if path.exists():
            return _load_from_file(path)
        # Explicit path specified but not found: use defaults
        return UnitCheckerConfig()

    # Search for config files
    search_dir = Path(project_root) if project_root else Path.cwd()

    # Walk up the directory tree
    current = search_dir.resolve()
    while True:
        # Check for .unit-checker.yaml
        yaml_path = current / ".unit-checker.yaml"
        if yaml_path.exists():
            return _load_from_file(yaml_path)

        # Check for .unit-checker.yml
        yml_path = current / ".unit-checker.yml"
        if yml_path.exists():
            return _load_from_file(yml_path)

        # Check for .unit-checker.toml
        toml_path = current / ".unit-checker.toml"
        if toml_path.exists():
            return _load_from_file(toml_path)

        # Check pyproject.toml for [tool.unit-checker] section
        pyproject_path = current / "pyproject.toml"
        if pyproject_path.exists():
            config = _load_from_pyproject(pyproject_path)
            if config is not None:
                return config

        # Move to parent directory
        parent = current.parent
        if parent == current:
            break  # Reached filesystem root
        current = parent

    return UnitCheckerConfig()


def _load_from_file(path: Path) -> UnitCheckerConfig:
    """Load config from a YAML or TOML file."""
    suffix = path.suffix.lower()

    if suffix in (".yaml", ".yml"):
        return _load_yaml(path)
    elif suffix == ".toml":
        return _load_toml(path)

    return UnitCheckerConfig()


def _load_yaml(path: Path) -> UnitCheckerConfig:
    """Load config from a YAML file."""
    try:
        # Use a minimal YAML parser that handles the subset we need.
        # We avoid requiring PyYAML as a hard dependency by providing
        # a simple key-value parser for flat YAML.
        data = _parse_simple_yaml(path.read_text(encoding="utf-8"))
        return _config_from_dict(data)
    except Exception:
        return UnitCheckerConfig()


def _load_toml(path: Path) -> UnitCheckerConfig:
    """Load config from a TOML file."""
    try:
        # Python 3.11+ has tomllib in stdlib
        import tomllib
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return _config_from_dict(data)
    except ImportError:
        # Fallback for older Python (should not happen with >=3.11 requirement)
        return UnitCheckerConfig()
    except Exception:
        return UnitCheckerConfig()


def _load_from_pyproject(path: Path) -> Optional[UnitCheckerConfig]:
    """Load config from pyproject.toml [tool.unit-checker] section."""
    try:
        import tomllib
        with open(path, "rb") as f:
            data = tomllib.load(f)
        tool_section = data.get("tool", {}).get("unit-checker")
        if tool_section is None:
            return None
        return _config_from_dict(tool_section)
    except (ImportError, Exception):
        return None


def _config_from_dict(data: dict[str, Any]) -> UnitCheckerConfig:
    """Create a UnitCheckerConfig from a dictionary."""
    config = UnitCheckerConfig()

    # Support both nested (defaults.unit_system) and flat (unit_system) formats
    defaults = data.get("defaults", data)

    if "unit_system" in defaults:
        config.unit_system = str(defaults["unit_system"])
    if "annotation_format" in defaults:
        config.annotation_format = str(defaults["annotation_format"])
    if "strict" in defaults:
        config.strict = bool(defaults["strict"])

    # Ignore section
    ignore = data.get("ignore", {})
    if "paths" in ignore:
        config.ignore_paths = list(ignore["paths"])
    elif "ignore_paths" in data:
        config.ignore_paths = list(data["ignore_paths"])

    if "functions" in ignore:
        config.ignore_functions = list(ignore["functions"])
    elif "ignore_functions" in data:
        config.ignore_functions = list(data["ignore_functions"])

    # Aliases section
    aliases = data.get("aliases", {})
    if isinstance(aliases, dict):
        config.aliases = {str(k): str(v) for k, v in aliases.items()}

    # Custom units section
    custom_units = data.get("custom_units", {})
    if isinstance(custom_units, dict):
        config.custom_units = {str(k): str(v) for k, v in custom_units.items()}

    return config


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse a simple YAML file (flat key-value pairs and simple nested dicts).

    This is a minimal parser that handles the subset of YAML we need
    for config files, avoiding a hard dependency on PyYAML.

    Supports:
        - key: value pairs
        - Nested sections (detected by indentation)
        - Lists with "- item" syntax
        - Comments with #
        - Quoted strings
        - Boolean values (true/false)
    """
    result: dict[str, Any] = {}
    current_dict: dict[str, Any] = result
    current_list_key: Optional[str] = None

    for line in text.splitlines():
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            continue

        # Calculate indentation
        indent = len(line) - len(line.lstrip())

        # List item
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            item = _yaml_unquote(item)
            if current_list_key and current_list_key in current_dict:
                if isinstance(current_dict[current_list_key], list):
                    current_dict[current_list_key].append(item)
            continue

        # Key-value pair
        if ":" in stripped:
            colon_pos = stripped.index(":")
            key = stripped[:colon_pos].strip()
            value_str = stripped[colon_pos + 1:].strip()

            if not value_str:
                # Section header or empty value -> start a new section
                if indent == 0:
                    result.setdefault(key, {})
                    current_dict = result[key]
                    current_list_key = None
                else:
                    # Could be a sub-key with list items following.
                    # Default to an empty list (will be filled by "- item" lines).
                    current_dict[key] = []
                    current_list_key = key
                continue

            # Parse the value
            value = _yaml_parse_value(value_str)

            if indent == 0:
                result[key] = value
                current_dict = result
            else:
                current_dict[key] = value

            # Check if this might be followed by a list
            if isinstance(value, str) and value.startswith("["):
                # Inline list: [a, b, c]
                items = value.strip("[]").split(",")
                current_dict[key] = [_yaml_unquote(item.strip()) for item in items if item.strip()]
            current_list_key = key

    return result


def _yaml_parse_value(value_str: str) -> Any:
    """Parse a YAML value string."""
    # Handle comments after values
    if " #" in value_str:
        value_str = value_str[:value_str.index(" #")].strip()

    # Remove quotes
    if (value_str.startswith('"') and value_str.endswith('"')) or \
       (value_str.startswith("'") and value_str.endswith("'")):
        return value_str[1:-1]

    # Boolean
    if value_str.lower() in ("true", "yes", "on"):
        return True
    if value_str.lower() in ("false", "no", "off"):
        return False

    # Integer
    try:
        return int(value_str)
    except ValueError:
        pass

    # Float
    try:
        return float(value_str)
    except ValueError:
        pass

    # Inline list
    if value_str.startswith("[") and value_str.endswith("]"):
        items = value_str[1:-1].split(",")
        return [_yaml_unquote(item.strip()) for item in items if item.strip()]

    return value_str


def _yaml_unquote(s: str) -> str:
    """Remove quotes from a YAML string."""
    if (s.startswith('"') and s.endswith('"')) or \
       (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s
