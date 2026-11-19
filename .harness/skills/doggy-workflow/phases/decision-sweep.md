## Decision sweep

Run the sweep before each round. It sorts decisions by what would settle them. The user holds facts the repository does not (load, environment, plans), and a decision made without them is a guess presented as a default.

**Context pass.** Before listing decisions, go through the dimensions once for the task as a whole: `load` (volume, peak, growth), `data` (size, shape, sensitivity), `concurrency` (parallel callers, processes, instances), `environment` (where and how it runs or is deployed, and who or what starts it), `consumers` (who calls or reads this and what they already depend on), `roadmap` (planned work this must not block), `failure` (what a failure costs and what loss is tolerable), `cost` (money, quota, latency budget). For each, note what a citation says about it for this task, or that it is unknown. Judge each dimension by everything the change sets off, not only by the code it edits: follow the records it creates or changes to the events they emit, the jobs those queue, the metered calls those jobs make, and the people or automations that react, until the chain ends or reaches something the repository cannot show (a configured automation, a plan's quota). New data reaching old machinery is where `consumers` and `cost` are most often decided. The chain also ends at an addition that existing callers never see unless they opt in (a new filter option, an optional field, an extra enum value nobody else matches on): it sets off nothing for them, so it raises no question about them. For an unknown dimension, picture the task at both ends of it (ten items or ten million; a laptop or a memory-limited container; a person at a terminal or a scheduled pipeline; one caller or a second one already planned) and add every decision that comes out differently at the two ends. Decisions nobody lists hide in the dimensions nobody looked at.

**Per decision.** For every decision the spec depends on, including those the context pass added:

1. Write the decision as a question, your leading option, one alternative a reasonable engineer could pick, and the **reversal condition**: the state of the world in which the alternative wins.
2. Place the reversal condition in the dimension it belongs to.
3. Settle the reversal condition with a citation: a repository `path:line`, an entry of `agent-docs/facts.md`, or a statement by the user. A condition you cannot cite is unknown. Do not settle it from what is typical for such projects.
4. Classify:
   - No reasonable alternative, an existing project convention, or no observable difference between the options → *Decided for you*.
   - Settled by a citation → *Decided for you*, with the citation.
   - Unknown, and a fact would settle it → *Fact question* when the decision is significant, a stated assumption otherwise.
   - No fact would settle it, because the options trade one quality for another → *Your decision* when it is significant, *Decided for you* otherwise.

A decision is **significant** when at least one holds:
- *hard to reverse*: persisted data, schemas or formats; interfaces others depend on (CLI flags, API fields, file formats); external side effects (sending, deleting, publishing); security boundaries; money;
- *load-bearing*: other code or later decisions build on it, such as a data model, module boundary, state ownership, concurrency or consistency model, new dependency, or failure policy;
- *different outcomes*: the options differ in what users see, operating cost, behavior at the expected load, or how it fails;
- *answerable for*: the user would have to explain the choice in a design review or after an incident.

An **engineer call** is a significant decision, whoever made it: every *Your decision*, and every *Decided for you* that meets a criterion above. Engineer calls are what the approval brief explains and the quiz asks about; the remaining *Decided for you* items stay in the spec.

Example, for the task "add CSV export of orders":
- "Run the export inside the request or as a background job?" Leading: inside the request. Alternative: background job. Reversal condition: an export can outlast the request timeout (`data`). The repository gives the timeout (`server/config.ts:12`, 30 s) but not how many orders one customer has, so the condition is unknown, and the choice is load-bearing → *Fact question*: "How many orders does the largest customer export at once? Up to tens of thousands it runs inside the request; beyond that it needs a background job and a way to deliver the file."
- "Which CSV library?" The project already uses one (`package.json:18`) → *Decided for you*, cited, and not an engineer call.
- "Timestamps in UTC or in the customer's time zone?" No fact settles it, users see the difference, and files already parsed by customers are hard to change → *Your decision*.
