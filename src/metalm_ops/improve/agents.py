"""The only Codex/Claude call site: exact CLI flags, strict replies and provenance.

Codex uses the owner's ChatGPT subscription; Claude's reported cost is stored
even when its answer is rejected. A call is reserved before the process starts.
"""

from __future__ import annotations

import hashlib
import json
import re
import math
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from metalm_ops.config import Config, Improve
from metalm_ops.improve import process, store

ROOT = Path(__file__).parent


def codex_binary(settings: Improve) -> str:
    """Configured Codex binary, falling back to PATH when it is absent."""
    configured = str(Path(settings.codex_bin).expanduser())
    return configured if Path(configured).is_file() else (shutil.which("codex") or "codex")


def claude_binary(settings: Improve) -> str:
    """Configured Claude binary with the home-directory abbreviation expanded."""
    return str(Path(settings.claude_bin).expanduser())


def validate(value: object, schema: dict, where: str = "answer") -> None:
    """Validate this package's strict JSON Schema subset, raising a named error."""
    kind = schema["type"]
    types = {"object": dict, "string": str, "boolean": bool, "array": list, "number": (int, float), "integer": int}
    if not isinstance(value, types[kind]) or (kind in {"number", "integer"} and isinstance(value, bool)):
        raise ValueError(f"{where}: expected {kind}")
    if kind == "object":
        if set(value) != set(schema["required"]):
            raise ValueError(f"{where}: missing or unknown fields")
        for name, field in schema["properties"].items():
            validate(value[name], field, f"{where}.{name}")
    elif kind == "array":
        if len(value) < schema.get("minItems", 0):
            raise ValueError(f"{where}: too few items")
        for item in value:
            validate(item, schema["items"], where)
    elif kind in {"number", "integer"}:
        if (isinstance(value, float) and not math.isfinite(value)) or not schema.get("minimum", -math.inf) <= value <= schema.get("maximum", math.inf):
            raise ValueError(f"{where}: outside allowed range")
    elif kind == "string" and not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", math.inf):
        raise ValueError(f"{where}: too long")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{where}: unknown value")


def rejected(reason: str) -> dict:
    """A failed review is a rejection, never a guessed approval."""
    return {"verdict": "reject", "clear_cut": False, "confidence": 0.0, "behaviour_change": False, "risks": [], "reasons": reason}


def prompt_id(template: str) -> str:
    """The `id:` from a prompt file's front matter, e.g. `propose_v2`; empty when it has none."""
    match = re.search(r"^id:\s*(\S+)\s*$", template.split("---", 2)[1] if template.startswith("---") else "", re.MULTILINE)
    return match.group(1) if match else ""


def call(config: Config, *, run_id: str, repo: str, role: str, worktree: Path, directory: Path, prompt: str, template: str) -> dict:
    """Invoke one proposer or independent reviewer and preserve its raw artifacts."""
    settings = config.improve
    assert settings is not None
    proposer = role == "propose"
    schema_path = ROOT / "schemas" / ("proposal.schema.json" if proposer else "verify.schema.json" if role == "verify" else "verdict.schema.json")
    schema_text = schema_path.read_text()
    answer_path = directory / f"{role}.json"
    directory.mkdir(parents=True, exist_ok=True)
    started = datetime.now().astimezone()
    ledger_id = store.reserve_call(
        config,
        {
            "run_id": run_id,
            "repo": repo,
            "started": started.isoformat(),
            "day": started.date().isoformat(),
            "role": role,
            "provider": "openai" if proposer else "anthropic",
            "model": settings.model if proposer else settings.review_model,
            "prompt_id": prompt_id(template) or ("propose" if proposer else role.replace("-", "_")),
            "prompt_sha256": hashlib.sha256(template.encode()).hexdigest(),
            "payload_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "duration": 0.0,
            "outcome": "started",
            "cost": None,
            "billing": "chatgpt-subscription" if proposer else "reported-cost",
        },
    )
    if proposer:
        arguments = [
            codex_binary(settings),
            "exec",
            "--ignore-user-config",
            "--ephemeral",
            "--color",
            "never",
            "--json",
            "-m",
            settings.model,
            "-c",
            f'model_reasoning_effort="{settings.effort}"',
            "-c",
            'approval_policy="never"',
            "--output-schema",
            str(schema_path),
            "-o",
            str(answer_path),
            "-C",
            str(worktree),
            "-s",
            "workspace-write",
            "-",
        ]
        timeout = settings.propose_timeout_min * 60
    else:
        arguments = [
            claude_binary(settings),
            "-p",
            "--model",
            settings.review_model,
            "--output-format",
            "json",
            "--json-schema",
            schema_text,
            "--tools",
            "",
            "--no-session-persistence",
            "--setting-sources",
            "",
            "--strict-mcp-config",
            "--max-turns",
            "3",
        ]
        timeout = settings.review_timeout_min * 60
    clock = time.monotonic()
    outcome, cost = "failed", None
    try:
        result = process.run(arguments, cwd=worktree, input=prompt, timeout=timeout)
        output = result.stdout or ""
        (directory / ("propose.jsonl" if proposer else f"{role}.json")).write_text(output)
        (directory / f"{role}.stderr.log").write_text(result.stderr or "")
        if proposer:
            if result.returncode:
                raise ValueError(f"proposer exited {result.returncode}")
            value = json.loads(answer_path.read_text())
        else:
            envelope = json.loads(output)
            if not isinstance(envelope, dict):
                raise ValueError("review response is not an object")
            reported = envelope.get("total_cost_usd")
            if isinstance(reported, (int, float)) and not isinstance(reported, bool) and math.isfinite(reported) and reported >= 0:
                cost = float(reported)
            if result.returncode or envelope.get("is_error") or "structured_output" not in envelope:
                raise ValueError("review failed or structured_output is missing")
            value = envelope["structured_output"]
        validate(value, json.loads(schema_text))
        if proposer and not value["skip"] and (not value["title"].strip() or "\n" in value["title"] or "\r" in value["title"]):
            raise ValueError("proposal.title: expected a nonempty single-line subject")
        outcome = "skipped" if proposer and value["skip"] else ("proposed" if proposer else value["verdict"])
        return value
    except (OSError, ValueError, OverflowError, subprocess.TimeoutExpired) as error:
        reason = f"{role} failed: {error}"
        if isinstance(error, subprocess.TimeoutExpired):
            partial = error.stdout or ""
            if isinstance(partial, bytes):
                partial = partial.decode(errors="replace")
            (directory / ("propose.jsonl" if proposer else f"{role}.json")).write_text(partial)
            reason = f"{role} timed out after {timeout} seconds"
        (directory / f"{role}.error.log").write_text(reason + "\n")
        return (
            {"skip": True, "skip_reason": reason}
            if proposer
            else ({"verdict": "uncertain", "counter_evidence": [], "reasons": reason} if role == "verify" else rejected(reason))
        )
    finally:
        if not answer_path.exists():
            answer_path.write_text("")
        if proposer and not (directory / "propose.jsonl").exists():
            (directory / "propose.jsonl").write_text("")
        store.finish_call(config, ledger_id, duration=time.monotonic() - clock, outcome=outcome, cost=cost)
