# Neo4j graph use cases from "Make Your AI Agents Predictable With Graph Engineering"

Talk: Zachary Blumenfeld (Neo4j), YouTube id `g_NgCLTibiM`. Video: https://www.youtube.com/watch?v=g_NgCLTibiM

## Thesis

Blumenfeld defines graph engineering as designing agent work as an explicit graph in which nodes do work and edges route state, and argues the term is new while the mechanisms (state machines, workflow graphs, knowledge graphs) are old; what changed is their relation to agents. He separates three kinds of graph: execution graphs (the runtime orchestration most frameworks already do), context graphs (decision traces and memory joined to domain data), and procedural graphs (skills and procedures compiled into graph form). The talk's central claim is that the second and third kinds, stored in a graph database next to the data rather than living only inside an agent runtime, buy three things: predictability (the agent is constrained to a known path), governance and auditability (every step is traceable and reviewable), and portability (the graph becomes a stored artefact, such as a skill, that any agent harness can run). The loan-approval demo shows the full loop: run an agent over a context graph, capture its reasoning traces, compile the successful runs into a graph-shaped skill, execute that skill deterministically through a small CLI, store the runs back in the graph, and as a result run faster, cheaper, and on a smaller model.

## Use cases

### 1. Execution graphs for agent orchestration

The familiar form of graph engineering: a workflow graph inside the agent harness where routers and agents are nodes and edges carry state between them (LangGraph and similar frameworks, multi-agent research setups). The speaker treats this as the baseline that most of the audience already does, and positions the rest of the talk as a way to get its benefits in a more portable form.

- Data/graph shape: runtime-only graph of agent and router nodes with state-carrying edges; not necessarily stored in a database.
- Problem solved: constraining the sequence of agent steps so the path is predictable rather than improvised each run.
- Timestamps: [1:46](https://www.youtube.com/watch?v=g_NgCLTibiM&t=106), [3:55](https://www.youtube.com/watch?v=g_NgCLTibiM&t=235)

### 2. Context graphs: decision traces joined to domain data

A context graph records instances of what an agent did (decisions, tool calls, outcomes) and links those traces to the entities in the domain they concern. Rather than logging traces off to the side, they become nodes in the same graph as the business data, so a later run can discover that a case, person or entity already has history.

- Data/graph shape: trace nodes (steps, tool calls, decisions) with edges to domain entity nodes; timestamps on each step.
- Problem solved: agents losing the connection between what they decided and the data the decision was about; enables precedent lookup and audit.
- Timestamps: [2:05](https://www.youtube.com/watch?v=g_NgCLTibiM&t=125), [4:17](https://www.youtube.com/watch?v=g_NgCLTibiM&t=257)

### 3. Procedural graphs: procedures and skills as graphs

A procedure (a skill, a policy workflow) is represented as a graph whose steps are not necessarily agents: some are deterministic scripts, some are calls to a decision model, some are validation or escalation gates. The speaker says this category is under-discussed and that understanding it also explains what execution graphs are trying to achieve, but in a more portable and efficient way.

- Data/graph shape: step nodes typed by kind (script, decision, router, validation, escalation) with directed edges for ordering and branching.
- Problem solved: capturing "how to do X" as explicit, inspectable structure instead of prose the agent must reinterpret every time.
- Timestamps: [2:17](https://www.youtube.com/watch?v=g_NgCLTibiM&t=137), [2:42](https://www.youtube.com/watch?v=g_NgCLTibiM&t=162)

### 4. Portable graph artefacts stored outside the runtime

Instead of a graph that exists only while an agent framework executes it, the graph is persisted in a knowledge layer and moved between runtimes. The payoff is interoperability (any harness that can read the artefact can run the logic) and a simpler stack, because orchestration knowledge is data rather than code locked into one framework.

- Data/graph shape: the procedural or context graph stored in Neo4j, exportable to a serialised format (the demo uses a graph-shaped YAML skill).
- Problem solved: lock-in to one agent framework; duplicated orchestration logic across runtimes.
- Timestamps: [3:33](https://www.youtube.com/watch?v=g_NgCLTibiM&t=213), [4:29](https://www.youtube.com/watch?v=g_NgCLTibiM&t=269), [9:09](https://www.youtube.com/watch?v=g_NgCLTibiM&t=549)

### 5. Knowledge layer between systems of record and agents

Neo4j is positioned as a layer that sits between upstream sources (Databricks, BigQuery, Snowflake, documentation, Obsidian-style markdown) and any agent or runtime. Data from multiple sources is loaded into the graph to form this layer, and standard protocols and artefacts live inside it so a graph engineering process becomes available to any agent that connects. The speaker notes that much of the AI tooling shown is a "graph AI" layer on top of the core database and analytics.

- Data/graph shape: a unified property graph integrating entities from several source systems plus documents, with memory and procedure graphs attached.
- Problem solved: agents retrieving from many disconnected systems with no shared, governed place where their logic and memory can live alongside the data.
- Timestamps: [4:42](https://www.youtube.com/watch?v=g_NgCLTibiM&t=282), [5:14](https://www.youtube.com/watch?v=g_NgCLTibiM&t=314)

### 6. Agent memory as a context graph (short-term, long-term, reasoning)

Neo4j's memory model has three layers in one graph: short-term memory as conversation history, long-term memory as entities extracted from conversations or loaded from data, and reasoning or decision traces. All three are connected, so a conversation links to the entities it mentions and to the trace of how the agent reasoned about them. The reference implementation is the Neo4j Agent Memory Service (NAMS).

- Data/graph shape: conversation and message nodes, extracted entity nodes, trace and step nodes, with edges tying each layer to the others.
- Problem solved: agent memory that is either flat text or a vector store with no structure, making recall, provenance and entity-level reasoning hard.
- Timestamps: [6:01](https://www.youtube.com/watch?v=g_NgCLTibiM&t=361), [8:49](https://www.youtube.com/watch?v=g_NgCLTibiM&t=529)

### 7. Compiling a written skill into a graph (research result)

A Neo4j workshop paper describes taking a skill as written material (a SKILL.md plus scripts, references and assets) and compiling it into a graph of decision nodes, routing points and scripts to execute, converting prose into deterministic steps where possible. Forcing the agent to run that graph rather than read the prose raised task reward across diverse hard tasks (physics, computer science, security and others), and allowed a smaller model (Sonnet at the time, now Haiku) to do the work.

- Data/graph shape: skill graph with nodes for decisions, routing points and script executions, linked to the source documents and assets.
- Problem solved: prose skills are interpreted inconsistently by the model; graph form makes the procedure reproducible and cheaper to run.
- Timestamps: [6:34](https://www.youtube.com/watch?v=g_NgCLTibiM&t=394), [7:28](https://www.youtube.com/watch?v=g_NgCLTibiM&t=448)

### 8. Distilling skills from memory graphs with provenance and drift tracking

The same compilation idea applied to memory: take the context graph of past decision traces and distill a skill from it, keeping the skill connected in the same graph to the traces and data it came from. Each step of the skill therefore has provenance, versioning and history, so a human can inspect where a tool call came from, assess drift over time, and edit the skill inside NAMS.

- Data/graph shape: skill nodes with edges back to the trace steps and data they were derived from; version nodes over time.
- Problem solved: skills that are hand-written and unversioned, with no link to the evidence that justified them; governance of agent behaviour as it evolves.
- Timestamps: [8:09](https://www.youtube.com/watch?v=g_NgCLTibiM&t=489), [8:36](https://www.youtube.com/watch?v=g_NgCLTibiM&t=516)

### 9. Compliance and audit-report automation with entity resolution (asset management)

Consultancies working with asset managers use graphs to automate audit reports where the inputs come from multiple sources: compliance documentation, and entity records whose tickers and names differ across databases and must be resolved. Expressing the required logic as a graph that sits next to the resolved data lets the agent automate the report in a governed, trustworthy way.

- Data/graph shape: resolved entity nodes (one node per real-world company linking multiple identifiers), compliance document nodes, and a procedure graph for the report logic.
- Problem solved: cross-source entity ambiguity and the need for an auditable, policy-following path when automating regulated reporting.
- Timestamps: [9:21](https://www.youtube.com/watch?v=g_NgCLTibiM&t=561), [9:44](https://www.youtube.com/watch?v=g_NgCLTibiM&t=584)

### 10. Configuration graphs for geographically varying regulations (Uber)

Uber models compliance and regulatory configuration as a graph: rules vary by geography and by vehicle component, and the underlying facts are scattered across many microservices. Putting the logic alongside the data in a graph lets them operationalise the lookups and rules rather than hand-stitching service calls.

- Data/graph shape: region nodes, vehicle component nodes, regulation and configuration nodes, with edges expressing which rule applies where and to what.
- Problem solved: answering "what applies here, for this part" across a sprawl of services with regionally varying rules.
- Timestamps: [10:13](https://www.youtube.com/watch?v=g_NgCLTibiM&t=613)

### 11. GraphRAG for loan approval over documents plus structured data

The demo's starting point: a question about approving a loan for a small business is answered by an agent crawling a graph that joins an uploaded business plan PDF, past transaction data pulled from Databricks, lending policy data, and previously made decisions. The agent can discover prior loans, prior errors or precedents for the same applicant and produce a recommendation with an audit trail.

- Data/graph shape: document chunk nodes from the PDF, transaction and account nodes from the warehouse, policy nodes, and past decision nodes, all linked to the applicant entity.
- Problem solved: retrieval that needs to connect unstructured documents, structured records and history for one entity, with the path of evidence visible.
- Timestamps: [11:24](https://www.youtube.com/watch?v=g_NgCLTibiM&t=684), [12:03](https://www.youtube.com/watch?v=g_NgCLTibiM&t=723), [12:35](https://www.youtube.com/watch?v=g_NgCLTibiM&t=755)

### 12. Persisting reasoning traces and comparing runs

Each agent run's reasoning trace is stored in the graph as timestamped steps with their tool calls, attached to the conversation. Querying two runs of the same policy side by side shows chains of different length (one found a precedent, the other did not), which makes visible that nothing enforces a consistent path and that confidence judgements at decision points (approve, deny, escalate) are uncalibrated.

- Data/graph shape: conversation node -> ordered step nodes with timestamps, tool-call nodes, decision nodes carrying confidence.
- Problem solved: diagnosing non-determinism and inconsistency in agent behaviour; building the evidence base for compiling a better procedure.
- Timestamps: [13:04](https://www.youtube.com/watch?v=g_NgCLTibiM&t=784), [13:32](https://www.youtube.com/watch?v=g_NgCLTibiM&t=812), [13:50](https://www.youtube.com/watch?v=g_NgCLTibiM&t=830)

### 13. Compiling successful runs into a graph-shaped skill (YAML)

The traces from successful though inconsistent runs are scraped and compiled into a skill whose core is a graph expressed in YAML, bundled with scripts, assets, optional reference resources, and the source policy documentation, plus instructions telling the agent how to run it. Because the format is deterministic and serialised, the skill can be loaded into other tooling and back into the graph database.

- Data/graph shape: a skill package whose graph YAML lists steps, routers and scripts, with links to source policy docs for traceability; mirrored as nodes in Neo4j.
- Problem solved: turning observed good behaviour into a reusable, portable procedure with traceability to the policy it implements.
- Timestamps: [14:28](https://www.youtube.com/watch?v=g_NgCLTibiM&t=868), [14:46](https://www.youtube.com/watch?v=g_NgCLTibiM&t=886), [15:22](https://www.youtube.com/watch?v=g_NgCLTibiM&t=922)

### 14. Deterministic skill execution through a CLI with typed decision models

A small CLI wraps the compiled skill so the agent invokes it rather than deciding routing itself. The procedure first checks hard policy rules in execution scripts (auto-approve or auto-deny), then routes borderline cases to a typed decision model (Zod or TypeSafe style) that outputs a risk tier, a material-exposure flag and an outcome, then branches on whether to escalate to a human, and otherwise has the agent write a report which passes through a check-and-lint loop. The speaker also suggests using such typed models to calibrate the confidence scores that free-form agents produce.

- Data/graph shape: the procedural graph with script nodes, a decision-model node with a constrained output schema, an escalation router, a report node and a validation cycle.
- Problem solved: the agent spending tokens and making errors on routing; uncalibrated confidence at approve/deny/escalate points; missing human-in-the-loop gates.
- Timestamps: [14:03](https://www.youtube.com/watch?v=g_NgCLTibiM&t=843), [15:34](https://www.youtube.com/watch?v=g_NgCLTibiM&t=934), [16:06](https://www.youtube.com/watch?v=g_NgCLTibiM&t=966), [16:50](https://www.youtube.com/watch?v=g_NgCLTibiM&t=1010)

### 15. Storing skill runs in the graph for governance and observability

Every execution of the compiled skill is persisted as a run node with its individual step executions, kept beside the business data. A small inspector shows run status, what was approved or denied, and which branches a run took; because it is a graph, you can also ask aggregate questions such as which branches are ever taken, which never are, and which steps have failed.

- Data/graph shape: run nodes -> step-execution nodes with status, linked to the skill's step definitions and to the entities acted on.
- Problem solved: observability and governance of agent procedures over time without building a separate logging system; evidence for improving the skill.
- Timestamps: [17:37](https://www.youtube.com/watch?v=g_NgCLTibiM&t=1057), [18:04](https://www.youtube.com/watch?v=g_NgCLTibiM&t=1084), [18:20](https://www.youtube.com/watch?v=g_NgCLTibiM&t=1100)

### 16. Cost and latency reduction by moving routing out of the LLM

With routing and policy checks in scripts and the decision step in a small typed model, the frontier model is no longer needed for most of the work. The speaker reports the task going from roughly 2.7 minutes of model time with a large model on the raw graph to about half that with the compiled procedure, and further down with Haiku, with wall-clock time dropping from about seven and a half minutes to half a minute to two minutes and cost falling sharply, while answers stayed correct.

- Data/graph shape: same procedural graph as above; the point is that the graph carries the control flow so the model carries less.
- Problem solved: expensive, slow, poorly governed agent runs on tasks that are mostly procedure.
- Timestamps: [18:59](https://www.youtube.com/watch?v=g_NgCLTibiM&t=1139), [19:32](https://www.youtube.com/watch?v=g_NgCLTibiM&t=1172)

## Resources mentioned

- Neo4j Aura (cloud database, free credits), the NODES speaker event, a startup program, and the labs code for AIP (skill compilation) and NAMS (agent memory service): [20:02](https://www.youtube.com/watch?v=g_NgCLTibiM&t=1202)
