"""Universal skill schema importer and dynamic lazy capability discovery."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from orkestra.capabilities.scanner import SkillSecurityScanner
from orkestra.schemas.capability import (
    CapabilityDescriptor,
    CompetencyLevel,
    DomainType,
)
from orkestra.schemas.scanner import ScanResult


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML-like frontmatter enclosed in `---` without external dependencies."""
    pattern = r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)$"
    match = re.match(pattern, content.strip(), re.DOTALL)
    if not match:
        return {}, content

    raw_frontmatter, body = match.groups()
    meta: dict[str, Any] = {}
    current_key: str | None = None

    for line in raw_frontmatter.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # List item continuation
        if line.startswith("- "):
            item = line[2:].strip().strip("\"'")
            if current_key and isinstance(meta.get(current_key), list):
                meta[current_key].append(item)
            continue

        # Key-value pair
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()

            if not val:
                # Key begins a list or nested structure
                current_key = key
                meta[current_key] = []
            else:
                current_key = None
                val_clean = val.strip("\"'")
                if val_clean.lower() == "true":
                    meta[key] = True
                elif val_clean.lower() == "false":
                    meta[key] = False
                elif re.match(r"^\d+$", val_clean):
                    meta[key] = int(val_clean)
                elif val.startswith("[") and val.endswith("]"):
                    # Inline JSON-style array: [item1, item2]
                    items = [i.strip().strip("\"'") for i in val[1:-1].split(",") if i.strip()]
                    meta[key] = items
                else:
                    meta[key] = val_clean

    return meta, body


class SkillImporter:
    """Imports and validates external skills and capabilities into Orkestra."""

    def __init__(self, scanner: SkillSecurityScanner | None = None) -> None:
        self.scanner = scanner or SkillSecurityScanner()

    def import_skill_content(
        self,
        content: str,
        source_name: str = "<skill>",
    ) -> tuple[CapabilityDescriptor | None, ScanResult]:
        """Scan and convert raw SKILL.md content into a CapabilityDescriptor."""
        # 1. Deterministic security scan
        scan = self.scanner.scan_text(content, source_name)
        if not scan.is_safe:
            return None, scan

        # 2. Extract metadata and instruction body
        meta, body = parse_frontmatter(content)
        name = str(meta.get("name") or Path(source_name).stem)

        # Sanitize domain
        domain_raw = str(meta.get("domain", "custom")).lower()
        try:
            domain = DomainType(domain_raw)
        except ValueError:
            domain = DomainType.CUSTOM

        # Sanitize competency
        comp_raw = str(meta.get("required_competency", "basic")).lower()
        try:
            competency = CompetencyLevel(comp_raw)
        except ValueError:
            competency = CompetencyLevel.BASIC

        # Extract tools and tags
        tools = meta.get("required_tools")
        if not isinstance(tools, list):
            tools = []

        tags = meta.get("tags")
        if not isinstance(tags, list):
            tags = []

        # Description falls back to first lines of body if omitted
        description = str(meta.get("description") or "").strip()
        if not description:
            first_line = body.strip().splitlines()[0] if body.strip() else ""
            description = first_line.lstrip("# ").strip() or f"Imported skill {name}"

        descriptor = CapabilityDescriptor(
            name=name,
            domain=domain,
            description=description,
            required_competency=competency,
            required_tools=[str(t) for t in tools],
            min_model_tier=str(meta.get("min_model_tier", "standard")),
            supported_modalities=meta.get("supported_modalities", ["text"]),
            tags=[str(t) for t in tags],
        )

        return descriptor, scan

    def import_skill_file(self, path: Path) -> tuple[CapabilityDescriptor | None, ScanResult]:
        """Read and import a single SKILL.md file."""
        if not path.is_file():
            scan = self.scanner.scan_file(path)
            return None, scan

        content = path.read_text(encoding="utf-8", errors="replace")
        return self.import_skill_content(content, source_name=str(path))

    def import_directory(
        self,
        directory: Path,
        recursive: bool = True,
    ) -> list[CapabilityDescriptor]:
        """Scan a directory for SKILL.md files and import all verified capabilities."""
        if not directory.is_dir():
            return []

        pattern = "**/*.md" if recursive else "*.md"
        imported: list[CapabilityDescriptor] = []

        for file_path in directory.glob(pattern):
            if (
                file_path.name.lower() in ("skill.md", "capability.md")
                or "skill" in file_path.name.lower()
            ):
                descriptor, scan = self.import_skill_file(file_path)
                if descriptor and scan.is_safe:
                    imported.append(descriptor)

        return imported

    def find_relevant_skills(
        self,
        intent: str,
        skills: list[CapabilityDescriptor],
        top_k: int = 5,
    ) -> list[CapabilityDescriptor]:
        """Rank and select top-k skills dynamically based on task intent tokens."""
        tokens = set(re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", intent.lower()))
        scored: list[tuple[float, CapabilityDescriptor]] = []

        for skill in skills:
            score = 0.0
            # Name match
            if skill.name.lower() in intent.lower():
                score += 5.0

            # Tags match
            matching_tags = tokens.intersection({t.lower() for t in skill.tags})
            score += len(matching_tags) * 3.0

            # Description match
            desc_tokens = set(re.findall(r"\b[a-zA-Z0-9_]+\b", skill.description.lower()))
            score += len(tokens.intersection(desc_tokens)) * 1.0

            if score > 0:
                scored.append((score, skill))

        scored.sort(key=lambda s: s[0], reverse=True)
        return [s for _, s in scored[:top_k]]
