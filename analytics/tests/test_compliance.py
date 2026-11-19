import unittest

from analytics.compliance import evaluate


def event(name, **fields):
    return {"event": name, "workflow_run_id": "run-1", "spec": "analytics", "spec_version": 1, **fields}


def passing_events(status="complete"):
    return [
        event("workflow_start"),
        event("workflow_phase", phase="implement_test"),
        event("workflow_phase", phase="verify"),
        event("verifier_result", round=1, result="pass", findings=0, seeds_run=2, seeds_detected=2),
        event("workflow_end", status=status),
    ]


class ComplianceTests(unittest.TestCase):
    """Independent oracle for spec v2 V2/Q1 (current spec telemetry only)."""

    def test_v2_completed_passing_run_is_compliant(self):
        self.assertEqual(evaluate(passing_events()), {"completed": True, "compliant": True, "reasons": []})

    def test_v2_unterminated_run_is_in_progress_and_unclassified(self):
        result = evaluate(passing_events()[:-1])
        self.assertFalse(result["completed"])
        self.assertIsNone(result["compliant"])

    def test_v2_correction_cycle_can_finish_after_a_retry(self):
        events = passing_events()[:3] + [
            event("verifier_result", round=1, result="retry", findings=1, seeds_run=1, seeds_detected=0),
            event("workflow_phase", phase="amend"),
            event("workflow_phase", phase="verify"),
            event("verifier_result", round=2, result="pass", findings=0, seeds_run=1, seeds_detected=1),
            event("workflow_end", status="complete"),
        ]
        self.assertEqual(evaluate(events), {"completed": True, "compliant": True, "reasons": []})

    def test_v2_complete_requires_a_latest_pass_result(self):
        for result in ("retry", "limit"):
            with self.subTest(latest_result=result):
                events = passing_events()
                events[-2] = {**events[-2], "result": result}
                outcome = evaluate(events)
                self.assertTrue(outcome["completed"])
                self.assertFalse(outcome["compliant"])
                self.assertTrue(outcome["reasons"])

    def test_v2_limit_requires_a_latest_limit_result(self):
        valid = passing_events("limit")
        valid[-2] = {**valid[-2], "result": "limit"}
        self.assertEqual(evaluate(valid), {"completed": True, "compliant": True, "reasons": []})
        for result in ("pass", "retry"):
            with self.subTest(latest_result=result):
                invalid = [*valid]
                invalid[-2] = {**invalid[-2], "result": result}
                outcome = evaluate(invalid)
                self.assertTrue(outcome["completed"])
                self.assertFalse(outcome["compliant"])
                self.assertTrue(outcome["reasons"])

    def test_v2_handoff_and_abort_can_end_without_verifier_at_each_workflow_point(self):
        points = {
            "start": [event("workflow_start")],
            "implement": [event("workflow_start"), event("workflow_phase", phase="implement_test")],
            "verify": [event("workflow_start"), event("workflow_phase", phase="implement_test"), event("workflow_phase", phase="verify")],
            "amend": [event("workflow_start"), event("workflow_phase", phase="implement_test"), event("workflow_phase", phase="verify"), event("verifier_result", round=1, result="retry", findings=1), event("workflow_phase", phase="amend")],
        }
        for status in ("handoff", "aborted"):
            for point, prefix in points.items():
                with self.subTest(status=status, point=point):
                    outcome = evaluate([*prefix, event("workflow_end", status=status)])
                    self.assertEqual(outcome, {"completed": True, "compliant": True, "reasons": []})

    def test_v2_completed_invalid_transition_variants_are_noncompliant(self):
        valid = passing_events()
        variants = {
            "missing_verifier": valid[:3] + valid[4:],
            "duplicate_phase": valid[:2] + [valid[1]] + valid[2:],
            "verify_before_implement": [valid[0], valid[2], valid[1], *valid[3:]],
            "mismatched_identity": [*valid[:2], {**valid[2], "workflow_run_id": "other"}, *valid[3:]],
            "post_end": [*valid, event("workflow_phase", phase="amend")],
            "orphan_result": [valid[0], valid[1], valid[3], valid[4]],
        }
        for name, events in variants.items():
            with self.subTest(variant=name):
                first = evaluate(events)
                self.assertTrue(first["completed"])
                self.assertFalse(first["compliant"])
                self.assertTrue(first["reasons"])
                self.assertEqual(first, evaluate(events))

    def test_v2_two_start_events_violate_one_start_first(self):
        """F3 'one start first': a second workflow_start is a noncompliant duplicate start."""
        valid = passing_events()
        events = [valid[0], valid[0], *valid[1:]]
        outcome = evaluate(events)
        self.assertTrue(outcome["completed"])
        self.assertFalse(outcome["compliant"])
        self.assertIn("expected_one_start", outcome["reasons"])
        self.assertEqual(outcome, evaluate(events))

    def test_v2_stream_not_starting_with_workflow_start_violates_one_start_first(self):
        """F3 'one start first': the first event of the stream must be workflow_start."""
        valid = passing_events()
        events = valid[1:]
        outcome = evaluate(events)
        self.assertTrue(outcome["completed"])
        self.assertFalse(outcome["compliant"])
        self.assertIn("expected_one_start", outcome["reasons"])
        self.assertEqual(outcome, evaluate(events))

    def test_flows_the_workflow_prescribes_are_compliant(self):
        start, implement, verify, amend = (
            event("workflow_start"), event("workflow_phase", phase="implement_test"),
            event("workflow_phase", phase="verify"), event("workflow_phase", phase="amend"))
        passed = event("verifier_result", round=1, result="pass", findings=0)
        retry = event("verifier_result", round=1, result="retry", findings=1)
        handoff, complete = event("workflow_end", status="handoff"), event("workflow_end", status="complete")
        flows = {
            "both roles dispatched again after an amendment": [start, implement, amend, implement, verify, passed, complete],
            "next step of a stepped spec after a pass": [start, implement, verify, passed, implement, verify, passed, complete],
            "resumed after a handoff": [start, implement, verify, retry, amend, handoff, start, amend, verify, passed, complete],
            "resumed and dispatched again without an amendment": [start, implement, handoff, start, implement, verify, passed, complete],
            "audit pending at the handoff is abandoned": [start, implement, verify, handoff, start, verify, passed, complete],
            "resumed twice across steps": [start, implement, verify, passed, handoff, start, implement, verify, passed,
                                           handoff, start, implement, verify, passed, complete],
            "resumed and stopped again": [start, implement, handoff, start, amend, handoff],
        }
        for name, events in flows.items():
            with self.subTest(flow=name):
                self.assertEqual(evaluate(events), {"completed": True, "compliant": True, "reasons": []})

    def test_repeats_and_restarts_outside_those_flows_stay_noncompliant(self):
        start, implement, verify, amend = (
            event("workflow_start"), event("workflow_phase", phase="implement_test"),
            event("workflow_phase", phase="verify"), event("workflow_phase", phase="amend"))
        passed = event("verifier_result", round=1, result="pass", findings=0)
        limit = event("verifier_result", round=2, result="limit", findings=1)
        handoff, complete = event("workflow_end", status="handoff"), event("workflow_end", status="complete")
        cases = {
            "implement_test twice in a row": ([start, implement, implement, verify, passed, complete],
                                              "duplicate_implement_test"),
            "implement_test again after a retry without an amendment": (
                [start, implement, verify, event("verifier_result", round=1, result="retry", findings=1), implement,
                 verify, passed, complete], "duplicate_implement_test"),
            "one amendment covers one dispatch": ([start, implement, amend, implement, implement, verify, passed, complete],
                                                 "duplicate_implement_test"),
            "start after a completed run": ([start, implement, verify, passed, complete, start, amend], "post_end_event"),
            "start after the verifier limit": (
                [start, implement, verify, limit, event("workflow_end", status="limit"), start, amend, verify, passed,
                 complete], "post_end_event"),
            "start after an abort": ([start, event("workflow_end", status="aborted"), start, implement], "post_end_event"),
            "phase after a handoff without a new start": ([start, implement, handoff, amend], "post_end_event"),
            "second start without a handoff": ([start, implement, start, verify, passed, complete], "expected_one_start"),
        }
        for name, (events, reason) in cases.items():
            with self.subTest(case=name):
                outcome = evaluate(events)
                self.assertTrue(outcome["completed"])
                self.assertFalse(outcome["compliant"])
                self.assertIn(reason, outcome["reasons"])


if __name__ == "__main__":
    unittest.main()
