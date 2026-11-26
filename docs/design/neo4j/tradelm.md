# Neo4j assessment: tradelm

Written 2026-11-04 from a read of the code and docs only (no broker, account or server was touched).
Use case numbers refer to [usecases.md](/Users/nagarkar/workspace/repos/metalm/docs/design/neo4j/usecases.md).

## (a) What the repo does and where its data and decisions live

tradelm backtests pluggable strategies (each a pure `decide()`), re-runs a ticker-by-strategy grid
every night, turns each active run's decision into a signal, and submits a same-day limit order to
Alpaca only when the owner approves it on the Today page. Its state is one SQLite file per workspace
([db.py](/Users/nagarkar/workspace/repos/tradelm/src/tradelm/db.py), about 20 tables) plus JSON files:
the nightly grid (`analysis/grid_results.json` and saved daily series), a dated status snapshot per
session (`history/status-<date>.json`), portfolio imports and reports
(`portfolios/<name>/...`), and one folder per ticker for the latest "hedge fund report". Every
decision in the order path is deterministic code: strategy selection
([selection.py](/Users/nagarkar/workspace/repos/tradelm/src/tradelm/selection.py), logged in
`strategy_selections`), the decision and its sizing
([execution.py](/Users/nagarkar/workspace/repos/tradelm/src/tradelm/execution.py), one `signals` row
per run per night, holds included, with outcome, `blocked_by`, status and reason), the human gate
(`/api/resolve`, which re-checks the ledger and may shrink or reject), the fill (`trade_history`,
keyed back by `signal_id`), and the circuit breaker (`circuit_breaker_trips`, scored afterwards
against the road not taken). The only LLM in the repo is
[hedge_report.py](/Users/nagarkar/workspace/repos/tradelm/src/tradelm/hedge_report.py): TradingAgents
run as a subprocess on demand, advisory reading only, latest report kept per ticker; by design it
makes no signal, order or setting.

## The loan-approval analogue, examined

The talk's demo ends where tradelm began. Mapping its compiled procedure onto this repo:

| Loan demo (use case 14, 15) | tradelm today |
|---|---|
| Hard policy rules in scripts (auto-approve, auto-deny) | `process_decision`: ceiling, cash less reservations, stale data, paused run, no limit price; each gives a named `outcome` / `blocked_by` |
| Typed decision model with a constrained output | `decide()` returns buy / sell / hold; `signals.decision` has a CHECK constraint; the strategy is an immutable hashed row (`strategies`) |
| Escalation gate to a human | Every order is escalated: nothing is submitted without Approve, and approval re-checks the ledger |
| Runs stored for audit | `signals` (every evaluation, holds and failures included), `strategy_selections` (every night, not only switches), `trade_history`, `circuit_breaker_trips`, `job_runs` |
| Routing moved out of the LLM for cost | There was never an LLM in the route |

So the procedure the talk compiles out of agent traces already exists here as tested Python with
import contracts, and the run storage already exists as relational rows with foreign keys. The
audit question "why did this order happen" is a fixed chain: signal -> strategy -> selection that
night -> order -> fill -> ledger. That is four or five joins of known depth over a few thousand
rows a year, which SQLite answers instantly. There is no variable-depth traversal, no path-finding
and no many-to-many web anywhere in the order path. Copying it into Neo4j would duplicate
relational tables without adding a query SQL cannot already do, and it would add a second store
beside money-relevant data whose single-file simplicity is a deliberate property (the nightly job
must run with nothing else up).

## (b) Use cases that plausibly apply

### Use case 2 / 12 / 15: decision traces joined to domain data, run storage

- Shape: `(:Session {date})`, `(:Ticker)`, `(:Account)-[:HOLDS_SLOT]->(:AccountTicker)-[:OF]->(:Ticker)`,
  `(:Strategy {kind, params})`, `(:GridCell)-[:SCORED]->(:Strategy)`,
  `(:Selection)-[:PICKED]->(:Strategy)`, `(:Signal)-[:FROM]->(:Selection)`,
  `(:Signal)-[:COMPUTED_ON]->(:Session)`, `(:Approval)-[:RESOLVES]->(:Signal)`,
  `(:Order)-[:FROM]->(:Signal)`, `(:Fill)-[:OF]->(:Order)`, `(:BreakerTrip)-[:PAUSED]->(:Run)`.
- Improves: one query for the full provenance of an order, and aggregate questions such as "which
  `blocked_by` branches are ever taken" or "how often does approval shrink a buy".
- Replaces or sits beside: sits beside SQLite as a derived copy. Everything except the grid cell is
  already a row with a foreign key; the aggregate questions are `GROUP BY outcome`.
- The one real gap it would paper over: the evidence for a selection (the grid cell and its windows
  that night) lives in a JSON file that is overwritten nightly, and `signals` does not point at the
  `strategy_selections` row it followed. Both are fixed more cheaply in SQLite (a `selection_id`
  column; keep the winning cell's figures on the selection row) than by adding a graph.
- Rating: low value, medium effort. Not recommended.

### Use case 5 / 11: knowledge layer and GraphRAG around a ticker

- Shape: `(:Ticker)` as the shared entity, with `(:HedgeReport)-[:ABOUT]->(:Ticker)`,
  `(:Holding)-[:OF]->(:Ticker)` from Schwab portfolio imports, `(:Valuation)`, `(:Earnings)`,
  `(:Signal)`, and from other repos `(:TranscriptSegment)-[:MENTIONS]->(:Ticker)` (ytlm, podlm, beelm)
  and `(:Sector)<-[:IN]-(:Ticker)`.
- Improves: "show me everything I have on NVDA before I approve this buy": the signal, both views,
  the valuation reading, the latest hedge report's rating, what I hold of it in the real portfolio,
  and what a video or conversation said about it.
- Replaces or sits beside: sits beside everything; tradelm would be a contributor of a few node
  types to a graph owned elsewhere (corpuslm or metalm), not an owner of a graph. Inside tradelm
  alone, every one of these is already keyed by symbol and joined by the chart and Today pages.
- Honest caveat: the value is entirely cross-repo and depends on the transcript corpora having
  reliable ticker or company mentions, which is an entity-extraction job that does not exist yet.
  It also sits awkwardly with two owner rules: fundamental signals stay separate from technical
  ones, and the hedge report is advisory only. A page that puts transcript chatter beside an
  Approve button invites exactly the mixing those rules prevent.
- Rating: medium value if the cross-repo graph exists for other reasons, low otherwise; small
  effort for tradelm's share (a nightly export of tickers, holdings, signals and report ratings
  through the shared Cypher module).

### Use case 1 / 12: the hedge report's agent run

- Shape: `(:HedgeRun)-[:STEP]->(:AgentStep {role: analyst|bull|bear|trader|risk|pm})-[:NEXT]->...`,
  `(:HedgeRun)-[:ABOUT]->(:Ticker)`, `(:HedgeRun)-[:RATED]->(:Rating)`.
- Improves: comparing two runs for the same ticker (did the bear case change, or only the rating),
  and scoring ratings against what the price did afterwards, as `trips.py` does for breaker trips.
- Replaces or sits beside: today only the latest report is kept per ticker, as files. TradingAgents
  is already a LangGraph execution graph inside its own venv; tradelm deliberately keeps it at
  arm's length as a subprocess.
- Honest caveat: the useful part (keep every report, score the rating later) is a `hedge_reports`
  table with a date and a rating, not a graph. Step-level traces would mean instrumenting a
  third-party tool for an advisory feature.
- Rating: low value, medium effort. Not recommended; if rating history is wanted, add a table.

### Use case 9: entity resolution across sources

- Shape: `(:Company)-[:KNOWN_AS]->(:Symbol {source: schwab|alpaca|tiingo|yfinance})`.
- Improves: Schwab exports, Alpaca, Tiingo and yfinance spell some symbols differently (share
  classes, funds), and a ticker can be renamed.
- Replaces or sits beside: the `instruments` table and whatever normalisation the importers do.
- Rating: low value, small effort. A symbol-alias table does this; the universe is tens of tickers.

## (c) Use cases that do not apply

- 3, 7, 13 (procedural graphs, compiling a skill from prose or from runs): the order procedure is
  already deterministic code with tests and import contracts; there is no prose skill and no agent
  trace to compile from.
- 4 (portable graph artefacts): there is one runtime, the Python package; nothing needs to move
  between agent harnesses.
- 6 (agent memory): no conversational agent lives in this repo.
- 8 (distilling skills from memory with drift tracking): no memory graph and no skills in the
  talk's sense; strategy drift is already tracked by the nightly selection log and status snapshots.
- 10 (configuration graphs for varying rules): rules vary by one axis only (per account, per
  ticker), held in `config.toml` and a few columns.
- 14 (deterministic execution through a CLI with typed decisions): already built, as `tradelm
  run-daily` and `process_decision`.
- 16 (cost reduction by moving routing out of the LLM): no LLM is in the route to remove.

## (d) Ranked recommendation

1. **Nothing yet inside tradelm.** The repo is the talk's destination reached by another road:
   scripts for the rules, a typed decision, a human gate on every order, and runs stored for audit,
   all in one SQLite file with foreign keys. Its queries are fixed-depth joins over small tables.
   A graph copy would be a second store to keep in step beside money-relevant data, with no
   question it answers that SQL does not.
2. **If a cross-repo ticker or company graph is built for other repos, let tradelm feed it.** A
   read-only nightly export (tickers with sector and tier, portfolio holdings, signals and their
   outcomes, hedge report ratings) is a small job and keeps SQLite the source of truth, in line
   with the adoption plan's rule 5. Do this second, and only once the transcript side can name
   tickers reliably.

Two cheap SQLite improvements surfaced by the exercise, neither needing a graph: link each signal
to the selection row it followed and keep the winning grid cell's figures on that row; keep a
dated history of hedge report ratings so they can be scored later.

## (e) Open questions for the owner

- Do you ever ask a "why" question about an order that the Today and account pages cannot answer
  today? If yes, which one; it decides whether the selection-evidence gap is worth closing.
- Would you want transcript or conversation mentions of a ticker shown anywhere near an approval,
  given the rule that fundamental and advisory readings stay apart from the technical signal?
- Is hedge report history (every run kept, ratings scored against later prices) wanted at all, or
  is "latest only" the intended design?
- If a shared graph is stood up, is it acceptable for the nightly job to gain an export step that
  can fail without affecting signals (as the Sheets export does now)?
- Is tradelm's data allowed to leave its workspace at all? Holdings and order history in a shared
  graph on Community Edition have no access control.
