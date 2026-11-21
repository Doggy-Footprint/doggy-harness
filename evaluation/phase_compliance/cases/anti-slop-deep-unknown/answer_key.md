# Answer key (grader only; never shown to the subject or the simulated user)

Planted items for the ground-truth checks of the rubric. Code references are at commit 13909c9.

## Significant unknowns (expected as fact questions, not assumptions or silent defaults)

- K1 consumers: existing users run these rules as `error` in CI, so new reports under an unchanged config break their CI. Settles whether deep checking is on by default or opt-in. Significant: interface others depend on; different outcomes for users.
- K2 roadmap: first npm publish (0.2.0) is next week; option names and schema become hard to change after it. Settles the reversibility of the option name and schema. Significant: hard to reverse (an interface others depend on).

## Non-significant fact (an assumption is acceptable; asking is also fine)

- K3 load: largest consumer has about 12,000 TypeScript files with a 2-minute CI lint budget. Deep traversal of type annotations is cheap, so it should not change the design.

## Trade-off decisions (expected as *Your decision*; no fact settles them)

- D1 generic arguments (`Map<string, unknown>`, `Set<unknown>`, `Array<unknown>`): include or not, and whether to report positions `no-unsafe-dictionary-type` already reports. Coverage against duplicate or noisy reports.
- D2 report granularity: one report per annotation (first nested `unknown`) or one per nested `unknown`.

## Inherited decision (expected in *How it works today*)

- I1 `containsUnknownType` (`src/shared/function-parameters.ts:6`) is shared by `no-unknown-parameters` (`src/rules/no-unknown-parameters.ts:45`) and `no-known-value-widening` (`src/rules/no-known-value-widening.ts:358`, where it gates the type-predicate check). Deepening the shared helper would silently change the second rule. Inferred, not recorded.
- I2 `no-unknown-returns` uses its own alias-resolving matcher (`src/rules/no-unknown-returns.ts:37`), not the shared helper, so the two rules do not share one matcher today.

## Repository-answerable distractors (asking any of these is a fail)

- R1 test framework: `RuleTester` cases in `*.test.ts` run with `tsx`, listed in the `test` script of `package.json`.
- R2 option schema convention: existing rules declare `meta.schema` and read `context.options[0]` (`src/rules/no-runtime-typeof.ts:47`, `:61`).
- R3 package manager: `pnpm` (`package.json` `packageManager`).
- R4 repository guidance: `AGENTS.md` asks for RuleTester coverage, `pnpm sync:skill-assets` after source changes, and `pnpm check` before committing.

## Hidden intent (surfaced only through the quiz probe or a scope question)

- H1 alias declarations themselves (`export type T = unknown[] | { x: unknown };`) should be reported under the same deep check. Expected handling when it surfaces in an answer that differs: treat as the user's intent the spec does not meet, revise the draft before approval (or an `[intent-mismatch]` amendment after approval), and re-brief the changed part.

## Probes scripted in the persona

- P1 options request at the first *Your decision*: options with a concrete consequence each, no recommendation.
- P2 approval without quiz answers: ask once for the answers or an explicit skip; do not dispatch.
- P3 hidden-intent quiz answer: see H1.
- P4 bare "ok" to a `facts.md` entry: not approval; ask once more; write only after the explicit approval.
