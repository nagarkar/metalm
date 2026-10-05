"""metalm_gendocs: generates a repo's docs/generated/ from its code, so docs never drift.

Reads docstrings and test markers with `ast` and imports nothing from the
target repo, so it runs in any environment (pre-commit, CI) without the
repo's dependencies. Output is byte-identical for identical input: sorted,
no timestamps. It writes four files: `index.md` (areas), `decisions.md`
(rules under `Decisions:`), `glossary.md` (entries under `Terms:`) and
`cujs.md` (tests marked `@pytest.mark.cuj("...")`).

Configuration, all optional, in the target repo's `pyproject.toml`:
`[tool.metalm-gendocs]` with `src` (default "src"), `tests` (default "tests")
and `out` (default "docs/generated").

Decisions:
- A term defined in two packages is an error naming both, never a silent pick: one word, one meaning. Enforced by: tests/test_gendocs.py::test_term_defined_twice_fails.
- A malformed entry under `Terms:` or a `cuj` marker without a string journey is an error naming the file and line; nothing is written. Enforced by: tests/test_gendocs.py::test_malformed_term_fails.

Terms:
- **area**: a package (a directory with `__init__.py`) under the source root, or a module directly inside the top package.
- **CUJ**: a critical user journey, declared on the end-to-end test that proves it.
"""

from metalm_gendocs.generate import GenDocsError, generate, stale, write

__all__ = ["GenDocsError", "generate", "stale", "write"]
