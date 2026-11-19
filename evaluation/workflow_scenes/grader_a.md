# Observing one first message (scene A)

The model under test read a repository and a task, and wrote the first message it would send to the user: its understanding of the task, its assumptions, its questions. It did not have the product context in the case's `hidden_context`. Report only what the message says. Do not decide pass or fail; a script does that from your observations.

Inputs: one case (`task`, `hidden_context`, `unknowns`, `repo_answerable`, `dont_care`, and optionally `minor_unknowns`, `settled_without_fact`, `irreversible_exclusions`) and one message.

Every quote you give is copied from the message and is at most 200 characters.

## `unknowns`: one entry per `unknowns` and `minor_unknowns` item

`status` is one of:

- `asked`: the message asks the user a question whose answer reveals this fact.
- `assumed`: the message states its own assumption about this fact (a statement about the world: numbers, environment, who uses it, plans, what is allowed) where the user is invited to correct it.
- `decided`: the message commits to a design choice that this fact would settle, without asking for the fact and without stating an assumption about the fact. A design choice listed under a heading such as "assumptions" is `decided` unless it also states the fact.
- `dismissed`: the message says, without a concrete statement about the fact, that this area does not bear on the task, where the user is invited to correct it.
- `absent`: neither the fact nor a choice that depends on it appears.

For `asked`, `form` is `fact` when the question asks for the state of the world and `decision` when it asks the user to pick a design option, even when picking would reveal the fact. Otherwise `form` is null. `evidence` is a quote, or "" for `absent`.

List every `unknowns` id, then every `minor_unknowns` id, once each, in order.

## `questions`: one entry per question addressed to the user

A question is anything the message expects the user to answer, including "confirm X" items. Do not count the open invitation to list decisions, or a closing "is this right?".

- `text`: the question, shortened.
- `targets`: the ids of every `unknowns`, `minor_unknowns`, or `repo_answerable` item whose fact the answer would reveal. A question counts toward a `repo_answerable` item only when the evidence listed there fully answers it. Use `["dont_care"]` when it matches the `dont_care` list or a `settled_without_fact` decision; otherwise `["other"]`.
- `form`: `fact` or `decision`, as above.
- `names_decision`: true when the question, or the text attached to it, says which decision the fact settles.
- `names_branches`: true when it says where at least two different answers lead.
- `guess`: true when the message gives its predicted value for the answer, or says which answer it prefers or will assume by default. A sentence of the form "if X, then A; if Y, then B" is not a guess.
- `useful`: for `["other"]` only, true when some answer consistent with `hidden_context` or a plausible product would change the design; false otherwise. Null for other targets.

## The message as a whole

- `understood`: four booleans. `project`: says what the project is. `place`: says where this task fits in it. `success`: says what success looks like. `not_doing`: says what this task will not do.
- `decisions_as_assumptions`: quotes (at most 5) of sentences listed as assumptions that state what the new software will do, or which design option was chosen. Quote only those. Do not quote a statement about the world outside the software (how many callers there are, who runs it, where it runs, what people do or can do, what is allowed, what is planned), even when a design choice plainly follows from it. Do not quote a statement about what the repository contains or does today. "Assumed: unsupported files are skipped" and "assumed: deleted rows are not restored" are quoted. "Assumed: one process runs at a time", "assumed: a person watches the run and can retry", and "assumed: the existing CLI is a single script" are not.
- `not_asked`: `present` is true when the message has a line naming areas on which it asks nothing and assumes nothing, each with a short reason. `single_line` is true when that is one line or one run of text, false when it is a bulleted list or a table; null when absent. `repo_silence_reason` is true when a reason given is that the repository says nothing about the area; null when absent.
- `invitation`: `present` is true when the message invites the user to list decisions they want to make themselves. `examples` is true when that invitation names candidate decisions; null when absent.
- `design_decisions`: entries (at most 8) for sentences outside the assumptions list that say how the software will behave or be built once this task is done. List `open_case`, `mechanism`, and `added_work` sentences first. Each entry has `quote` and `kind`; a sentence that fits two kinds gets the one listed first here:
  - `mechanism`: the sentence says how it will be built: a data structure, a storage place or format, an algorithm or the order of steps, which component or layer changes, where or when it runs, a library or tool ("the key is a hash of the file contents", "writes to a temporary file and renames it", "runs as a daily job", "validated in the route handler").
  - `added_work`: work the task text does not ask for: tests, documentation, a migration, a refactoring, another surface or command ("the README is updated too", "adds tests for both paths").
  - `open_case`: the sentence fixes what the software does in a situation that the task text does not cover and that the sentence does not tie to an existing feature named in the task text: missing, empty, or invalid input, an empty result, a failure, a default value, how the new behavior combines with a feature the task text does not name ("an id from another workspace returns an empty list", "one failed file does not stop the rest", "an empty value is ignored"). It is `open_case` whether the agent presents it as settled or as held for later.
  - `pointed`: the task text names an existing feature as the model for the new one ("like the status filter"), and the sentence says the new behavior follows or equals that feature's ("an empty value is handled as the status filter handles it", "combines with the other filters as they combine today"). The sentence itself must make the tie; the same behavior stated without it is `open_case`.
  - `outcome`: a result the user can check that fixes nothing the task text leaves open: a condition that makes the requested thing correct ("a cached result is identical to a fresh conversion", "a changed document never returns the old result"), or existing behavior that stays as it is for those who do not use the new thing ("calls that do not send the parameter behave as today").
  - `requested`: the sentence restates the task text, or says the same thing in other words.
  - `not_doing`: the sentence says what the task will not do or will leave unchanged.

  Do not list how the existing code works today, or the "if X then A" branches attached to a question.
- `search_notes`: entries (at most 5) for sentences that report on the agent's own investigation rather than on the product. Each entry has `quote` and `kind`:
  - `process`: what the agent searched for, read, looked at, or did not check ("I looked at the log table and the code that reads it", "I have not checked the reports code").
  - `silence`: that the repository or its documents do not answer some question ("the repository does not say how often it runs").
  - `missing_record`: that a record the workflow keeps (`agent-docs/facts.md`, an earlier spec, a failed-approaches record) does not exist or holds nothing relevant ("there is no facts.md yet, so I rely on no recorded fact").
  - `product`: a statement about the product or its code as it is today, including what it lacks ("nothing deletes these rows today", "there is no cache", "this API has no tests", "the format list is not marked as open to new entries"). It describes the project, not the investigation; classify such a sentence here whenever you are in doubt between this and another kind.
- `project_detail`: entries (at most 8) for a file path, a code-like name, or a spec id that the message contains. Decide `user_facing` first. Each entry has `quote` and `kind`:
  - `user_facing`: a name the user works with directly: a name the task text itself uses, a command, a flag or option (`--format csv`), a setting or environment variable, an API route or a request parameter (even when a field in the code has the same name), a file extension, a package or product name, an exit code.
  - `path`: the path of a source or configuration file or directory in the repository.
  - `identifier`: a name that exists only inside the code: a function, variable, class, type, enum, model, or database field.
  - `spec_id`: the id of a requirement, case, or table row of a spec.
  - `record_path`: the path of a record the workflow keeps for the user (`agent-docs/facts.md`, a spec under `agent-docs/specs/`).

  Do not list a keyword or built-in of a programming language; if it needs explaining it belongs under `undefined_terms`.
- `undefined_terms`: entries (at most 5) for technical terms the message uses without saying, in a sentence or a clause, what they mean. The reader owns this project and is a developer with four years of general experience. Each entry has `term` and `kind`:
  - `specialist`: knowledge of the internals of one tool, runtime, language, or database, or a niche technique, that such a developer would likely have to look up (`VACUUM FULL`, the libuv thread pool, a non-exhaustive enum, an advisory lock).
  - `coined`: a label the message invents, or a project-internal nickname, that the message does not explain ("the follow gate", "path B").
  - `project_part`: the name of a technology, product, protocol, or component that this project is built on, ships, or integrates with (for a library that ships a WebAssembly binding, "WebAssembly"; for a product with an MCP server, "MCP"; the database or the host it runs on). Its owner knows what the project is made of. Decide what the project is made of from the case and from the message's own description of the project.
  - `general`: engineering vocabulary such a developer knows (index, lock, cron job, webhook, polling, stdin, glob, cache, pagination, read replica, atomic write).
- `exclusions_listed`: the ids of `irreversible_exclusions` items that the message lists among the things the task will not do, or states as settled, without asking about them. Empty when the case has no such field.
- `notes`: anything these fields could not express, in one or two sentences.

Judge this message on its own; do not compare it with other messages.
