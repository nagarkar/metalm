"""metalm_gendocs.generate against small throwaway repos: what lands in each generated file, and the errors."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import put

from metalm_gendocs import GenDocsError, generate, stale, write

ROOT = Path(__file__).resolve().parents[1]


def test_index_lists_packages_and_top_modules_with_paragraph_one(repo: Path) -> None:
    """Source: design.md#generated-docs: index.md lists every area with paragraph one and never-imports."""
    index = generate(repo)["docs/generated/index.md"]
    assert "## `shop`" in index and "Shop: sells things to people." in index
    assert "Second paragraph" not in index
    assert "## `shop.orders`" in index and "Never imports: shop.web" in index
    assert "## `shop.web`" in index
    assert "shop.orders.store" not in index


def test_decisions_split_owner_from_drafted_and_join_continuations(repo: Path) -> None:
    """Source: design.md#generated-docs: decisions.md lists every (owner) rule with its package."""
    decisions = generate(repo)["docs/generated/decisions.md"]
    owner, drafted = decisions.split("## Agent-drafted")
    assert (
        "- `shop.orders`: An order is never deleted; it is cancelled. Why: refunds need the row. Enforced by: tests/test_orders.py::test_cancel. (owner)"
        in owner
    )
    assert "Order ids are ULIDs." in drafted and "ULIDs" not in owner


def test_glossary_names_the_owning_package(repo: Path) -> None:
    """Source: design.md#the-package-docstring: a term lives in the package that owns it (owner)."""
    assert "- **order** (`shop.orders`): a request to buy, with lines and a total." in generate(repo)["docs/generated/glossary.md"]


def test_cujs_list_each_marked_test_and_skip_unmarked(repo: Path) -> None:
    """Source: requirements.md#cujs-are-generated-from-the-code: cujs.md lists every CUJ with the test that proves it."""
    cujs = generate(repo)["docs/generated/cujs.md"]
    assert "(`tests/test_orders.py::test_cancel`)" in cujs
    assert "(`tests/test_orders.py::TestRefund::test_refund`)" in cujs
    assert "test_plain" not in cujs


def test_output_is_deterministic_and_rerun_is_a_no_op(repo: Path) -> None:
    """Source: coding.md#idempotence-and-writes: a rerun on unchanged input changes nothing."""
    assert write(repo) == sorted(generate(repo))
    first = {rel: (repo / rel).read_text() for rel in generate(repo)}
    assert write(repo) == []
    assert stale(repo) == []
    assert {rel: (repo / rel).read_text() for rel in first} == first


def test_stale_names_the_file_after_a_docstring_change(repo: Path) -> None:
    """Source: design.md#generated-docs: a test fails when regenerating would change docs/generated/ (owner)."""
    write(repo)
    put(repo, "src/shop/web.py", '"""Web: the HTTP surface, now with JSON."""\n')
    assert stale(repo) == ["docs/generated/index.md"]


def test_term_defined_twice_fails(repo: Path) -> None:
    """Source: metalm_gendocs Decisions: a term defined in two packages is an error naming both."""
    put(repo, "src/shop/web.py", '"""Web.\n\nTerms:\n- **Order**: something else.\n"""\n')
    with pytest.raises(GenDocsError, match="defined in both"):
        generate(repo)


def test_malformed_term_fails(repo: Path) -> None:
    """Source: metalm_gendocs Decisions: a malformed Terms: entry is an error naming the file and line."""
    put(repo, "src/shop/web.py", '"""Web.\n\nTerms:\n- order is a thing\n"""\n')
    with pytest.raises(GenDocsError, match="src/shop/web.py: Terms entry"):
        generate(repo)


def test_cuj_without_string_fails(repo: Path) -> None:
    """Source: metalm_gendocs Decisions: a cuj marker without a string journey is an error naming the file and line."""
    put(repo, "tests/test_bad.py", "import pytest\n\nJ = 'x'\n\n@pytest.mark.cuj(J)\ndef test_x():\n    pass\n")
    with pytest.raises(GenDocsError, match="tests/test_bad.py:5: cuj marker"):
        generate(repo)


def test_unknown_config_key_fails(repo: Path) -> None:
    """Source: coding.md#failure: an unknown config key is an error naming the key."""
    put(repo, "pyproject.toml", '[tool.metalm-gendocs]\nsource = "lib"\n')
    with pytest.raises(GenDocsError, match="unknown key"):
        generate(repo)


def test_config_moves_roots_and_output(tmp_path: Path) -> None:
    """Source: design.md#generated-docs: config keys src, tests, out and roots."""
    put(tmp_path, "pyproject.toml", '[tool.metalm-gendocs]\nsrc = "lib"\ntests = "t"\nout = "gen"\n')
    put(tmp_path, "lib/app/__init__.py", '"""App: the app."""\n')
    put(tmp_path, "t/test_app.py", 'import pytest\n@pytest.mark.cuj("A user opens the app.")\ndef test_open():\n    pass\n')
    files = generate(tmp_path)
    assert sorted(files) == ["gen/cujs.md", "gen/decisions.md", "gen/glossary.md", "gen/index.md"]
    assert "App: the app." in files["gen/index.md"] and "A user opens the app." in files["gen/cujs.md"]


def test_empty_repo_writes_placeholders(tmp_path: Path) -> None:
    """Source: design.md#generated-docs: every repo has the four generated files."""
    files = generate(tmp_path)
    assert all("Do not edit" in text for text in files.values())
    assert "None yet" in files["docs/generated/glossary.md"]


def test_metalm_own_generated_docs_are_current() -> None:
    """Source: design.md#generated-docs: a test fails when regenerating would change docs/generated/ (owner)."""
    assert stale(ROOT) == [], "run: metalm-gendocs (from the metalm root) and commit docs/generated/"


@pytest.fixture
def node_repo(tmp_path: Path) -> Path:
    put(tmp_path, "package.json", '{"name": "shop"}\n')
    put(
        tmp_path,
        "src/orders/index.ts",
        """
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
    """,
    )
    put(tmp_path, "src/main.ts", "/** Main: starts the server. */\nexport {};\n")
    put(
        tmp_path,
        "src/orders/orders.test.ts",
        """
        import { test } from "vitest";

        // cuj: The owner cancels an order via the orders page, and sees it marked cancelled.
        test("cancel order", () => {});

        it("plain", () => {});
    """,
    )
    return tmp_path


def test_node_package_documentation_feeds_index_decisions_and_glossary(node_repo: Path) -> None:
    """Source: design.md#generated-docs: TypeScript/JavaScript @packageDocumentation blocks are read."""
    files = generate(node_repo)
    assert "## `orders`" in files["docs/generated/index.md"] and "Orders: takes and keeps orders." in files["docs/generated/index.md"]
    assert "Never imports: web" in files["docs/generated/index.md"]
    assert "## `main`" in files["docs/generated/index.md"] and "Main: starts the server." in files["docs/generated/index.md"]
    assert "orders.test" not in files["docs/generated/index.md"]
    assert "- `orders`: Orders are cancelled, never deleted. (owner)" in files["docs/generated/decisions.md"]
    assert "- **order** (`orders`): a request to buy." in files["docs/generated/glossary.md"]


def test_node_cuj_comment_names_the_test(node_repo: Path) -> None:
    """Source: design.md#generated-docs: a `// cuj:` comment names its test."""
    cujs = generate(node_repo)["docs/generated/cujs.md"]
    assert "sees it marked cancelled. (`src/orders/orders.test.ts::cancel order`)" in cujs
    assert "plain" not in cujs


def test_node_cuj_comment_without_a_test_call_fails(node_repo: Path) -> None:
    """Source: coding.md#failure: a CUJ that names no test fails loudly."""
    put(node_repo, "tests/bad.spec.ts", "// cuj: A journey with nothing under it.\nconst x = 1;\n")
    with pytest.raises(GenDocsError, match="tests/bad.spec.ts:1: '// cuj:'"):
        generate(node_repo)


def test_node_files_ignored_without_package_json(repo: Path) -> None:
    """Source: design.md#generated-docs: Node files are read only in a folder with a package.json at or above it."""
    put(repo, "src/shop/pages/app.js", "/** App: page script. */\n")
    assert "app" not in generate(repo)["docs/generated/index.md"].split("## `shop.web`")[0].split("## `shop.orders`")[0]
    assert "pages" not in generate(repo)["docs/generated/index.md"]


def test_wrapped_never_imports_keeps_its_continuation_lines(repo: Path) -> None:
    """Source: design.md#the-package-docstring: the Never imports line, however wrapped."""
    put(repo, "src/shop/web.py", '"""Web: the HTTP surface.\n\nNever imports: shop.orders,\n    shop.payments\n"""\n')
    assert "Never imports: shop.orders, shop.payments" in generate(repo)["docs/generated/index.md"]


@pytest.fixture
def rust_repo(tmp_path: Path) -> Path:
    put(tmp_path, "pyproject.toml", '[tool.metalm-gendocs]\nroots = ["app/src-tauri/src", "app/src"]\n')
    put(
        tmp_path,
        "app/src-tauri/src/lib.rs",
        """
        #![allow(dead_code)]
        //! Studio: turns manifests into audio.
        //!
        //! Never imports: ui
        //!
        //! Decisions:
        //! - The app writes only state files. (owner)
        //!
        //! Terms:
        //! - **take**: one rendered clip of a sentence.

        pub mod stitch;
    """,
    )
    put(
        tmp_path,
        "app/src-tauri/src/stitch.rs",
        """
        //! Stitch: joins takes into a chapter.

        /// cuj: The owner stitches a chapter in the app, and sees one file per chapter.
        ///
        /// Two takes in, one chapter file out.
        #[test]
        #[ignore]
        fn stitches_a_chapter() {}

        /// Not a module doc.
        fn helper() {}
    """,
    )
    put(tmp_path, "app/src-tauri/target/debug/build.rs", "//! Build output: never read.\n")
    put(tmp_path, "app/package.json", '{"name": "studio"}\n')
    put(tmp_path, "app/src/index.ts", "/** @packageDocumentation\n * Studio UI: the window.\n */\nexport {};\n")
    put(tmp_path, "app/src/__tests__/ui.test.ts", '// cuj: The owner opens a book in the app, and sees its chapters.\ntest("opens a book", () => {});\n')
    return tmp_path


def test_rust_inner_docs_feed_index_decisions_and_glossary(rust_repo: Path) -> None:
    """Source: design.md#generated-docs: Rust //! module docs are read."""
    files = generate(rust_repo)
    index = files["docs/generated/index.md"]
    assert "## `app/src-tauri/src`" in index and "Studio: turns manifests into audio." in index
    assert "Never imports: ui" in index
    assert "## `app/src-tauri/src/stitch`" in index and "Stitch: joins takes into a chapter." in index
    assert "Build output" not in index and "Not a module doc" not in index
    assert "Not covered" not in index
    assert "- `app/src-tauri/src`: The app writes only state files. (owner)" in files["docs/generated/decisions.md"]
    assert "- **take** (`app/src-tauri/src`): one rendered clip of a sentence." in files["docs/generated/glossary.md"]


def test_rust_cuj_doc_line_on_the_test_fn(rust_repo: Path) -> None:
    """Source: design.md#generated-docs: a Rust CUJ is a `/// cuj:` doc line on the test."""
    cujs = generate(rust_repo)["docs/generated/cujs.md"]
    assert "sees one file per chapter. (`app/src-tauri/src/stitch.rs::stitches_a_chapter`)" in cujs


def test_rust_cuj_on_a_plain_fn_fails(rust_repo: Path) -> None:
    """Source: coding.md#failure: a Rust CUJ on a non-test fn fails loudly."""
    put(rust_repo, "app/src-tauri/src/bad.rs", "/// cuj: A journey on a plain fn.\nfn x() {}\n")
    with pytest.raises(GenDocsError, match="app/src-tauri/src/bad.rs:1: '/// cuj:' must document a #\\[test\\] fn"):
        generate(rust_repo)


def test_rust_plain_comment_cuj_names_the_doc_form(rust_repo: Path) -> None:
    """Source: cli.md#output-and-errors: the error names the fix (the doc-line form)."""
    put(rust_repo, "app/src-tauri/src/bad.rs", "// cuj: Wrong form.\n#[test]\nfn x() {}\n")
    with pytest.raises(GenDocsError, match="bad.rs:1: a Rust CUJ is a doc line"):
        generate(rust_repo)


def test_node_project_below_the_root_is_read_from_an_extra_root(rust_repo: Path) -> None:
    """Source: design.md#generated-docs: roots adds a sub-project outside src."""
    files = generate(rust_repo)
    assert "## `app/src`" in files["docs/generated/index.md"] and "Studio UI: the window." in files["docs/generated/index.md"]
    assert "sees its chapters. (`app/src/__tests__/ui.test.ts::opens a book`)" in files["docs/generated/cujs.md"]


def test_nested_node_project_under_src_is_read(repo: Path) -> None:
    """Source: design.md#generated-docs: any folder with a package.json at or above it."""
    put(repo, "src/shop/web/package.json", '{"name": "page"}\n')
    put(repo, "src/shop/web/src/App.tsx", "/** App: the page.\n *\n * Decisions:\n * - The page polls; no sockets.\n */\nexport {};\n")
    assert "- `shop/web/src/App`: The page polls; no sockets." in generate(repo)["docs/generated/decisions.md"]


def test_roots_must_be_a_list_of_strings(repo: Path) -> None:
    """Source: coding.md#failure: malformed config is an error naming the key."""
    put(repo, "pyproject.toml", '[tool.metalm-gendocs]\nroots = "app"\n')
    with pytest.raises(GenDocsError, match="roots must be a list of strings"):
        generate(repo)
