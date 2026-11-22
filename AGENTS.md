# Project Definition

This harness, installed into a git repository, makes Claude Code agree on the work with the user before building it with workflow to follow
Before a feature or fix, the agent and the user agree on a written spec: what to build, which choices are the user's, and how it will be checked.
Separate agents then write the code and the tests without seeing each other's work, and another agent checks the tests against the spec.
Across sessions, the agent keeps only what the user approved: facts about the project, failed attempts, and the spec of unfinished work.
Hooks and git checks block a few rule breaks in code; the rest are rules the agent is told to follow.

<!-- harness:begin -->
@.harness/instructions/harness-block.md
<!-- harness:end -->
