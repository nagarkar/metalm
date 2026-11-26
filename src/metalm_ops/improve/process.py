"""The subprocess boundary for improvement runs; offline tests inject one runner."""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path
from typing import Callable

RUNNER: Callable[..., subprocess.CompletedProcess[str]] | None = None


def run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    input: str | None = None,
    timeout: float = 300,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command without a shell, preserving stdout and stderr separately."""
    if RUNNER is not None:
        return RUNNER(argv, cwd=cwd, input=input, timeout=timeout, env=env)
    with subprocess.Popen(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    ) as child:
        try:
            output, errors = child.communicate(input=input, timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt, SystemExit) as error:
            # Agent CLIs and test shells can spawn descendants that outlive the
            # direct child. Kill the whole owned group before worktree cleanup.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            output, errors = child.communicate()
            if isinstance(error, subprocess.TimeoutExpired):
                error.output, error.stderr = output, errors
            raise
        return subprocess.CompletedProcess(argv, child.returncode, output, errors)
