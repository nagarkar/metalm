"""metalm_gendocs: generates a repo's docs/generated/ from its code, so docs never drift.

Reads Python docstrings and test markers with `ast`, Rust `//!` module docs and
`/// cuj:` doc lines on tests, and TypeScript/JavaScript `@packageDocumentation`
blocks and `// cuj:` comments in any folder with a `package.json` at or above it. It imports nothing from the target repo, so it runs in any
environment (pre-commit, CI) without the repo's dependencies. Languages it does
not read are listed under "Not covered" in `index.md`, so agents ask the owner
to add them. Output is byte-identical for identical input: sorted,
no timestamps. It writes four files: `index.md` (areas), `decisions.md`
(rules under `Decisions:`), `glossary.md` (entries under `Terms:`) and
`cujs.md` (tests marked `@pytest.mark.cuj("...")` or `// cuj: ...`).

Configuration, all optional, in the target repo's `pyproject.toml`:
`[tool.metalm-gendocs]` with `src` (default "src"), `tests` (default "tests"),
`out` (default "docs/generated") and `roots` (default none: extra source roots,
such as a sub-project outside `src`, whose modules are named by path).

Decisions:
- A term defined in two packages is an error naming both, never a silent pick: one word, one meaning. Enforced by: tests/test_generate.py::test_term_defined_twice_fails.
- A malformed entry under `Terms:` or a `cuj` marker without a string journey is an error naming the file and line; nothing is written. Enforced by: tests/test_generate.py::test_malformed_term_fails.

Terms:
- **area**: a package (a directory with `__init__.py` or `index.ts`/`index.js`) under the source root, a module directly inside the top Python package, or a Node file directly under the source root.
- **CUJ**: a critical user journey, declared on the end-to-end test that proves it.
"""

from metalm_gendocs.generate import GenDocsError, generate, stale, uncovered, write

__all__ = ["GenDocsError", "generate", "stale", "uncovered", "write"]
