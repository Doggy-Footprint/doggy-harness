---
commit: dcd1808afd6796da3ced28f5f0926d1bb05e72b3
---

# Share the main checkout's node_modules with local worktrees

## Goal
A local worktree of an npm project gets its verification tools without a second full copy of `node_modules` on disk.

## Observation
- The project owner asked on 2026-11-20 whether a local worktree can use the original checkout's mutation tool, and raised disk use when worktrees are kept. The owner chose to handle it as a task separate from spec `agent-docs/spec-logs/37f43a7fb2bc2bcf-checkout-setup-at-session-start.md`, which installs per checkout.
- Measured on 2026-11-20 in a scratch clone of the harness target that uses uv: `uv sync --frozen --inexact --offline` took 2 s and about 19 MB of real disk (`df` before and after) for an environment `du` reports as 1.2 GB. Re-check: clone it, run the command, compare `df -k` before and after.
- That target's environment holds an editable install: the `_editable_impl_<package>.pth` file under `.venv/lib/python*/site-packages/` contains the checkout's own `src` path. An environment symlinked from another checkout would import that other checkout's `src`.
- The harness target that uses npm had an 811 MB `node_modules` on 2026-11-20 (`du -sh node_modules`), no `workspaces` key in `package.json`, and a `node_modules/.vite` cache directory. `npm ci` copies files into `node_modules` and deletes the directory first.
- Measured on 2026-11-20 in a scratch clone of that target: `npm ci`, started by the session-start hook, took 30 s and produced an 824 MB `node_modules`. Re-check: clone it, run `npm ci`, time it, `du -sh node_modules`.
- Not checked: whether Stryker and vitest run correctly when `node_modules` is a symlink to another checkout's directory.
- On 2026-11-20 the owner's worktrees of harness targets lived in directories outside the repositories (`git worktree list` in two targets).

## Conditions named in the discussion of 2026-11-20 (the owner has not decided)
- Link only while the worktree's lockfile bytes equal the main checkout's, and only when the project has no workspaces.
- When the lockfiles diverge, replace the link with a real install.
- A shared tree means a dependency change made in one checkout appears in the other, and caches kept inside `node_modules` are shared.

## Next Step
- Run Stryker and vitest in a scratch worktree of the npm target whose `node_modules` is a symlink to the main checkout's, and record whether both pass and where they write caches. Then ask the owner whether to build the link with the conditions above.

## Related
- agent-docs/spec-logs/37f43a7fb2bc2bcf-checkout-setup-at-session-start.md, installer/verification_tools.py
