"""Run project-defined verification commands and inspect exit codes.

The authoritative gate is the user's ``[verify]`` commands. Plan-derived
acceptance entries may run *in addition*, but only after
``gate_command_problem`` confirms they are runnable argv commands -
LLM-suggested prose or shell one-liners are never exec'd. Everything is
parsed with ``shlex.split`` and runs without a shell. An agent claiming
"tests pass" has no effect on this module (threat T14).

Windows note:
Orkestra intentionally runs child processes with an allowlisted environment.
On Windows, Python and vendor CLIs also depend on a small set of OS/user
environment variables (for example SystemRoot, USERPROFILE and APPDATA).
Those variables are preserved here without opening the environment wholesale.
"""

from __future__ import annotations

import asyncio
import os
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from orkestra.errors import VerificationError

_ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "TMPDIR",
    "USER",
    "SHELL",
    "VIRTUAL_ENV",
    "PYTHONPATH",
    "NODE_PATH",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "CI",
)

# Windows variables required by CPython / Win32 process loading and commonly
# used by subscription-authenticated coding CLIs to locate per-user state.
# Matching is case-insensitive because Windows environment variable names are.
_WINDOWS_ENV_ALLOWLIST = frozenset(
    {
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "USERNAME",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "PROGRAMW6432",
        "HOMEDRIVE",
        "HOMEPATH",
    }
)


#: Characters that mean the string relies on a shell (pipes, globs,
#: substitution) or is prose (parentheses) - either way, not a gate.
_GATE_FORBIDDEN = set("|&;<>`$()*?{}[]\n")


def _spawn_group_kwargs() -> dict[str, Any]:
    """Platform-appropriate child-process group/session settings."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def gate_command_problem(command: str, *, strict: bool = True) -> str | None:
    """Why this string cannot be exec'd as a verification gate (None = fine).

    ``strict=True`` (plan-derived entries): must be plain argv with a
    resolvable executable and no shell/prose syntax - anything else is
    dropped by the caller instead of exec'd or allowed to block a run.
    ``strict=False`` (user-authored [verify] commands): only checks the
    string parses and its executable exists, so a broken config is caught
    *before* an agent is dispatched, without second-guessing the user.
    """
    stripped = command.strip()
    if not stripped:
        return "empty"
    if strict:
        bad = sorted({c for c in stripped if c in _GATE_FORBIDDEN})
        if bad:
            rendered = " ".join(repr(c) if c.isspace() else c for c in bad)
            return f"contains shell/prose syntax ({rendered}) - commands run without a shell"
        # Prose that merely *starts* with a real binary ("python3 -m pytest,
        # run from the repo root, exits 0") passes a naive check; commas and
        # sentence length are the reliable tells.
        if "," in stripped:
            return "reads as prose (contains a comma), not a command"
        if len(stripped) > 160:
            return "too long to be a command - reads as prose"
    try:
        argv = shlex.split(stripped)
    except ValueError as exc:
        return f"cannot be parsed as a command ({exc})"
    if not argv:
        return "empty"
    if strict and len(argv) > 12:
        return "too many words to be a command - reads as prose"
    path_env = subprocess_env().get("PATH")
    if shutil.which(argv[0], path=path_env) is None:
        return f"{argv[0]!r} is not an executable on PATH"
    return None


def subprocess_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Allowlisted environment for verification/agent subprocesses (threat T3)."""
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if key in _ENV_ALLOWLIST or (os.name == "nt" and key.upper() in _WINDOWS_ENV_ALLOWLIST):
            env[key] = value
    if os.name == "nt" and "PATH" in env:
        git_exe = shutil.which("git")
        if git_exe:
            git_usr_bin = str(Path(git_exe).parent.parent / "usr" / "bin")
            if Path(git_usr_bin).is_dir() and git_usr_bin not in env["PATH"]:
                env["PATH"] = f"{env['PATH']};{git_usr_bin}"
    if extra:
        env.update(extra)
    return env


def worktree_pythonpath(cwd: Path, existing: str | None = None) -> str:
    """``PYTHONPATH`` that binds Python imports to *this* tree, first.

    A src-layout project installed editable puts an absolute path to the
    main checkout on ``sys.path`` through a ``.pth`` file in site-packages.
    That path is honoured whatever the working directory is, so ``pytest``
    run inside a worktree imports the main checkout's code and reports on a
    tree it never read. ``PYTHONPATH`` entries are placed ahead of anything
    site-packages processing contributes, so naming the worktree here makes
    the gate read the tree it was pointed at. The inherited value is kept,
    after ours, so a user's own PYTHONPATH still works.
    """
    root = Path(cwd).resolve()
    # Only one of these, never both. The worktree root carries the project's
    # top-level modules, and a project with its own types.py or queue.py at the
    # root would shadow the standard library for every gate we run. A src
    # layout keeps importable code under src/, so naming the root there buys
    # nothing and risks exactly that.
    src = root / "src"
    entries = [str(src)] if src.is_dir() else [str(root)]
    if existing:
        entries.extend(part for part in existing.split(os.pathsep) if part)
    seen: set[str] = set()
    ordered: list[str] = []
    for entry in entries:
        if entry not in seen:
            seen.add(entry)
            ordered.append(entry)
    return os.pathsep.join(ordered)


def gate_env(cwd: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    """Environment for a gate (or a probe of it) running in ``cwd``.

    Identical to :func:`subprocess_env` plus the worktree-scoped
    ``PYTHONPATH`` above, unless the caller states a ``PYTHONPATH`` of its
    own - which the binding canary does, in order to measure what an
    unmitigated environment actually does.
    """
    extra = dict(extra or {})
    env = subprocess_env(extra)
    if "PYTHONPATH" not in extra:
        env["PYTHONPATH"] = worktree_pythonpath(cwd, os.environ.get("PYTHONPATH"))
    return env


@dataclass
class CommandResult:
    command: str
    exit_code: int
    duration_s: float
    stdout_tail: str
    stderr_tail: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


@dataclass
class VerificationOutcome:
    results: list[CommandResult] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    """The environment the commands actually ran in.

    Captured rather than reconstructed. A record that rebuilds the
    environment afterwards describes an environment that may never have
    existed: `gate_env` varies with the worktree and with `env_extra`, so
    a second call is a guess that happens to be right only while no
    caller passes anything.
    """

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def summary(self) -> str:
        if not self.results:
            return "no verification commands configured"
        lines = [
            f"{'PASS' if r.passed else 'FAIL'} (exit {r.exit_code}, "
            f"{r.duration_s:.1f}s): {r.command}"
            for r in self.results
        ]
        return "\n".join(lines)

    def failure_detail(self, max_chars: int = 4000) -> str:
        """Output of the failing command(s) - what the user and the
        repairing agent need in order to understand the rejection."""
        chunks = []
        for r in self.results:
            if r.passed:
                continue
            body = "\n".join(part for part in (r.stdout_tail, r.stderr_tail) if part.strip())
            chunks.append(f"$ {r.command}   (exit {r.exit_code})\n{body or '(no output)'}")
        text = "\n\n".join(chunks)
        return text[:max_chars] + ("\n… (truncated)" if len(text) > max_chars else "")


async def run_verification(
    commands: list[str],
    cwd: Path,
    timeout_s: int = 900,
    env_extra: dict[str, str] | None = None,
) -> VerificationOutcome:
    """Run each command in order; stop at first failure."""
    env = gate_env(cwd, env_extra)
    outcome = VerificationOutcome(env=env)
    for command in commands:
        argv = shlex.split(command)
        if not argv:
            continue
        start = time.monotonic()
        executable = shutil.which(argv[0], path=env.get("PATH")) or argv[0]
        try:
            proc = await asyncio.create_subprocess_exec(
                executable,
                *argv[1:],
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                **_spawn_group_kwargs(),
            )
        except FileNotFoundError as exc:
            msg = f"verification command not found: {argv[0]!r} (from {command!r})"
            raise VerificationError(msg) from exc
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            outcome.results.append(
                CommandResult(
                    command=command,
                    exit_code=124,
                    duration_s=time.monotonic() - start,
                    stdout_tail="",
                    stderr_tail=f"timed out after {timeout_s}s",
                )
            )
            return outcome
        outcome.results.append(
            CommandResult(
                command=command,
                exit_code=proc.returncode if proc.returncode is not None else -1,
                duration_s=time.monotonic() - start,
                stdout_tail=stdout.decode(errors="replace")[-4000:],
                stderr_tail=stderr.decode(errors="replace")[-4000:],
            )
        )
        if not outcome.results[-1].passed:
            return outcome
    return outcome
