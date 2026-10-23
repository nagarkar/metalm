"""Shared fixtures: a small throwaway Python repo for metalm-gendocs to read."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


def put(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip())


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    put(
        tmp_path,
        "src/shop/__init__.py",
        '''
        """Shop: sells things to people.

        Second paragraph is not in the index.
        """
    ''',
    )
    put(
        tmp_path,
        "src/shop/orders/__init__.py",
        '''
        """Orders: takes and keeps orders.

        Never imports: shop.web

        Decisions:
        - An order is never deleted; it is cancelled. Why: refunds need the row.
          Enforced by: tests/test_orders.py::test_cancel. (owner)
        - Order ids are ULIDs.

        Terms:
        - **order**: a request to buy, with lines and a total.
        """
    ''',
    )
    put(tmp_path, "src/shop/web.py", '"""Web: the HTTP surface."""\n')
    put(tmp_path, "src/shop/orders/store.py", '"""Store: not an area (module inside a subpackage)."""\n')
    put(
        tmp_path,
        "tests/test_orders.py",
        """
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
    """,
    )
    return tmp_path
