# UI
Status: DRAFT — not yet ratified by the owner.
Scope: the layout and navigation of every served page. Serving, restarting and browser checks: `operations.md`. Tests for pages: `testing.md`.

Learned from tradelm, 2026-10-03: every feature claimed was built and served, yet the owner found none of them. They sat two clicks from the home page behind small corner links, the account was split over two pages, and on desktop each label sat a screen's width from its number.

## Findable
- **Done means findable.** Handing over a UI feature gives the click path from the home page ("Accounts → AI Flyers → Last signals") and a screenshot taken on the real server. A feature the owner cannot reach from that path is not done.
- **A card is one target.** The whole card opens its item. A secondary action inside a card is a button or a link layered above the card's link, never the only way in.
- **No feature behind small text alone.** The way into a page is a card, a nav chip or a full-size button, not a small link in a corner.
- **A list card says what is inside.** Beside its numbers it carries one line of what waits on the far side (e.g. "3 tickers · 0 waiting · last signal HOLD"), so the owner knows whether to open it.

## One object, one page
- What the owner thinks of as one thing (an account, a book, a SKU) gets one page. Editing it happens on that page, behind an Edit toggle on the part being edited, never on a sibling page.
- A separate page is for a different thing (a ticker's chart is not the account), not for a different mode of the same thing.
- **Why:** a "setup" page beside a "view" page for the same account made the owner ask which one is the account. The split followed build order, not use.

## Readable at every width
- **Labels stay next to their values.** A label-and-value block is capped at about 480 px or laid out as a compact grid; it never spans the page. Widening `main` for one wide table (a seventeen-column desk) must not stretch every card with it.
- **The main action is the most visible thing on the page;** status numbers come second.
- The desktop and 375 px check (`operations.md#browser-checks`) asks two readability questions beyond "it renders": can each number be read with its label at a glance, and is the next thing the owner would do the most visible thing?
