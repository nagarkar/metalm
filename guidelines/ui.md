# UI
(owner) Every rule in this file is the owner's.
Scope: the layout and navigation of every served page. Serving, restarting and browser checks: `operations.md`. Tests for pages: `testing.md`.

## Findable
- **Done means findable.** Handing over a UI feature gives the click path from the home page ("Section → item → the part that changed") and a screenshot taken on the real server. A feature the owner cannot reach from that path is not done.
- **A card is one target.** The whole card opens its item. A secondary action inside a card is a button or a link layered above the card's link, never the only way in.
- **No feature behind small text alone.** The way into a page is a card, a nav chip or a full-size button, not a small link in a corner.
- **A list card says what is inside.** Beside its numbers it carries one line of what waits on the far side (e.g. "3 items · 1 waiting for you · last run 8 PM"), so the owner knows whether to open it.

## One object, one page
- What the owner thinks of as one thing gets one page. Editing it happens on that page, behind an Edit toggle on the part being edited, never on a sibling page.
- A separate page is for a different thing (a detail view of something else), not for a different mode of the same thing.
- **Why:** a "setup" page beside a "view" page for the same thing makes the owner ask which one is the thing. Such splits follow build order, not use.

## Readable at every width
- **Labels stay next to their values.** A label-and-value block is capped at about 480 px or laid out as a compact grid; it never spans the page. Widening the page for one wide table must not stretch every card with it.
- **The main action is the most visible thing on the page;** status numbers come second.
- The desktop and 375 px check (`operations.md#browser-checks`) asks two readability questions beyond "it renders": can each number be read with its label at a glance, and is the next thing the owner would do the most visible thing?

## Brand
- **Every app wears the SuperLM family mark.** Each repo with a served page or app window has its own icon in the SuperLM style (`brand/` in metalm): the rounded gradient tile, one bold white letter, the green spark top right. The app's own letter and gradient tell it apart; the shape, letter weight and spark never change.
- **Made by metalm, copied into the repo.** A new app gets a row in `APPS` in `tools/notifier/make_brand.py` (a hue apart from the other apps and from the green spark), then `python3 tools/notifier/make_brand.py --app <repo> brand/<repo>/`. The repo copies that folder (favicon, touch and PWA icons, logo, light and dark wordmarks) into its served assets; never hand-draw or restyle it there.
- **Every served page shows it:** `favicon.ico`, `favicon-32.png` and `apple-touch-icon.png` linked in the page head, and the icon or wordmark in the page header.
