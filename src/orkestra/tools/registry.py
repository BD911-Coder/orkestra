"""Authoritative Tool Registry managing descriptors, effect-class gating, and telemetry."""

from __future__ import annotations

from typing import Any

from orkestra.schemas.common import utc_now
from orkestra.schemas.tools import (
    EFFECT_CLASS_RANKS,
    EffectClass,
    ToolDescriptor,
    ToolTelemetry,
)


def _get_standard_tools() -> list[ToolDescriptor]:
    return [
        # SE0: Read-only observation / inspection
        ToolDescriptor(
            name="view_file",
            description="Inspect the contents of a file in the workspace.",
            effect_class=EffectClass.SE0_READ_ONLY,
            timeout_seconds=10.0,
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path to view"},
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (1-indexed)",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number (inclusive)",
                    },
                },
                "required": ["path"],
            },
            tags=["read", "file", "inspect"],
        ),
        ToolDescriptor(
            name="search_code",
            description="Search for symbols or text occurrences across workspace files.",
            effect_class=EffectClass.SE0_READ_ONLY,
            timeout_seconds=15.0,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term or regex pattern"},
                    "file_pattern": {"type": "string", "description": "File glob filter"},
                },
                "required": ["query"],
            },
            tags=["search", "grep", "symbols"],
        ),
        ToolDescriptor(
            name="web_search",
            description="Perform a web query for external documentation or research data.",
            effect_class=EffectClass.SE0_READ_ONLY,
            timeout_seconds=20.0,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query keywords"},
                },
                "required": ["query"],
            },
            tags=["web", "search", "docs"],
        ),
        ToolDescriptor(
            name="read_url",
            description="Fetch textual content from a web URL for research synthesis.",
            effect_class=EffectClass.SE0_READ_ONLY,
            timeout_seconds=25.0,
            parameters_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target HTTP/HTTPS URL"},
                },
                "required": ["url"],
            },
            tags=["web", "fetch", "docs"],
        ),
        # SE1: Reversible local write
        ToolDescriptor(
            name="write_file",
            description="Write full code or document content to a file in workspace.",
            effect_class=EffectClass.SE1_LOCAL_WRITE,
            timeout_seconds=15.0,
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Target relative file path"},
                    "content": {"type": "string", "description": "Complete text content to write"},
                },
                "required": ["path", "content"],
            },
            tags=["write", "file", "create"],
        ),
        ToolDescriptor(
            name="replace_file_content",
            description="Replace targeted block of text within an existing file.",
            effect_class=EffectClass.SE1_LOCAL_WRITE,
            timeout_seconds=15.0,
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Target relative file path"},
                    "target_content": {"type": "string", "description": "Exact text to find"},
                    "replacement_content": {"type": "string", "description": "Replacement text"},
                },
                "required": ["path", "target_content", "replacement_content"],
            },
            tags=["edit", "file", "refactor"],
        ),
        # SE2: Local process / filesystem mutation
        ToolDescriptor(
            name="run_command",
            description="Execute a shell command within the workspace directory.",
            effect_class=EffectClass.SE2_MUTATION,
            timeout_seconds=60.0,
            parameters_schema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command line to execute"},
                },
                "required": ["command"],
            },
            tags=["command", "exec", "shell"],
        ),
        ToolDescriptor(
            name="run_tests",
            description="Execute automated test runner and return structured test outcome.",
            effect_class=EffectClass.SE2_MUTATION,
            timeout_seconds=120.0,
            parameters_schema={
                "type": "object",
                "properties": {
                    "test_path": {"type": "string", "description": "Specific test path or pattern"},
                },
            },
            tags=["test", "verify", "quality"],
        ),
        ToolDescriptor(
            name="git_commit",
            description="Record staged modifications to local git history.",
            effect_class=EffectClass.SE2_MUTATION,
            timeout_seconds=20.0,
            parameters_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Commit message adhering to convention",
                    },
                },
                "required": ["message"],
            },
            tags=["git", "vcs", "commit"],
        ),
        # SE3: Append-only remote evidence publication
        ToolDescriptor(
            name="git_push",
            description="Publish verified local commits to authenticated remote repository.",
            effect_class=EffectClass.SE3_REMOTE_EVIDENCE,
            timeout_seconds=30.0,
            requires_permission=True,
            allowed_roles=["director"],
            parameters_schema={
                "type": "object",
                "properties": {
                    "remote": {"type": "string", "description": "Git remote name"},
                    "branch": {"type": "string", "description": "Branch name to push"},
                },
                "required": ["branch"],
            },
            tags=["git", "vcs", "push", "remote"],
        ),
        # SE4: Economic / Counterparty / Critical operations
        ToolDescriptor(
            name="cloud_deploy",
            description="Trigger cloud infrastructure deployment or financial transaction.",
            effect_class=EffectClass.SE4_EXTERNAL_CRITICAL,
            timeout_seconds=180.0,
            requires_permission=True,
            allowed_roles=["director"],
            tags=["deploy", "production", "critical"],
        ),
    ]


class ToolRegistry:
    """Central catalog and gatekeeper for tool invocation, permissions, and telemetry."""

    def __init__(self, include_defaults: bool = True) -> None:
        self._tools: dict[str, ToolDescriptor] = {}
        self._telemetry: dict[str, ToolTelemetry] = {}
        if include_defaults:
            for tool in _get_standard_tools():
                self.register(tool)

    def register(self, tool: ToolDescriptor) -> None:
        """Register or update a tool descriptor."""
        self._tools[tool.name] = tool
        if tool.name not in self._telemetry:
            self._telemetry[tool.name] = ToolTelemetry(tool_name=tool.name)

    def get(self, name: str) -> ToolDescriptor | None:
        """Retrieve tool descriptor by name."""
        return self._tools.get(name)

    def list_tools(self, effect_class: EffectClass | None = None) -> list[ToolDescriptor]:
        """List all tools, optionally filtered by side-effect class."""
        if effect_class is not None:
            return [t for t in self._tools.values() if t.effect_class == effect_class]
        return sorted(self._tools.values(), key=lambda t: t.name)

    def authorize(
        self,
        tool_name: str,
        agent_role: str,
        max_allowed_effect: EffectClass = EffectClass.SE2_MUTATION,
    ) -> tuple[bool, str]:
        """Verify whether an agent role is authorized to execute a tool under the effect ceiling.

        Returns (allowed, reason).
        """
        tool = self._tools.get(tool_name)
        if not tool:
            return False, f"Tool '{tool_name}' is not registered in ToolRegistry"

        # Check role allowance
        if agent_role not in tool.allowed_roles:
            return (
                False,
                f"Agent role '{agent_role}' is not in allowed roles "
                f"{tool.allowed_roles} for tool '{tool_name}'",
            )

        # Check effect class ceiling
        tool_rank = EFFECT_CLASS_RANKS[tool.effect_class]
        ceiling_rank = EFFECT_CLASS_RANKS[max_allowed_effect]
        if tool_rank > ceiling_rank:
            return (
                False,
                f"Tool effect '{tool.effect_class.value}' (rank {tool_rank}) "
                f"exceeds maximum permitted effect ceiling "
                f"'{max_allowed_effect.value}' (rank {ceiling_rank})",
            )

        return True, "Authorized"

    def record_invocation(self, tool_name: str, success: bool, latency_ms: float) -> None:
        """Record telemetry for a tool execution."""
        if tool_name not in self._telemetry:
            self._telemetry[tool_name] = ToolTelemetry(tool_name=tool_name)

        tel = self._telemetry[tool_name]
        tel.invocations += 1
        if success:
            tel.successes += 1
        else:
            tel.failures += 1
        tel.total_latency_ms += latency_ms
        tel.last_invoked = utc_now()

    def get_telemetry(self, tool_name: str) -> ToolTelemetry | None:
        """Retrieve execution telemetry for a tool."""
        return self._telemetry.get(tool_name)

    def list_all_telemetry(self) -> list[ToolTelemetry]:
        """List telemetry for all registered tools."""
        return list(self._telemetry.values())

    def export_openai_tools(self) -> list[dict[str, Any]]:
        """Export tool definitions conforming to the OpenAI function calling schema."""
        tools: list[dict[str, Any]] = []
        for t in sorted(self._tools.values(), key=lambda x: x.name):
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters_schema or {"type": "object", "properties": {}},
                    },
                }
            )
        return tools

    def export_anthropic_tools(self) -> list[dict[str, Any]]:
        """Export tool definitions conforming to Anthropic tool schema."""
        tools: list[dict[str, Any]] = []
        for t in sorted(self._tools.values(), key=lambda x: x.name):
            tools.append(
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters_schema or {"type": "object", "properties": {}},
                }
            )
        return tools
