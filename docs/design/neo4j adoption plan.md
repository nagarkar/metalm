# Neo4j adoption plan

Status: draft, 2026-11-04. Living document; updated as the plan changes.

## Decision

Adopt Neo4j Community Edition to learn which graph use cases pay off. Isolate the
dependency from day one so that outgrowing Community means migrating to another
engine, not rewriting one. Do not build a homegrown graph engine.

## Why Neo4j Community first

- Cheapest way to find out whether a graph model pays off for our problems.
- Cypher is now the ISO GQL standard (Cypher 25 since Neo4j 2025.06). Modelling
  and query knowledge transfers to Memgraph, FalkorDB, Apache AGE, Kuzu and others.
- Best-in-class planner, tooling (Browser, Bloom), docs, Graph Data Science
  library, vector index (VECTOR type since 2025.10), and LLM-framework integrations.
- Single node, one database is far from a ceiling for most of our workloads.

## Community Edition limits (GPLv3)

One database, no clustering, no RBAC, no online backup, no GDS enterprise
features, no sharding. Everything multi-node or multi-tenant is Enterprise
(closed, paid) or Aura (managed).

## Why not a homegrown engine later

The gated features (consensus-based clustering, online backup, sharding, RBAC,
a planner that stays fast at scale) are years of database-team work. A homegrown
store would be the least-tested component carrying the most important data.
The one exception: if the "enterprise" need is a single in-process adjacency
structure with a few fixed traversals, that is a data structure, not a
database, and is fine to write.

## Keeping the exit open

1. All Cypher lives in one module, not scattered through application code.
2. Plain Cypher over APOC and Neo4j-only procedures wherever it does the job.
3. Bolt driver behind a thin adapter of our own so the connection layer can swap.
4. An export path exercised regularly (nightly dump to CSV or Parquet); data is
   never only inside the store.
5. Graph as a derived or secondary store where possible; source of truth stays
   in Postgres or files, so migration is a rebuild, not a conversion.

## Exit options when Community is outgrown

| Option | License | Fit |
|---|---|---|
| Memgraph | BSL 1.1 (not OSI) | Near drop-in: Cypher, Bolt. In-memory. HA paid. |
| FalkorDB | SSPL (not OSI) | Cypher on Redis; many small graphs, GraphRAG. |
| Apache AGE | Apache 2.0 | openCypher in Postgres; fully open; slower on deep traversals. |
| Kuzu | MIT | Embedded analytical engine; upstream archived Oct 2025, forks only. |
| JanusGraph / NebulaGraph / Dgraph | Apache 2.0 | Distributed scale; Gremlin, nGQL or DQL, not Cypher. |
| Neo4j Enterprise or Aura | Commercial | Pay when the ceiling is actually hit. |

Decide only when the ceiling is reached. Any of these is cheaper and safer than
a rewrite.

## Next steps

- [ ] Pick the first use case(s) to model.
- [ ] Stand up Neo4j Community locally (Docker or launch agent, per the served-apps
      conventions).
- [ ] Write the Cypher module and driver adapter.
- [ ] Add the export job.
- [ ] Revisit this plan after the first use case ships.

## Open questions

- Which repos' data are the first candidates for a graph model?
- Does the graph become a served app on the tailnet, or stay internal?
