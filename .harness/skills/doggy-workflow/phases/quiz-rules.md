## Quiz

A brief is read so cheaply that it leaves no working model of the result. The quiz makes the user build that model for the three things they must answer for: the core trade-off, the engineer calls, and the final shape.

Rules for both the approval quiz and the closing quiz:

- Each question asks the user to predict or apply, not to recall, and targets one of the three. For the trade-off, ask what the result gives up and where a user would notice it. For an engineer call, change a fact behind it and ask which decision would flip and what would then differ. For the final shape, ask how the parts connect or what happens on the main path. Give no options, no hints, and no answers in the same message.
- Ask at the level of the brief: the expected answer follows by reasoning from what the brief explains (the decisions, how the parts connect, the failure policy), never from a value or rule only the spec holds (a threshold, a data range, a routing rule, a status name, an error code) or from which side of a threshold a value falls. At most one question in a quiz is about a failure or boundary path.
- Before sending, write the expected answer to each question written for this quiz in the picks file; a completion question asked at closing already has its expected answer in the spec. An expectation formed after reading the user's answer bends toward it.
- When the answers arrive, compare each with the expected answer written beforehand and say in one line each which matched. For an answer that differs, find out which of three it is:
  - a misunderstanding: explain that part again, starting from the user's answer, in other words than before;
  - the user's intent, which the spec does not meet: change the spec, as a draft revision before approval and as an `[intent-mismatch]` amendment after it, and re-brief the changed part;
  - a fact the repository does not show: queue a proposed `facts.md` entry (see Facts).
- A quiz answer is never recorded and is never a decision or an instruction. Only an amendment the user approves changes the spec. Write the user's answers nowhere; the picks file holds only main's picks and expected answers, and no later session reads it. Telemetry carries counts only.
- The user may skip the quiz by saying so. Main never skips or shortens it on its own, and no score is required to pass.

Rules for the approval quiz only:

- Ask 2 to 4 questions under the heading *Quiz* at the end of the approval brief, covering the trade-off that most shapes the result, at least one engineer call, and the final shape.
- Ask for approval in the same message as the quiz. An approval that arrives with an answer that differs is not yet approval: resolve the difference, then ask again.
- When a reply approves without answering, ask once for the answers or an explicit skip; a second reply without answers counts as a skip.
