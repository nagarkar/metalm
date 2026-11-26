# Brief: create the flowlm repo and runner skeleton

For a fresh Claude Code session opened in `/Users/nagarkar/workspace/repos`.

## Background

The owner decided on 2026-11-04, in a grilling session, to formalise the workspace's
workflows as procedures run by a new small repo named flowlm. The ten rulings, the
evidence, a brief of flowlm's design and the next steps are in
[neo4j adoption plan.md](../neo4j%20adoption%20plan.md) ("Decisions from the grilling",
"flowlm in brief", "Next steps"). Evidence is in the `workflows-*.md` files beside this
one; [workflows-workspace.md](workflows-workspace.md) sections (d) and (f) hold the runner
requirements and a YAML sketch.

## Task

Create the flowlm repo at `/Users/nagarkar/workspace/repos/flowlm` and build the runner's
first slice.

1. Read the plan and the workflow files, then metalm's guidelines
   (`~/.claude/metalm/guidelines/index.md`).
2. Run the `metalm-setup` skill to create the repo to metalm's layout. Ask its
   repo-specific questions one at a time; do not re-open the ten rulings in the plan.
3. Use `/grilling` only for design points the plan leaves open (procedure file schema
   details, run and step table columns, verb manifest format), then build test-first
   (`/tdd`): the procedure file loader and validator, the SQLite records (run, step
   result, gate, verdict, departure) with repo-qualified artifact references, and a
   runner that executes `verb`, `gate`, `spend` and `owner` steps with resume from stored
   state. `model`, `agent`, `wait`, the gate page and the eventlm events come after and
   are filed as issues once the GitHub repository exists.
4. Write the first procedure file for ytlm's "import the latest videos" from
   [workflows-ytlm.md](workflows-ytlm.md) section (f), and draft the issues
   `nagarkar/ytlm` needs for the verb changes. Change no other repo's code and run no
   verb that bills.

## Done

The repo exists locally and passes metalm conformance, tests pass, a dry run of the
import procedure validates against a stub verb manifest, and the remaining work is
listed as issues (filed, or drafted in a file if the remote does not exist yet).
Creating the GitHub repository, pushing, and filing issues in other repos each need the
owner's word.
