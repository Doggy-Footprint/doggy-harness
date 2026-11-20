---
name: project-map
description: Explain how an existing project, or one area of it, is built today, and the core engineering decisions and trade-offs behind that shape, as an HTML page with a structure diagram, followed by a short quiz in chat. Use whenever the user wants to understand, re-learn, or take ownership of code that an AI agent or someone else mostly wrote — "how does this fit together", "walk me through the architecture", "why is it built this way", "I can't explain this codebase anymore", onboarding onto a repo, paying back understanding debt — even if they do not ask for a map or a page. Not for designing a new feature or change (use doggy-workflow), reviewing a diff, or auditing code quality.
---

# Project map

Code an agent wrote can work while its owner can no longer explain it. That gap is understanding debt: the owner approves changes they cannot predict, and the first incident is where they meet the design. This skill pays it back for the code as it stands today. It gives the owner a working model: the parts, how they connect, where state lives, and the decisions that made the structure this shape. Each decision comes with what it costs and the state of the world in which it would be wrong. A quiz at the end makes the owner use that model, because reading a clear page leaves a feeling of understanding that is easy to mistake for the real thing.

The skill explains; it does not change code, judge code quality, or propose refactors. When the explanation surfaces a gap between what the code does and what the user wants, offer a follow-up task instead.

## Reader

An engineer who owns the project and will answer for it, but has not read this code. Write for a developer with about 4 years of experience and explain anything beyond that in a sentence. Use full sentences and define project terms at first use. Never use a label (an id, an abbreviation, a table key) that the page itself does not resolve.

Describe behavior, structure, data and control flow, and consequences. Give each part on the map one path as an anchor, so the reader can find it later. Leave out function and variable names unless the reader must act on that name (a command, a flag, a setting). The aim is a reader who could explain the project and defend its shape without the page in front of them. A page that lists every module reads as complete and teaches nothing.

## Scope

- No area named: the whole project, at the level of its top parts. A large repository gets a top-level map plus a short list of areas worth a page of their own.
- An area named (a directory, a feature, a flow such as "what happens on login"): that area. Show its neighbors only as far as they explain the area's boundaries.
- A follow-up "go deeper into X" gets its own page under a new file name, which links back to the earlier page.

## Gather

Read the code that decides the structure yourself. A subagent may locate files, but a summary of a summary loses the reasons. Work from the outside in:

1. The project's own definition: `AGENTS.md` / `CLAUDE.md`, the README, and `agent-docs/facts.md` when it exists. facts.md holds what the repository cannot show (environment, intent, plans), and it often settles whether a decision still fits.
2. Shape: `git ls-files`, the manifests (package files, build files, CI workflows), and the entry points (CLI mains, servers, hooks, scheduled jobs). Who or what starts each one?
3. The main paths: follow one or two real flows through the code from trigger to effect, then the failure path of each.
4. State and boundaries: what is persisted, in what format, and who writes and reads it. Note every external system, and every interface others depend on (CLI flags, file formats, APIs).
5. History, for the reasons behind choices: commit messages (in harness projects, their `Request:` and `Intent:` lines), archived specs under `agent-docs/spec-logs/` (their `# Alternatives` and `# Assumptions and Defaults` sections), ADRs, and design notes. `git log --stat` also shows where change concentrates. A recorded reason is a claim about the code at the time it was written. Where the code has changed since (an `agent-docs/` record's `commit:` stamp against HEAD), re-check the reason against the current code before using it. The code is the ground truth.

Do not open `agent-docs/try-n-fail/` for the map: the project reads it only by search, at specific moments. When the user asks why an alternative was not taken, search its `index.md` for that alternative's nouns and open only the matching records.

## Find the core decisions

A core decision is a choice that shaped the structure and that a reasonable engineer could have made differently. Keep 4 to 8. Pick by these criteria, at least one of which must hold:

- *hard to reverse*: persisted data and formats, interfaces others depend on, external side effects, security boundaries, money;
- *load-bearing*: other code or later decisions build on it (data model, module boundary, state ownership, concurrency model, a dependency, failure policy);
- *different outcomes*: the options differ in what users see, cost, behavior under load, or how things fail;
- *answerable for*: the owner would have to explain it in a design review or after an incident.

Conventions followed, libraries reused, and naming do not qualify; leave them out.

For each decision, work out:

- **Chosen**: what the code does, in one sentence.
- **Alternative**: the option a reasonable engineer could have picked instead.
- **Buys / costs**: what the choice gains, and what it gives up or rules out.
- **Wrong when**: the reversal condition, the state of the world in which the alternative wins. Phrase it as a fact about the world, for example "a second process writes the same file" or "exports exceed the 30 s request timeout".
- **Evidence**: *recorded*, where a spec, commit, ADR, or doc states the reason (cite it), or *inferred*, where only the code shows the choice (cite `path:line` and say the reason is your inference). Never present an inferred reason as recorded. When nothing explains a choice, say that the reason was not recorded.
- **Condition today**: whether the reversal condition holds, does not hold (cite the code or facts.md), or is unknown. An unknown condition is a question only the user can answer. Collect these questions for the user.

One decision is the **core trade-off**: the one that most shapes the whole. The page leads with it.

## The page

Write one self-contained HTML file outside the repository, in the session scratchpad when there is one and the system temporary directory otherwise. Name it `<repo>-<scope>-map.html`. When the Artifact tool is available, publish the file as a private artifact, following that tool's own page rules (it asks you to load its design skill first). Otherwise, give the file's absolute path so the user can open it in a browser. Write nothing into the repository.

The page has these sections, in this order:

1. **What this is**: two or three sentences on what the project or area does, who or what uses it, and how it runs. Then the core trade-off in one sentence.
2. **Map**: a diagram (inline SVG), not a list. Parts are boxes, each with a one-line responsibility and its anchor path. Connections are labeled arrows, marked as data or control. External systems and stored state sit at the edges. Aim for 5 to 12 boxes; group smaller pieces. If the diagram needs a legend to be read, simplify it.
3. **Main paths**: one to three walkthroughs, each a numbered sequence from trigger to observable effect. For each, add what happens when the most likely step fails.
4. **State**: each kind of persisted state, its format, who writes it, and who reads it. Mark any format that something outside the code depends on.
5. **Core decisions**: one card per decision with the fields above, the core trade-off first. Show *recorded* or *inferred* visibly on each card.
6. **Questions for you**: the unknown reversal conditions. For each, state the fact that would settle it, and what would need to change if the answer goes the other way.
7. **Terms**: the project's own vocabulary, one line each.
8. Footer: the scope, the commit the map was made from (short hash), the date, and one line saying the code is the ground truth and the page goes stale as the code changes.

Keep it readable in about ten minutes. Put the quiz in chat, not on the page.

## Chat message and quiz

Before sending, write the expected answer to each quiz question in a file outside the repository, next to the page, named `<repo>-<scope>-quiz.md`. An expectation written after reading the user's answer bends toward that answer.

Then send:

- the page link or path, and three to five sentences: the core trade-off and the one or two decisions most likely to matter next;
- the **Questions for you** from the page, at most three, the most consequential first;
- a **Quiz** of 2 to 4 questions, with no options, hints, or answers. Each question asks the user to predict or apply, not to recall:
  - the core trade-off: what the project gives up, and where a user or operator would notice it;
  - a core decision: change the fact behind it ("a second machine now writes the same telemetry") and ask what breaks or which choice would flip;
  - the structure: how two parts connect, or what happens on a main path.
  
  Ask at the level of the page: the answer must follow by reasoning from what the page explains, never from a constant, a name, or a rule only the code holds. At most one question may be about a failure path. Tell the user they may skip the quiz.

When the answers arrive, compare each with the expected answer and say in one line each whether it matched. For an answer that differs, find out which of these it is:

- **A misunderstanding**: explain that part again, starting from the user's answer, in different words than the page used. When the page itself misled, fix it and republish to the same path.
- **A fact the repository does not show** (a plan, the load, the environment): propose an `agent-docs/facts.md` entry. Show the exact bullet in the project's format, `- <sentence> — source: user, <YYYY-MM-DD>; re-check: <how>`. Ask about it on its own, naming facts.md, apart from the quiz. Write it only after the user approves that exact text.
- **The user expected the code to behave differently**: this is a gap between intent and code, not a quiz miss. Describe the gap with a citation, and offer to start a task for it (doggy-workflow in a harness project). Do not change the code in this skill.
- **Your expected answer misread the code**: say so, correct the page, and republish it.

Quiz answers are written nowhere. The quiz file holds only your expected answers, and no later session reads it.
