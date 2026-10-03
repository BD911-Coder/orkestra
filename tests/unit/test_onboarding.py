"""Unit tests for intelligent project onboarding director and CLI."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from orkestra.cli.main import app
from orkestra.director.onboarding import OnboardingDirector

runner = CliRunner()


class TestOnboardingDirector:
    def test_detect_python_project(self) -> None:
        director = OnboardingDirector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "pyproject.toml").write_text(
                """
[project]
name = "demo-api"
dependencies = [
    "fastapi>=0.100.0",
    "pytest>=8.0.0",
    "ruff>=0.5.0",
    "mypy>=1.0.0",
]
""",
                encoding="utf-8",
            )
            (root / "uv.lock").write_text("", encoding="utf-8")
            (root / "tests").mkdir()

            profile = director.analyze_repository(root)
            assert "python" in profile.languages
            assert "uv" in profile.package_managers
            assert "fastapi" in profile.frameworks
            assert "pytest" in profile.test_frameworks
            assert "ruff" in profile.linters_and_formatters
            assert "mypy" in profile.linters_and_formatters
            assert any("pytest" in cmd for cmd in profile.recommended_verify_commands)

            config = director.generate_config_toml(profile)
            assert "pytest" in config
            assert "adaptive_routing = true" in config

    def test_detect_typescript_project(self) -> None:
        director = OnboardingDirector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "tsconfig.json").write_text("{}", encoding="utf-8")
            pkg_data = {
                "name": "frontend-app",
                "dependencies": {"react": "^18.0.0", "next": "^14.0.0"},
                "devDependencies": {"jest": "^29.0.0", "eslint": "^8.0.0"},
                "scripts": {"test": "jest", "lint": "eslint ."},
            }
            (root / "package.json").write_text(json.dumps(pkg_data), encoding="utf-8")
            (root / "pnpm-lock.yaml").write_text("", encoding="utf-8")

            profile = director.analyze_repository(root)
            assert "typescript" in profile.languages
            assert "pnpm" in profile.package_managers
            assert "react" in profile.frameworks
            assert "next.js" in profile.frameworks
            assert "jest" in profile.test_frameworks
            assert "eslint" in profile.linters_and_formatters
            assert "pnpm test" in profile.recommended_verify_commands

    def test_detect_rust_project(self) -> None:
        director = OnboardingDirector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "Cargo.toml").write_text(
                '[package]\nname = "rust-core"\nversion = "0.1.0"', encoding="utf-8"
            )

            profile = director.analyze_repository(root)
            assert "rust" in profile.languages
            assert "cargo" in profile.package_managers
            assert "cargo test" in profile.recommended_verify_commands

    def test_detect_go_project(self) -> None:
        director = OnboardingDirector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "go.mod").write_text(
                "module github.com/user/demo\n\ngo 1.22\n", encoding="utf-8"
            )

            profile = director.analyze_repository(root)
            assert "go" in profile.languages
            assert "go" in profile.package_managers
            assert "go test" in profile.test_frameworks
            assert "go test ./..." in profile.recommended_verify_commands

    def test_detect_fallback_unmarked_project(self) -> None:
        director = OnboardingDirector()
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            profile = director.analyze_repository(root)
            assert profile.languages == []
            assert profile.recommended_verify_commands == ["git status"]


class TestOnboardCLI:
    def test_onboard_preview_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "test-pkg"\ndependencies = ["pytest"]',
                encoding="utf-8",
            )
            result = runner.invoke(app, ["onboard", "--path", str(root)])
            assert result.exit_code == 0
            assert "Detected Project Profile" in result.stdout
            assert "python" in result.stdout

    def test_onboard_write_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "Cargo.toml").write_text(
                '[package]\nname = "cargo-pkg"',
                encoding="utf-8",
            )
            result = runner.invoke(app, ["onboard", "--path", str(root), "--write"])
            assert result.exit_code == 0
            assert "Successfully written configuration" in result.stdout
            assert (root / ".orkestra" / "config.toml").is_file()
