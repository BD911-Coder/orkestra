"""Intelligent project onboarding and capability auto-detection engine."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ProjectProfile(BaseModel):
    """Detected cultural and technical profile of a software project."""

    model_config = ConfigDict(extra="forbid")

    project_name: str
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    test_frameworks: list[str] = Field(default_factory=list)
    linters_and_formatters: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    recommended_verify_commands: list[str] = Field(default_factory=list)
    recommended_capabilities: list[str] = Field(default_factory=list)


class OnboardingDirector:
    """Heuristic engine analyzing repositories and synthesizing optimal Orkestra configurations."""

    def analyze_repository(self, root: Path) -> ProjectProfile:
        """Analyze repository markers, manifests, and configs to infer project profile."""
        name = root.resolve().name or "unnamed-project"

        languages: set[str] = set()
        frameworks: set[str] = set()
        test_frameworks: set[str] = set()
        linters: set[str] = set()
        package_managers: set[str] = set()
        verify_cmds: list[str] = []
        capabilities: set[str] = {
            "software.architecture",
            "software.implementation",
            "software.debugging",
            "software.code_review",
        }

        # 1. Python detection
        if (
            (root / "pyproject.toml").exists()
            or (root / "setup.py").exists()
            or (root / "requirements.txt").exists()
        ):
            languages.add("python")
            if (root / "uv.lock").exists():
                package_managers.add("uv")
            elif (root / "poetry.lock").exists():
                package_managers.add("poetry")
            elif (root / "Pipfile.lock").exists():
                package_managers.add("pipenv")
            else:
                package_managers.add("pip")

            # Check contents of pyproject.toml
            pyproject_path = root / "pyproject.toml"
            if pyproject_path.exists():
                text = pyproject_path.read_text(encoding="utf-8", errors="replace").lower()
                if "fastapi" in text:
                    frameworks.add("fastapi")
                if "django" in text:
                    frameworks.add("django")
                if "flask" in text:
                    frameworks.add("flask")
                if "pytest" in text or (root / "tests").exists():
                    test_frameworks.add("pytest")
                if "ruff" in text:
                    linters.add("ruff")
                if "mypy" in text:
                    linters.add("mypy")
                if "black" in text:
                    linters.add("black")

            pm = "uv run " if "uv" in package_managers else ""
            if "pytest" in test_frameworks or (root / "tests").exists():
                verify_cmds.append(f"{pm}pytest -q")
            if "ruff" in linters:
                verify_cmds.append(f"{pm}ruff check .")

        # 2. JavaScript / TypeScript detection
        pkg_json = root / "package.json"
        if pkg_json.exists():
            if (root / "tsconfig.json").exists():
                languages.add("typescript")
            else:
                languages.add("javascript")

            if (root / "pnpm-lock.yaml").exists():
                package_managers.add("pnpm")
                pm_exec = "pnpm"
            elif (root / "yarn.lock").exists():
                package_managers.add("yarn")
                pm_exec = "yarn"
            elif (root / "bun.lockb").exists():
                package_managers.add("bun")
                pm_exec = "bun"
            else:
                package_managers.add("npm")
                pm_exec = "npm"

            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8", errors="replace"))
                deps = {
                    **data.get("dependencies", {}),
                    **data.get("devDependencies", {}),
                }
                if "react" in deps:
                    frameworks.add("react")
                if "next" in deps:
                    frameworks.add("next.js")
                if "vue" in deps:
                    frameworks.add("vue")
                if "jest" in deps:
                    test_frameworks.add("jest")
                if "vitest" in deps:
                    test_frameworks.add("vitest")
                if "eslint" in deps:
                    linters.add("eslint")
                if "prettier" in deps:
                    linters.add("prettier")

                scripts = data.get("scripts", {})
                if "test" in scripts and f"{pm_exec} test" not in verify_cmds:
                    verify_cmds.append(f"{pm_exec} test")
                if "lint" in scripts and f"{pm_exec} run lint" not in verify_cmds:
                    verify_cmds.append(f"{pm_exec} run lint")
            except (json.JSONDecodeError, OSError):
                pass

        # 3. Rust detection
        if (root / "Cargo.toml").exists():
            languages.add("rust")
            package_managers.add("cargo")
            test_frameworks.add("cargo test")
            linters.add("clippy")
            verify_cmds.append("cargo test")
            verify_cmds.append("cargo clippy -- -D warnings")

        # 4. Go detection
        if (root / "go.mod").exists():
            languages.add("go")
            package_managers.add("go")
            test_frameworks.add("go test")
            linters.add("golangci-lint")
            verify_cmds.append("go test ./...")

        # Fallback if no specific commands found
        if not verify_cmds:
            verify_cmds.append("git status")

        return ProjectProfile(
            project_name=name,
            languages=sorted(languages),
            frameworks=sorted(frameworks),
            test_frameworks=sorted(test_frameworks),
            linters_and_formatters=sorted(linters),
            package_managers=sorted(package_managers),
            recommended_verify_commands=verify_cmds,
            recommended_capabilities=sorted(capabilities),
        )

    def generate_config_toml(self, profile: ProjectProfile) -> str:
        """Synthesize an optimized, production-grade .orkestra/config.toml."""
        verify_list = ",\n".join(f'    "{cmd}"' for cmd in profile.recommended_verify_commands)

        lines = [
            f"# Orkestra configuration auto-generated for {profile.project_name}",
            'version = "1"',
            "",
            "[project]",
            f'name = "{profile.project_name}"',
            f"languages = {json.dumps(profile.languages)}",
            f"frameworks = {json.dumps(profile.frameworks)}",
            "",
            "[verify]",
            "commands = [",
            verify_list,
            "]",
            'binding = "required"',
            "",
            "[policy]",
            'preset = "strict"',
            "allow_subagents = true",
            "allow_agent_teams = true",
            "max_nested_workers = 4",
            "max_total_concurrent_agents = 8",
            "max_subagent_depth = 2",
            "",
            "[routing]",
            "adaptive_routing = true",
            "quality_floor_enforcement = true",
            'default_profile = "balanced"',
            "",
            "[director]",
            'provider = "claude"',
            'model = "auto"',
            "",
        ]
        return "\n".join(lines)
