**Running a step.** Before each step after the first, give the user a short step brief in the terms of Voice: what this step adds to what already exists, and its held decisions. Search try-n-fail for the step's approach.

- Mark the step `active`, then run Workflow items 3 to 8 for its requirements and obligations only; dispatch instructions name the step and its ids.
- `max_verifier_invocations` bounds each step separately: count invocations in the step's `verifier invocations` cell and the run total in Workflow Control, and use the run total for telemetry `--round`. A step that exhausts its verifier budget ends the run with status `limit`.
- Obligations of earlier steps stay accepted in the audit state; reopen them only through the change-impact rule of the Verification model.
- When the stop condition holds for the step, mark it `done` with the date and go on to the next step, unless the user asks to stop or the session cannot continue (an outside wait, or too little context left to finish another step).
