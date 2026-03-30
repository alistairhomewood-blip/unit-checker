"""Tests for the configuration loader.

Tests cover:
    - Default configuration
    - YAML config loading (simple parser)
    - TOML config loading
    - pyproject.toml [tool.unit-checker] section
    - Config file search (walk up directories)
    - Nested sections (defaults, ignore, aliases)
    - Boolean, string, list values
    - Missing config file falls back to defaults
"""

import tempfile
import os
from pathlib import Path

from unit_checker.config.loader import (
    UnitCheckerConfig,
    load_config,
    _parse_simple_yaml,
    _config_from_dict,
)


class TestDefaultConfig:
    def test_default_values(self):
        config = UnitCheckerConfig()
        assert config.unit_system == "SI"
        assert config.annotation_format == "comment"
        assert config.strict is False
        assert config.ignore_paths == []
        assert "__repr__" in config.ignore_functions

    def test_load_config_no_file(self):
        """Loading from a nonexistent path returns defaults."""
        config = load_config(config_path="/nonexistent/path/.unit-checker.yaml")
        assert config.unit_system == "SI"
        assert config.strict is False


class TestYamlParsing:
    def test_simple_key_value(self):
        yaml_text = """
unit_system: CGS
strict: true
annotation_format: type_hint
"""
        data = _parse_simple_yaml(yaml_text)
        assert data["unit_system"] == "CGS"
        assert data["strict"] is True
        assert data["annotation_format"] == "type_hint"

    def test_nested_sections(self):
        yaml_text = """
defaults:
  unit_system: SI
  strict: false

ignore:
  paths: [tests/, setup.py]
  functions: [__repr__, __str__]
"""
        data = _parse_simple_yaml(yaml_text)
        assert "defaults" in data
        assert data["defaults"]["unit_system"] == "SI"

    def test_list_values(self):
        yaml_text = """
ignore:
  paths:
    - tests/
    - setup.py
    - docs/
"""
        data = _parse_simple_yaml(yaml_text)
        assert "ignore" in data
        assert "paths" in data["ignore"]
        assert len(data["ignore"]["paths"]) == 3
        assert "tests/" in data["ignore"]["paths"]

    def test_comments_ignored(self):
        yaml_text = """
# This is a comment
unit_system: SI  # inline comment
"""
        data = _parse_simple_yaml(yaml_text)
        assert data["unit_system"] == "SI"

    def test_quoted_strings(self):
        yaml_text = """
unit_system: "CGS"
annotation_format: 'decorator'
"""
        data = _parse_simple_yaml(yaml_text)
        assert data["unit_system"] == "CGS"
        assert data["annotation_format"] == "decorator"


class TestConfigFromDict:
    def test_flat_dict(self):
        data = {
            "unit_system": "CGS",
            "strict": True,
            "annotation_format": "type_hint",
        }
        config = _config_from_dict(data)
        assert config.unit_system == "CGS"
        assert config.strict is True
        assert config.annotation_format == "type_hint"

    def test_nested_defaults(self):
        data = {
            "defaults": {
                "unit_system": "natural",
                "strict": True,
            },
        }
        config = _config_from_dict(data)
        assert config.unit_system == "natural"
        assert config.strict is True

    def test_ignore_section(self):
        data = {
            "ignore": {
                "paths": ["tests/", "docs/"],
                "functions": ["__init__"],
            },
        }
        config = _config_from_dict(data)
        assert config.ignore_paths == ["tests/", "docs/"]
        assert config.ignore_functions == ["__init__"]

    def test_aliases_section(self):
        data = {
            "aliases": {
                "velocity_units": "m/s",
                "force_units": "N",
            },
        }
        config = _config_from_dict(data)
        assert config.aliases["velocity_units"] == "m/s"
        assert config.aliases["force_units"] == "N"

    def test_custom_units(self):
        data = {
            "custom_units": {
                "mph": "m/s",
                "psi": "Pa",
            },
        }
        config = _config_from_dict(data)
        assert config.custom_units["mph"] == "m/s"


class TestYamlConfigFile:
    def test_load_yaml_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("unit_system: CGS\nstrict: true\n")
            f.flush()
            config = load_config(config_path=f.name)
            assert config.unit_system == "CGS"
            assert config.strict is True
        os.unlink(f.name)


class TestTomlConfigFile:
    def test_load_toml_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False
        ) as f:
            f.write('unit_system = "natural"\nstrict = true\n')
            f.flush()
            config = load_config(config_path=f.name)
            assert config.unit_system == "natural"
            assert config.strict is True
        os.unlink(f.name)


class TestConfigFileSearch:
    def test_search_finds_yaml_in_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".unit-checker.yaml"
            config_path.write_text("unit_system: CGS\n")
            config = load_config(project_root=tmpdir)
            assert config.unit_system == "CGS"

    def test_search_finds_toml_in_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".unit-checker.toml"
            config_path.write_text('unit_system = "natural"\n')
            config = load_config(project_root=tmpdir)
            assert config.unit_system == "natural"

    def test_search_finds_pyproject_section(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pyproject_path = Path(tmpdir) / "pyproject.toml"
            pyproject_path.write_text(
                '[tool.unit-checker]\nunit_system = "CGS"\nstrict = true\n'
            )
            config = load_config(project_root=tmpdir)
            assert config.unit_system == "CGS"
            assert config.strict is True

    def test_no_config_file_returns_defaults(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = load_config(project_root=tmpdir)
            assert config.unit_system == "SI"
            assert config.strict is False
