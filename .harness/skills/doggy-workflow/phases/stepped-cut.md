# Stepped specs

A task that one session cannot finish runs as one spec cut into steps, each of which passes the whole verification structure on its own. Recommend the cut when at least one holds:

- *size*: after drafting, `# Verification Obligations` has 15 rows or more (the number is `step_split_obligations` in `.harness/config.json` when that key is set);
- *order dependence*: an open question can be settled only by building or running an earlier part;
- *outside wait*: the work has to wait for something outside the session, such as a deployment, an action by the user, or a long measurement;
- *too many decisions*: the decision round counted more than 3 *Your decision* items and the user wants the work kept in one spec;
- *a stopped session*: a session of a spec without steps ended with a nonterminal stop.

The first three are recommended in the approval brief. *Too many decisions* is proposed in outline in the decision round (which decisions can wait for which part) and fixed in the approval brief. *A stopped session* is proposed by the next session, before it continues, as an amendment with a re-brief; verifier invocations already used count against the first remaining step. The cut is a brief item: the user approves it, and changing it later is an amendment with a re-brief.

**Cutting.** Each step delivers an outcome the user can observe and owns its requirement and obligation ids; every id belongs to exactly one step, and an obligation that spans steps belongs to the last step that completes it. After each step the Test command passes and no behavior is left half-switched, so the work can be committed or stopped at any step boundary. Order steps by dependency, and put a step that settles an open question before the steps that depend on the answer.
