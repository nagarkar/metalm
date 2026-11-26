"""Deterministic code-health signals that point each proposal at one measured finding.

The owner, 2026-11-26: "build deterministic tools and deterministic verbs instead of relying on the
agent to figure everything out every time" (nagarkar/metalm#97). Every signal is computed without a
model, from git, Python's `ast` and `tokenize`, a pytest junit report, and metalm's own pinned ruff,
so every repo is measured with the same tools.

- A finding names one problem, its location, a metric with its value and threshold, the lenses that
  may fix it, and a fingerprint (signal, path, symbol; never line numbers) that survives other edits.
- `measure` reads a checkout; `choose` picks the finding for a lens; `improved` is the gate that a
  proposal made its finding better.
"""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import io
import json
import re
import tokenize
import xml.etree.ElementTree as ElementTree
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

from metalm_ops.improve import process

THRESHOLDS = {
    "size_lines": 400,  # a file this long usually mixes concerns
    "function_lines": 60,  # a function this long usually does several things
    "complexity": 10,  # ruff C901 max-complexity
    "fan_out": 12,  # other repo modules one module imports
    "fan_in": 15,  # repo modules importing one module
    "duplicate_lines": 12,  # consecutive matching normalised lines
    "untested_lines": 40,  # smaller modules are not worth a tests finding
    "slow_test_seconds": 2.0,
    "slow_suite_seconds": 60.0,  # above this, the five slowest tests are findings too
    "churn_days": 14,
    "churn_files": 5,  # the busiest files by recently changed lines
}
SIGNALS = ("churn", "size", "complexity", "coupling", "duplication", "security", "docs", "untested", "slow-tests")
LENSES = {
    "churn": ("readability", "backend-robustness", "tests", "documentation", "drift"),
    "size": ("readability",),
    "complexity": ("readability",),
    "coupling": ("readability",),
    "duplication": ("duplication",),
    "security": ("backend-robustness",),
    "docs": ("documentation",),
    "untested": ("tests",),
    "slow-tests": ("performance",),
    "frontend-churn": ("frontend-robustness", "ui"),
}
FRONTEND = ("*.html", "*.js", "*.jsx", "*.ts", "*.tsx", "*.vue", "*.svelte", "*.css")
STEP_OF = {"complexity": "ruff", "security": "ruff", "docs": "ruff", "frontend-churn": "churn"}
SLOW_TEST_GAIN = 0.8  # a slow test must get at least 20% faster; smaller differences are timing noise
# PLR0913 (too many arguments) is left out: fixing it changes signatures, which is not a small safe change.
RUFF_SELECT = "C901,PLR0911,PLR0912,PLR0915,S,D100,D101,D103,D104"
# Security codes that flag ordinary tooling (asserts, subprocess with fixed arguments, random), not risk.
RUFF_IGNORE = "S101,S311,S404,S603,S607"
SKIPPED_PARTS = {"tests", "test", "docs", ".venv", "venv", "node_modules", "migrations", "generated", "build", "dist"}
MAX_TARGET_FILES = 4
MAX_TEST_FILES = 2  # tests named after the module first


def _git(root: Path, *arguments: str) -> str:
    result = process.run(["git", "-C", str(root), *arguments])
    if result.returncode:
        raise ValueError(f"git {arguments[0]} failed: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def is_test(path: str) -> bool:
    name = PurePosixPath(path).name
    parts = PurePosixPath(path).parts
    return "tests" in parts or "test" in parts or name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"


def files(root: Path, excludes: tuple[str, ...] = ()) -> tuple[list[str], list[str]]:
    """Tracked Python sources and tests, minus generated, vendored and excluded paths."""
    # --others: files the proposer just created (a new test, an extracted module) are measured too.
    tracked = sorted({path for path in _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*.py").split("\x00") if path})
    sources, tests = [], []
    for path in tracked:
        if any(fnmatch.fnmatch(path, pattern) for pattern in excludes):
            continue
        if is_test(path):
            tests.append(path)
        elif not SKIPPED_PARTS.intersection(PurePosixPath(path).parts[:-1]):
            sources.append(path)
    return sources, tests


def module_name(path: str) -> str:
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _parse(root: Path, path: str) -> tuple[str, ast.Module | None]:
    try:
        text = (root / path).read_text()
    except (OSError, UnicodeDecodeError):
        return "", None
    try:
        return text, ast.parse(text)
    except SyntaxError:
        return text, None


def _fingerprint(signal: str, path: str, symbol: str) -> str:
    return f"{signal}:{path}:{symbol}"


def finding(signal: str, path: str, start: int, end: int, metric: str, value: float, threshold: float, detail: str, symbol: str = "", **extra) -> dict:
    return {
        "signal": signal,
        "lenses": list(LENSES[signal]),
        "path": path,
        "start_line": start,
        "end_line": end,
        "metric": metric,
        "value": value,
        "threshold": threshold,
        "detail": detail,
        "symbol": symbol,
        "fingerprint": _fingerprint(signal, path, symbol),
        **extra,
    }


def _functions(tree: ast.Module):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _enclosing(tree: ast.Module | None, line: int) -> str:
    """The innermost function or class holding a line, else "module"; never a line number, so edits elsewhere keep the fingerprint."""
    best, size = "module", None
    if tree is None:
        return best
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.lineno <= line <= (node.end_lineno or node.lineno):
            span = (node.end_lineno or node.lineno) - node.lineno
            if size is None or span <= size:
                best, size = node.name, span
    return best


def size(root: Path, sources: list[str], limits: dict, parsed: dict) -> list[dict]:
    found = []
    for path in sources:
        text, tree = parsed[path]
        lines = len(text.splitlines())
        if lines > limits["size_lines"]:
            found.append(finding("size", path, 1, lines, "lines", lines, limits["size_lines"], f"{path} has {lines} lines"))
        for node in _functions(tree) if tree else ():
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length > limits["function_lines"]:
                found.append(
                    finding(
                        "size",
                        path,
                        node.lineno,
                        node.end_lineno or node.lineno,
                        "function lines",
                        length,
                        limits["function_lines"],
                        f"function {node.name} has {length} lines",
                        node.name,
                    )
                )
    return found


PASSWORD_CODES = {"S105", "S106", "S107"}


def _names_a_variable(text: str, line: int) -> bool:
    """ruff's hard-coded-password rules fire on names like TOKEN = "PLANNER_TOKEN"; a value that is itself
    an environment-variable or setting name is not a secret."""
    lines = text.splitlines()
    source = lines[line - 1] if 0 < line <= len(lines) else ""
    values = re.findall(r"""["']([^"']*)["']""", source)
    return bool(values) and all(re.fullmatch(r"[A-Z][A-Z0-9_]*|[a-z][a-z0-9]*(?:[_.-][a-z0-9]+)+", value) for value in values)


def ruff(root: Path, sources: list[str], ruff_bin: Path, limits: dict, parsed: dict) -> list[dict]:
    """Complexity, security and missing-docstring findings from metalm's ruff, ignoring the repo's config."""
    if not sources:
        return []
    result = process.run(
        [
            str(ruff_bin),
            "check",
            "--isolated",
            "--select",
            RUFF_SELECT,
            "--ignore",
            RUFF_IGNORE,
            "--config",
            f"lint.mccabe.max-complexity = {limits['complexity']}",
            "--output-format",
            "json",
            "--exit-zero",
            *sources,
        ],
        cwd=root,
    )
    if result.returncode:
        raise ValueError(f"ruff failed: {(result.stderr or result.stdout).strip()[:300]}")
    found = []
    for item in json.loads(result.stdout or "[]"):
        path = Path(item["filename"])
        path = str(path.relative_to(root)) if path.is_absolute() else str(path)
        code, message = item.get("code"), item["message"]
        if not code:  # a syntax error in one file; the other files' findings still count
            continue
        start = item["location"]["row"]
        end = item.get("end_location", {}).get("row", start)
        tree = parsed.get(path, ("", None))[1]
        name = re.search(r"`([^`]+)`", message)
        where = name.group(1) if name and code.startswith("C9") else _enclosing(tree, start)
        symbol = f"{code}:{where}"
        if code.startswith(("C9", "PLR")):
            numbers = re.search(r"\((\d+) > (\d+)\)", message)
            value, limit = (int(numbers.group(1)), int(numbers.group(2))) if numbers else (1, 0)
            found.append(finding("complexity", path, start, end, code, value, limit, message, symbol))
        elif code.startswith("S"):
            if code in PASSWORD_CODES and _names_a_variable(parsed.get(path, ("", None))[0], start):
                continue
            found.append(finding("security", path, start, end, code, 1, 0, message, symbol))
        elif code.startswith("D"):
            found.append(finding("docs", path, start, end, code, 1, 0, message, symbol))
    return found


def _statements(tree: ast.AST, inside_functions: bool):
    """Import statements; imports inside functions (the usual way to break a cycle) and under
    `if TYPE_CHECKING:` are left out of the module graph unless asked for."""
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not inside_functions:
            continue
        elif isinstance(node, ast.If) and not inside_functions and "TYPE_CHECKING" in ast.unparse(node.test):
            continue
        else:
            yield from _statements(node, inside_functions)


def _imports(tree: ast.Module, module: str, is_package: bool, inside_functions: bool = False) -> list[tuple[str, list[str]]]:
    """(base module, imported names) per import; `import a.b` is ("a.b", [])."""
    result = []
    package = module if is_package else module.rpartition(".")[0]
    for node in _statements(tree, inside_functions):
        if isinstance(node, ast.Import):
            result.extend((alias.name, []) for alias in node.names)
        else:
            base = node.module or ""
            if node.level:
                anchor = package.split(".") if package else []
                anchor = anchor[: len(anchor) - (node.level - 1)] if node.level > 1 else anchor
                base = ".".join([*anchor, base] if base else anchor)
            result.append((base, [alias.name for alias in node.names]))
    return result


def _resolve(name: str, modules: dict[str, str]) -> str | None:
    while name:
        if name in modules:
            return name
        name = name.rpartition(".")[0]
    return None


def _targets(item: tuple[str, list[str]], modules: dict[str, str]) -> set[str]:
    """Repo modules one import reaches: `from pkg import mod` reaches pkg.mod, not pkg's __init__."""
    base, names = item
    reached = set()
    for name in names:
        if f"{base}.{name}" in modules:
            reached.add(f"{base}.{name}")
        elif base and (target := _resolve(base, modules)):
            reached.add(target)
    if not names and base and (target := _resolve(base, modules)):
        reached.add(target)
    return reached


def graph(sources: list[str], parsed: dict) -> dict[str, set[str]]:
    modules = {module_name(path): path for path in sources}
    edges: dict[str, set[str]] = {module: set() for module in modules}
    for module, path in modules.items():
        tree = parsed[path][1]
        if tree is None:
            continue
        for item in _imports(tree, module, path.endswith("__init__.py")):
            edges[module].update(target for target in _targets(item, modules) if target != module)
    return edges


def _cycles(edges: dict[str, set[str]]) -> list[list[str]]:
    """Strongly connected components of two or more modules (Tarjan, iterative order is deterministic)."""
    index, low, stack, on_stack, result, counter = {}, {}, [], set(), [], [0]

    def visit(node: str) -> None:
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        for target in sorted(edges.get(node, ())):
            if target not in index:
                visit(target)
                low[node] = min(low[node], low[target])
            elif target in on_stack:
                low[node] = min(low[node], index[target])
        if low[node] == index[node]:
            component = []
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.append(member)
                if member == node:
                    break
            if len(component) > 1:
                result.append(sorted(component))

    for node in sorted(edges):
        if node not in index:
            visit(node)
    return result


def coupling(sources: list[str], parsed: dict, limits: dict) -> list[dict]:
    edges = graph(sources, parsed)
    paths = {module_name(path): path for path in sources}
    incoming: dict[str, int] = defaultdict(int)
    for targets in edges.values():
        for target in targets:
            incoming[target] += 1
    found = []
    for module, targets in sorted(edges.items()):
        if len(targets) > limits["fan_out"]:
            found.append(
                finding("coupling", paths[module], 1, 1, "fan-out", len(targets), limits["fan_out"], f"{module} imports {len(targets)} repo modules", "fan-out")
            )
        if incoming[module] > limits["fan_in"]:
            found.append(
                finding(
                    "coupling", paths[module], 1, 1, "fan-in", incoming[module], limits["fan_in"], f"{incoming[module]} repo modules import {module}", "fan-in"
                )
            )
    for component in _cycles(edges):
        found.append(
            finding(
                "coupling",
                paths[component[0]],
                1,
                1,
                "import cycle",
                len(component),
                1,
                "import cycle: " + " -> ".join(component),
                "cycle:" + ",".join(component),
                related=[paths[member] for member in component[1:]],
            )
        )
    return found


def _normalised(text: str) -> list[tuple[int, str]]:
    """(line, tokens) for each line with code; comments, blank lines and layout tokens dropped."""
    lines: dict[int, list[str]] = defaultdict(list)
    skip = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING, tokenize.ENDMARKER}
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type not in skip:
                lines[token.start[0]].append(token.string)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []
    # Lines of bare closing brackets or a lone keyword match everywhere; they never start or make a duplicate.
    return [(number, " ".join(tokens)) for number, tokens in sorted(lines.items()) if len(" ".join(tokens)) > 3]


def duplication(sources: list[str], parsed: dict, limits: dict) -> list[dict]:
    width = limits["duplicate_lines"]
    normal = {path: _normalised(parsed[path][0]) for path in sources}
    windows: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for path, lines in normal.items():
        for start in range(len(lines) - width + 1):
            key = hashlib.sha1("\n".join(text for _, text in lines[start : start + width]).encode()).hexdigest()
            windows[key].append((path, start))
    runs: dict[tuple[str, str, int], list[int]] = defaultdict(list)
    for places in windows.values():
        for first in range(len(places)):
            for second in range(first + 1, len(places)):
                (path_a, a), (path_b, b) = places[first], places[second]
                if path_a == path_b and abs(a - b) < width:
                    continue
                runs[(path_a, path_b, a - b)].append(a)
    found = []
    for (path_a, path_b, offset), starts in runs.items():
        starts = sorted(set(starts))
        begin = previous = starts[0]
        for start in [*starts[1:], None]:
            if start is not None and start == previous + 1:
                previous = start
                continue
            span = previous - begin + width
            line_a, line_b = normal[path_a][begin][0], normal[path_b][begin - offset][0]
            end_a = normal[path_a][previous + width - 1][0]
            end_b = normal[path_b][previous - offset + width - 1][0]
            digest = hashlib.sha1("\n".join(text for _, text in normal[path_a][begin : begin + width]).encode()).hexdigest()[:12]
            found.append(
                finding(
                    "duplication",
                    path_a,
                    line_a,
                    end_a,
                    "duplicated lines",
                    span,
                    width,
                    f"{span} lines duplicated at {path_b}:{line_b}-{end_b}",
                    digest,
                    related=[path_b],
                    other={"path": path_b, "start_line": line_b, "end_line": end_b},
                )
            )
            if start is not None:
                begin = previous = start
    found.sort(key=lambda item: (-item["value"], item["path"], item["start_line"]))
    return found[:20]


def tested_by(sources: list[str], tests: list[str], parsed_tests: dict) -> dict[str, list[str]]:
    """Each source path and the test files that import it."""
    modules = {module_name(path): path for path in sources}
    result: dict[str, list[str]] = {path: [] for path in sources}
    for test in tests:
        tree = parsed_tests[test][1]
        if tree is None:
            continue
        for item in _imports(tree, module_name(test), False, inside_functions=True):
            for target in _targets(item, modules):
                if test not in result[modules[target]]:
                    result[modules[target]].append(test)
    return result


def untested(sources: list[str], parsed: dict, coverage: dict[str, list[str]], limits: dict) -> list[dict]:
    found = []
    for path in sources:
        lines = len(parsed[path][0].splitlines())
        importable = all(part.isidentifier() for part in module_name(path).split("."))  # a test could import it
        if importable and not coverage.get(path) and lines > limits["untested_lines"] and not path.endswith("__init__.py"):
            found.append(finding("untested", path, 1, lines, "importing test files", 0, 1, f"no test file imports {module_name(path)}", "module"))
    return found


def slow_tests(root: Path, junit: Path | None, limits: dict) -> list[dict]:
    if junit is None or not junit.exists():
        return []
    cases = []
    for case in ElementTree.parse(junit).iter("testcase"):
        seconds = float(case.get("time") or 0)
        classname, name = case.get("classname", ""), case.get("name", "")
        parts, path = classname.split("."), classname
        while parts:  # tests.test_x.TestY -> tests/test_x.py
            if (root / ("/".join(parts) + ".py")).exists():
                path = "/".join(parts) + ".py"
                break
            parts.pop()
        cases.append((seconds, path, f"{classname}::{name}", name))
    cases.sort(reverse=True)
    total = sum(seconds for seconds, *_ in cases)
    chosen = {case for case in cases if case[0] > limits["slow_test_seconds"]}
    if total > limits["slow_suite_seconds"]:
        chosen.update(cases[:5])
    return [
        finding(
            "slow-tests", path, 1, 1, "seconds", round(seconds, 3), limits["slow_test_seconds"], f"{label} takes {seconds:.2f}s (suite {total:.1f}s)", label
        )
        for seconds, path, label, _ in sorted(chosen, reverse=True)
    ]


def churn(root: Path, sources: list[str], now: datetime, limits: dict, excludes: tuple[str, ...] = ()) -> list[dict]:
    """The busiest source files by changed lines on first-parent main, excluding the system's own merges.
    Front-end files are counted too, for the front-end lenses, which have no other signal."""
    since = (now - timedelta(days=limits["churn_days"])).astimezone(timezone.utc).isoformat()
    output = _git(
        root, "log", "HEAD", "--first-parent", "--diff-merges=first-parent", "--no-renames", "--numstat", "-z", "--format=%x1e%P%x00%B%x00", f"--since={since}"
    )
    counts: dict[str, int] = defaultdict(int)
    front: dict[str, int] = defaultdict(int)
    wanted = set(sources)
    for record in output.split("\x1e"):
        if not record.strip("\x00\n "):
            continue
        parents, message, changes = record.split("\x00", 2)
        if len(parents.split()) > 1 and re.search(r"auto-improve/[^\s'\"]+", message):
            continue
        for change in changes.split("\x00"):
            change = change.lstrip("\n")
            if change.count("\t") < 2:
                continue
            added, removed, path = change.split("\t", 2)
            if added == "-":
                continue
            if path in wanted:
                counts[path] += int(added) + int(removed)
            elif (
                any(fnmatch.fnmatch(PurePosixPath(path).name, pattern) for pattern in FRONTEND)
                and not SKIPPED_PARTS.intersection(PurePosixPath(path).parts[:-1])
                and not any(fnmatch.fnmatch(path, pattern) for pattern in excludes)
                and (root / path).exists()
            ):
                front[path] += int(added) + int(removed)
    found = []
    for signal, table in (("churn", counts), ("frontend-churn", front)):
        busiest = sorted(table.items(), key=lambda item: (-item[1], item[0]))[: limits["churn_files"]]
        found.extend(
            finding(signal, path, 1, 1, "lines changed", changed, 0, f"{changed} lines changed in {limits['churn_days']} days", "recent")
            for path, changed in busiest
        )
    return found


def measure(
    root: Path, *, ruff_bin: Path, excludes: tuple[str, ...] = (), thresholds: dict | None = None, junit: Path | None = None, now: datetime | None = None
) -> dict:
    """Every signal for one checkout; a failing signal is reported and the rest still run."""
    limits = {**THRESHOLDS, **(thresholds or {})}
    now = now or datetime.now(timezone.utc).astimezone()
    sources, tests = files(root, excludes)
    parsed = {path: _parse(root, path) for path in sources}
    parsed_tests = {path: _parse(root, path) for path in tests}
    coverage = tested_by(sources, tests, parsed_tests)
    steps = {
        "churn": lambda: churn(root, sources, now, limits, excludes),
        "size": lambda: size(root, sources, limits, parsed),
        "ruff": lambda: ruff(root, sources, ruff_bin, limits, parsed),
        "coupling": lambda: coupling(sources, parsed, limits),
        "duplication": lambda: duplication(sources, parsed, limits),
        "untested": lambda: untested(sources, parsed, coverage, limits),
        "slow-tests": lambda: slow_tests(root, junit, limits),
    }
    findings, errors = [], []
    for name, step in steps.items():
        try:
            findings.extend(step())
        except Exception as error:  # one broken tool must not hide the other signals
            errors.append({"signal": name, "error": str(error)[:300]})
    findings = _merge(findings)
    return {
        "files": len(sources),
        "tests": len(tests),
        "findings": findings,
        "errors": errors,
        "churned": [item["path"] for item in findings if item["signal"] == "churn"],
        "tested_by": coverage,
    }


def _merge(findings: list[dict]) -> list[dict]:
    """One finding per fingerprint: repeated hits (two S310 in one function, one block copied to several
    places) become a count, so the gate asks for fewer, not for every copy at once."""
    merged: dict[str, dict] = {}
    for item in findings:
        same = merged.get(item["fingerprint"])
        if same is None:
            merged[item["fingerprint"]] = dict(item)
            continue
        if item["signal"] in {"security", "docs"}:
            same["value"] += item["value"]
            same["start_line"] = min(same["start_line"], item["start_line"])
            same["end_line"] = max(same["end_line"], item["end_line"])
        elif item["value"] > same["value"]:
            merged[item["fingerprint"]] = {**item, "related": sorted({*same.get("related", []), *item.get("related", [])})}
        else:
            same["related"] = sorted({*same.get("related", []), *item.get("related", [])})
    return list(merged.values())


def _shuffle(seed: str, fingerprint: str) -> str:
    return hashlib.sha256(f"{seed}|{fingerprint}".encode()).hexdigest()


def candidates(report: dict, lens: str, *, avoid: set[str] = frozenset(), seed: str = "") -> list[dict]:
    """Findings for a lens: recently changed files first, then furthest over threshold, then a seeded shuffle."""
    churned = set(report.get("churned", []))
    pool = [item for item in report["findings"] if lens in item["lenses"] and item["fingerprint"] not in avoid]

    def excess(item: dict) -> float:
        return item["value"] / item["threshold"] if item["threshold"] else float(item["value"])

    # Measured findings in recently changed files first; a bare "this file was busy" finding only when nothing measured fits.
    return sorted(pool, key=lambda item: (item["signal"] == "churn", item["path"] not in churned, -excess(item), _shuffle(seed, item["fingerprint"])))


def target_files(report: dict, item: dict) -> list[str]:
    """The finding's file, its tests, and any related location; at most MAX_TARGET_FILES."""
    chosen = [item["path"]]
    for path in item.get("related", []):
        if path not in chosen:
            chosen.append(path)
    stem = PurePosixPath(item["path"]).stem
    tests = sorted(report.get("tested_by", {}).get(item["path"], []), key=lambda path: (stem not in PurePosixPath(path).stem, path))
    for path in tests[:MAX_TEST_FILES]:
        if path not in chosen:
            chosen.append(path)
    return chosen[:MAX_TARGET_FILES]


def improved(before: dict, after_report: dict) -> tuple[bool, str]:
    """Whether a proposal made its finding better: gone, or a smaller metric. Churn has no metric."""
    if before["signal"] in {"churn", "frontend-churn"}:
        return True, "churn finding: no metric to re-measure"
    step = STEP_OF.get(before["signal"], before["signal"])
    broken = [item["error"] for item in after_report.get("errors", []) if item["signal"] == step]
    if broken:
        # A tool that failed on the changed code cannot show the finding gone.
        return False, f"finding not re-measured: {step} failed: {broken[0][:120]}"
    same = next((item for item in after_report["findings"] if item["fingerprint"] == before["fingerprint"]), None)
    if same is None:
        return True, f"{before['metric']} finding resolved"
    limit = before["value"] * SLOW_TEST_GAIN if before["signal"] == "slow-tests" else before["value"]
    if same["value"] < limit:
        return True, f"{before['metric']} {before['value']} -> {same['value']}"
    return False, f"finding not improved: {before['metric']} {before['value']} -> {same['value']}"
