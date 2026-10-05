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


@pytest.fixture
def node_repo(tmp_path: Path) -> Path:
    put(tmp_path, "package.json", '{"name": "shop"}\n')
    put(tmp_path, "src/orders/index.ts", '''
        import { db } from "../db";

        /**
         * @packageDocumentation
         * Orders: takes and keeps orders.
         *
         * Never imports: web
         *
         * Decisions:
         * - Orders are cancelled, never deleted. (owner)
         *
         * Terms:
         * - **order**: a request to buy.
         */
        export const x = 1;
    ''')
    put(tmp_path, "src/main.ts", '/** Main: starts the server. */\nexport {};\n')
    put(tmp_path, "src/orders/orders.test.ts", '''
        import { test } from "vitest";

        // cuj: The owner cancels an order via the orders page, and sees it marked cancelled.
        test("cancel order", () => {});

        it("plain", () => {});
    ''')
    return tmp_path


def test_node_package_documentation_feeds_index_decisions_and_glossary(node_repo: Path) -> None:
    files = generate(node_repo)
    assert "## `orders`" in files["docs/generated/index.md"] and "Orders: takes and keeps orders." in files["docs/generated/index.md"]
    assert "Never imports: web" in files["docs/generated/index.md"]
    assert "## `main`" in files["docs/generated/index.md"] and "Main: starts the server." in files["docs/generated/index.md"]
    assert "orders.test" not in files["docs/generated/index.md"]
    assert "- `orders`: Orders are cancelled, never deleted. (owner)" in files["docs/generated/decisions.md"]
    assert "- **order** (`orders`): a request to buy." in files["docs/generated/glossary.md"]


def test_node_cuj_comment_names_the_test(node_repo: Path) -> None:
    cujs = generate(node_repo)["docs/generated/cujs.md"]
    assert "sees it marked cancelled. (`src/orders/orders.test.ts::cancel order`)" in cujs
    assert "plain" not in cujs


def test_node_cuj_comment_without_a_test_call_fails(node_repo: Path) -> None:
    put(node_repo, "tests/bad.spec.ts", "// cuj: A journey with nothing under it.\nconst x = 1;\n")
    with pytest.raises(GenDocsError, match="tests/bad.spec.ts:1: '// cuj:'"):
        generate(node_repo)


def test_node_files_ignored_without_package_json(repo: Path) -> None:
    put(repo, "src/shop/pages/app.js", "/** App: page script. */\n")
    assert "app" not in generate(repo)["docs/generated/index.md"].split("## `shop.web`")[0].split("## `shop.orders`")[0]
    assert "pages" not in generate(repo)["docs/generated/index.md"]


def test_uncovered_languages_are_listed_for_the_agent_to_raise(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    put(repo, "src/native/Bridge.swift", "// swift\n")
    put(repo, "src/native/lib.rs", "// rust\n")
    index = generate(repo)["docs/generated/index.md"]
    assert "## Not covered" in index and "Rust (1 files), Swift (1 files)" in index
    assert "ask the owner whether to add each language" in index
    main(["--root", str(repo)])
    assert "not covered: Rust, Swift" in capsys.readouterr().err
