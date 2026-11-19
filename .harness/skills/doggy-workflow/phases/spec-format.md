## Required format

Create the spec file with the lifecycle command, then fill it in:

```sh
python3 .harness/bin/spec_lifecycle.py new --run-id ID --name <kebab-name>
```

It copies `.harness/skills/doggy-workflow/spec-template.md` to `agent-docs/specs/<run-id>-<kebab-name>.md`, fills in the frontmatter (version 1, the run id, status `draft`, the current commit as `base_commit`), and prints the path. Keep every heading of the template, in its order: the lifecycle check refuses a spec that lacks one. Replace each `<...>` placeholder, and add rows under the header row of each table.

`# Steps` and `# Session Memory` exist only in a stepped spec (see Stepped specs); every other spec ends at the Version Log, so delete both sections from the file of a spec without steps.

Every intent, requirement, Case, quality requirement, obligation, assumption, and open question has a stable id. Each applicable quality characteristic has at least one quality requirement. Each quality requirement defines the measured property and context, method and input quantities, unit, threshold and pass direction, evidence procedure, and source. ISO/IEC 25023 supplies measure concepts and ISO/IEC/IEEE 29119-4 supplies test design techniques with their coverage measures; neither supplies project-specific pass thresholds or coverage targets. Main sets both as defaults in `# Assumptions and Defaults`.

`level` is `normal`, `boundary`, `error`, or `edge`; include every level or a `none — <reason>` row. Error rows name both signal and post-failure state. Implementation and Tests paths are disjoint. The implementer never reads Tests; test roles never read Implementation.

`# Alternatives` holds one row for each significant decision's option that a reasonable engineer could have picked, whoever decided. `# Open Questions` holds what approval left unknown and what the work turns up later; write `none` when there is nothing. `# Completion Questions` holds the questions for the completion check and the closing quiz (see Quiz). Only main uses it: it restates the brief's result, is no requirement, Case, or oracle, and where it conflicts with a requirement the requirement holds. All three are plan content: they change only by amendment, except the `asked` column of `# Completion Questions`, which main fills at each closing like Workflow Control. At completion every open question is `settled` or `deferred`.
