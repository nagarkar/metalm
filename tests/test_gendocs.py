"""metalm-gendocs against small throwaway repos: what lands in each generated file, and the errors."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from metalm_gendocs import GenDocsError, generate, stale, write
from metalm_gendocs.cli import main

ROOT = Path(__file__).resolve().parents[1]


def put(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip())


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    put(tmp_path, "src/shop/__init__.py", '''
        """Shop: sells things to people.

        Second paragraph is not in the index.
        """
    ''')
    put(tmp_path, "src/shop/orders/__init__.py", '''
        """Orders: takes and keeps orders.

        Never imports: shop.web

        Decisions:
        - An order is never deleted; it is cancelled. Why: refunds need the row.
          Enforced by: tests/test_orders.py::test_cancel. (owner)
        - Order ids are ULIDs.

        Terms:
        - **order**: a request to buy, with lines and a total.
        """
    ''')
    put(tmp_path, "src/shop/web.py", '"""Web: the HTTP surface."""\n')
    put(tmp_path, "src/shop/orders/store.py", '"""Store: not an area (module inside a subpackage)."""\n')
    put(tmp_path, "tests/test_orders.py", '''
        import pytest

        @pytest.mark.cuj("The owner cancels an order via `shop cancel`, and sees it marked cancelled.")
        def test_cancel():
            pass

        class TestRefund:
            @pytest.mark.cuj("A customer is refunded via the refund page, and sees the money back.")
            def test_refund(self):
                pass

        def test_plain():
            pass
    ''')
    return tmp_path


def test_index_lists_packages_and_top_modules_with_paragraph_one(repo: Path) -> None:
    index = generate(repo)["docs/generated/index.md"]
    assert "## `shop`" in index and "Shop: sells things to people." in index
    assert "Second paragraph" not in index
    assert "## `shop.orders`" in index and "Never imports: shop.web" in index
    assert "## `shop.web`" in index
    assert "shop.orders.store" not in index


def test_decisions_split_owner_from_drafted_and_join_continuations(repo: Path) -> None:
    decisions = generate(repo)["docs/generated/decisions.md"]
    owner, drafted = decisions.split("## Agent-drafted")
    assert "- `shop.orders`: An order is never deleted; it is cancelled. Why: refunds need the row. Enforced by: tests/test_orders.py::test_cancel. (owner)" in owner
    assert "Order ids are ULIDs." in drafted and "ULIDs" not in owner


def test_glossary_names_the_owning_package(repo: Path) -> None:
    assert "- **order** (`shop.orders`): a request to buy, with lines and a total." in generate(repo)["docs/generated/glossary.md"]


def test_cujs_list_each_marked_test_and_skip_unmarked(repo: Path) -> None:
    cujs = generate(repo)["docs/generated/cujs.md"]
    assert "(`tests/test_orders.py::test_cancel`)" in cujs
    assert "(`tests/test_orders.py::TestRefund::test_refund`)" in cujs
    assert "test_plain" not in cujs


def test_output_is_deterministic_and_rerun_is_a_no_op(repo: Path) -> None:
    assert write(repo) == sorted(generate(repo))
    first = {rel: (repo / rel).read_text() for rel in generate(repo)}
    assert write(repo) == []
    assert stale(repo) == []
    assert {rel: (repo / rel).read_text() for rel in first} == first


def test_stale_names_the_file_after_a_docstring_change(repo: Path) -> None:
    write(repo)
    put(repo, "src/shop/web.py", '"""Web: the HTTP surface, now with JSON."""\n')
    assert stale(repo) == ["docs/generated/index.md"]


def test_term_defined_twice_fails(repo: Path) -> None:
    put(repo, "src/shop/web.py", '"""Web.\n\nTerms:\n- **Order**: something else.\n"""\n')
    with pytest.raises(GenDocsError, match="defined in both"):
        generate(repo)


def test_malformed_term_fails(repo: Path) -> None:
    put(repo, "src/shop/web.py", '"""Web.\n\nTerms:\n- order is a thing\n"""\n')
    with pytest.raises(GenDocsError, match="src/shop/web.py: Terms entry"):
        generate(repo)


def test_cuj_without_string_fails(repo: Path) -> None:
    put(repo, "tests/test_bad.py", "import pytest\n\nJ = 'x'\n\n@pytest.mark.cuj(J)\ndef test_x():\n    pass\n")
    with pytest.raises(GenDocsError, match="tests/test_bad.py:5: cuj marker"):
        generate(repo)


def test_unknown_config_key_fails(repo: Path) -> None:
    put(repo, "pyproject.toml", '[tool.metalm-gendocs]\nsource = "lib"\n')
    with pytest.raises(GenDocsError, match="unknown key"):
        generate(repo)


def test_config_moves_roots_and_output(tmp_path: Path) -> None:
    put(tmp_path, "pyproject.toml", '[tool.metalm-gendocs]\nsrc = "lib"\ntests = "t"\nout = "gen"\n')
    put(tmp_path, "lib/app/__init__.py", '"""App: the app."""\n')
    put(tmp_path, "t/test_app.py", 'import pytest\n@pytest.mark.cuj("A user opens the app.")\ndef test_open():\n    pass\n')
    files = generate(tmp_path)
    assert sorted(files) == ["gen/cujs.md", "gen/decisions.md", "gen/glossary.md", "gen/index.md"]
    assert "App: the app." in files["gen/index.md"] and "A user opens the app." in files["gen/cujs.md"]


def test_empty_repo_writes_placeholders(tmp_path: Path) -> None:
    files = generate(tmp_path)
    assert all("Do not edit" in text for text in files.values())
    assert "None yet" in files["docs/generated/glossary.md"]


def test_cli_exit_codes_follow_pre_commit(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--root", str(repo), "--check"]) == 1
    assert main(["--root", str(repo)]) == 1
    assert "add them and commit again" in capsys.readouterr().err
    assert main(["--root", str(repo)]) == 0
    assert main(["--root", str(repo), "--check"]) == 0
    put(repo, "src/shop/web.py", "def broken(:\n")
    assert main(["--root", str(repo)]) == 2


def test_imports_nothing_from_the_target_repo(repo: Path) -> None:
    put(repo, "src/shop/web.py", '"""Web: importing me would fail."""\nraise SystemExit("imported")\n')
    out = subprocess.run([sys.executable, "-m", "metalm_gendocs.cli", "--root", str(repo)], capture_output=True, text=True)
    assert out.returncode == 1, out.stderr
    assert "imported" not in out.stdout + out.stderr


def test_metalm_own_generated_docs_are_current() -> None:
    assert stale(ROOT) == [], "run: metalm-gendocs (from the metalm root) and commit docs/generated/"
