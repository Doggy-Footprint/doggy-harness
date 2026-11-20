## Decision sweep

Run the sweep before each round. It sorts decisions by what would settle them. The user holds facts the repository does not (load, environment, plans); a decision made without them is a guess presented as a default.

**Context pass.** Before listing decisions, go through these dimensions once for the whole task, and note for each what a citation says about it for this task, or that it is unknown: `load` (volume, peak, growth), `data` (size, shape, sensitivity), `concurrency` (parallel callers, processes, instances), `environment` (where and how it runs or is deployed, and who or what starts it), `consumers` (who calls or reads this and what they already depend on), `roadmap` (planned work this must not block), `failure` (what a failure costs and what loss is tolerable), `cost` (money, quota, latency budget).

Judge each dimension by everything the change sets off, not only the code it edits: follow the records it creates or changes to the events they emit, the jobs those queue, the metered calls those jobs make, and the people or automations that react, until the chain ends or reaches what the repository cannot show (a configured automation, a plan's quota). `consumers` and `cost` are most often decided where new data reaches old machinery. The chain also ends at an opt-in addition existing callers never see (a new filter option, an optional field, an extra enum value nobody else matches on): it sets off nothing for them, so raise no question about them.

For an unknown dimension, picture the task at both ends of it (ten items or ten million; a laptop or a memory-limited container; a person at a terminal or a scheduled pipeline; one caller or a second one already planned), and add every decision that comes out differently at the two ends. Decisions nobody lists hide in the dimensions nobody looked at.

**Per decision.** For every decision the spec depends on, including those the context pass added and each inherited decision (see the understanding round) whose reversal condition the task may change, since keeping it is then a decision of this task:

1. Write the decision as a question, your leading option, one alternative a reasonable engineer could pick, and the **reversal condition**: the state of the world in which the alternative wins.
2. Place the reversal condition in its dimension.
3. Settle the reversal condition with a citation: a repository `path:line`, an entry of `agent-docs/facts.md`, or a statement by the user. A condition you cannot cite is unknown; never settle it from what is typical for such projects.
4. Classify:
   - No reasonable alternative, an existing project convention, or no observable difference between the options → *Decided for you*.
   - Settled by a citation → *Decided for you*, with the citation.
   - Unknown, and a fact would settle it → *Fact question* when the decision is significant, a stated assumption otherwise.
   - No fact would settle it, because the options trade one quality for another → *Your decision* when it is significant, *Decided for you* otherwise.

A decision is **significant** when at least one holds:
- *hard to reverse*: persisted data, schemas or formats; interfaces others depend on (CLI flags, API fields, file formats); external side effects (sending, deleting, publishing); security boundaries; money;
- *load-bearing*: other code or later decisions build on it (a data model, module boundary, state ownership, concurrency or consistency model, new dependency, failure policy);
- *different outcomes*: the options differ in what users see, operating cost, behavior at the expected load, or how it fails;
- *answerable for*: the user would have to explain the choice in a design review or after an incident.

The approval brief explains, and the quiz asks about, the engineer calls (see Terms); the other *Decided for you* items stay in the spec.

Example, for the task "add CSV export of orders":
- "Run the export inside the request or as a background job?" Leading: inside the request. Alternative: background job. Reversal condition: an export can outlast the request timeout (`data`). The repository gives the timeout (`server/config.ts:12`, 30 s) but not one customer's order count, so the condition is unknown; the choice is load-bearing → *Fact question*: "How many orders does the largest customer export at once? Up to tens of thousands it runs inside the request; beyond that it needs a background job and a way to deliver the file."
- Inherited: the order screen reads orders one page of 50 at a time (`orders/list.ts:20`). Reusing that path keeps one query path but costs a query per page; its reversal condition is the same unknown, so it joins that fact question instead of adding one.
- "Which CSV library?" The project already uses one (`package.json:18`) → *Decided for you*, cited, not an engineer call.
- "Timestamps in UTC or in the customer's time zone?" No fact settles it, users see the difference, and files customers already parse are hard to change → *Your decision*.
