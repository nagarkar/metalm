import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apps import department_router, pager, route, spam_filter  # noqa: E402 (after the sys.path line)
from jevkit import QuestionSet, decide  # noqa: E402

QUESTION_SET = QuestionSet.load(ROOT / "questions/ticket_triage_v1.json")


def response_body(noul, choice, choice_probabilities, urgency_probabilities):
    """Response in the documented /v1/systemone shape. Confidence recomputed with the documented formulas."""
    option_count = len(choice_probabilities)
    choice_confidence = (max(choice_probabilities.values()) - 1 / option_count) / (1 - 1 / option_count)
    most_likely = max(urgency_probabilities, key=urgency_probabilities.get)
    level_count = len(urgency_probabilities)
    mean_distance = sum(abs(index - (level_count - 1) / 2) for index in range(level_count)) / level_count
    urgency_confidence = max(
        0.0, 1 - sum(probability * abs(int(level) - int(most_likely)) for level, probability in urgency_probabilities.items()) / mean_distance
    )
    return {
        "model": "jev-test",
        "usage": {"input_tokens": 1, "output_tokens": 1},
        "answers": {
            "is_spam": {"type": "noul", "noul": noul},
            "department": {"type": "choice", "choice": choice, "probabilities": choice_probabilities, "confidence": choice_confidence},
            "urgency": {
                "type": "score",
                "score": sum(int(level) * probability for level, probability in urgency_probabilities.items()),
                "legend": {str(index): situation for index, situation in enumerate(QUESTION_SET.questions["urgency"]["criteria"])},
                "probabilities": urgency_probabilities,
                "confidence": urgency_confidence,
            },
        },
    }


def decide_with(**answers):
    sent = []
    decision = decide(lambda body: (sent.append(body), response_body(**answers))[1], {"ticket": {"text": "x"}}, QUESTION_SET, "jev-test-model")
    return decision, sent[0]


CLEAR_BILLING = {
    "noul": 0.01,
    "choice": "billing",
    "choice_probabilities": {"billing": 0.9, "technical": 0.05, "sales": 0.03, "none_of_these": 0.02},
    "urgency_probabilities": {"0": 0, "1": 0.02, "2": 0.08, "3": 0.9},
}


class Request(unittest.TestCase):
    def test_one_batched_call_with_full_question_text(self):
        """Source: coding.md#typed-decisions-jev: one batched call per state; full meaning in every question."""
        _, body = decide_with(**CLEAR_BILLING)
        self.assertEqual(set(body["questions"]), {"is_spam", "department", "urgency"})
        self.assertIn("`ticket.text`", body["questions"]["department"]["instructions"])
        self.assertEqual(len(body["questions"]["urgency"]["criteria"]), 4)


class Noul(unittest.TestCase):
    def test_confident_spam_archives(self):
        """Source: coding.md#typed-decisions-jev: gate Noul with p >= bar."""
        decision, _ = decide_with(**{**CLEAR_BILLING, "noul": 0.99})
        self.assertEqual(spam_filter(decision, QUESTION_SET), "archive")

    def test_confident_not_spam_keeps(self):
        """Source: coding.md#typed-decisions-jev: gate Noul with p <= 1 - bar."""
        self.assertEqual(spam_filter(decide_with(**CLEAR_BILLING)[0], QUESTION_SET), "keep")

    def test_undecided_goes_to_human(self):
        """Source: coding.md#typed-decisions-jev: not sure goes to a person."""
        for probability in (0.5, 0.9, 0.1):  # 0.9 is "probably spam" but below the 0.98 archive bar
            self.assertEqual(spam_filter(decide_with(**{**CLEAR_BILLING, "noul": probability})[0], QUESTION_SET), "human", probability)


class Choice(unittest.TestCase):
    def test_confident_team_routes(self):
        """Source: coding.md#typed-decisions-jev: gate Choice on confidence."""
        for team in ("billing", "technical", "sales"):
            probabilities = {option: (0.85 if option == team else 0.05) for option in CLEAR_BILLING["choice_probabilities"]}
            self.assertEqual(
                department_router(decide_with(**{**CLEAR_BILLING, "choice": team, "choice_probabilities": probabilities})[0], QUESTION_SET), f"queue:{team}"
            )

    def test_flat_distribution_goes_to_human(self):
        """Source: coding.md#typed-decisions-jev: not sure goes to a person."""
        probabilities = {"billing": 0.4, "technical": 0.35, "sales": 0.15, "none_of_these": 0.1}  # confidence 0.2
        self.assertEqual(department_router(decide_with(**{**CLEAR_BILLING, "choice_probabilities": probabilities})[0], QUESTION_SET), "human")

    def test_none_of_these_goes_to_human(self):
        """Source: coding.md#typed-decisions-jev: none_of_these goes to a person."""
        probabilities = {"billing": 0.02, "technical": 0.02, "sales": 0.01, "none_of_these": 0.95}
        self.assertEqual(
            department_router(decide_with(**{**CLEAR_BILLING, "choice": "none_of_these", "choice_probabilities": probabilities})[0], QUESTION_SET), "human"
        )


class Score(unittest.TestCase):
    def test_mass_at_top_pages(self):
        """Source: coding.md#typed-decisions-jev: level >= k as P(level >= k) >= bar."""
        self.assertTrue(pager(decide_with(**CLEAR_BILLING)[0], QUESTION_SET))

    def test_weighted_score_between_levels_does_not_page(self):
        """Source: coding.md#typed-decisions-jev: never gate on the weighted score."""
        # score = 2.5 looks "above 2", but only half the mass is at level 3
        urgency_probabilities = {"0": 0, "1": 0, "2": 0.5, "3": 0.5}
        decision = decide_with(**{**CLEAR_BILLING, "urgency_probabilities": urgency_probabilities})[0]
        self.assertAlmostEqual(decision.answers["urgency"]["score"], 2.5)
        self.assertFalse(pager(decision, QUESTION_SET))

    def test_level_none_when_spread(self):
        """Source: coding.md#typed-decisions-jev: gate Score on confidence."""
        urgency_probabilities = {"0": 0.25, "1": 0.25, "2": 0.25, "3": 0.25}
        self.assertIsNone(decide_with(**{**CLEAR_BILLING, "urgency_probabilities": urgency_probabilities})[0].level("urgency", 0.5))


class Combined(unittest.TestCase):
    def test_route(self):
        """Source: coding.md#typed-decisions-jev: one decision feeds every app's policy."""
        self.assertEqual(route(decide_with(**CLEAR_BILLING)[0], QUESTION_SET), ["queue:billing", "page_manager"])


class Guards(unittest.TestCase):
    def test_uncalibrated_bars_send_everything_to_a_person(self):
        """Source: coding.md#typed-decisions-jev: uncalibrated bars send everything to a person."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "q.json"
            data = json.loads((ROOT / "questions/ticket_triage_v1.json").read_text())
            data["bars_status"] = "uncalibrated (wording changed in v2)"
            path.write_text(json.dumps(data))
            question_set = QuestionSet.load(path)
            self.assertEqual(route(decide_with(**CLEAR_BILLING)[0], question_set), ["human"])

    def test_bars_never_sent_to_jev(self):
        """Source: coding.md#typed-decisions-jev: bars are not sent."""
        _, body = decide_with(**CLEAR_BILLING)
        self.assertFalse(any("bars" in q for q in body["questions"].values()))

    def test_retuning_a_bar_keeps_the_wording_hash(self):
        """Source: coding.md#typed-decisions-jev: log raw answers with a wording hash; re-tuning edits bars in place."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "q.json"
            data = json.loads((ROOT / "questions/ticket_triage_v1.json").read_text())
            data["questions"]["is_spam"]["bars"]["archive"] = 0.9
            path.write_text(json.dumps(data))
            self.assertEqual(QuestionSet.load(path).wording_hash, QUESTION_SET.wording_hash)
            data["questions"]["is_spam"]["instructions"] += " "
            path.write_text(json.dumps(data))
            self.assertNotEqual(QuestionSet.load(path).wording_hash, QUESTION_SET.wording_hash)

    def test_wrong_type_read_is_loud(self):
        """Source: coding.md#failure: a wrong-type read fails loudly."""
        with self.assertRaises(TypeError):
            decide_with(**CLEAR_BILLING)[0].yes("department", 0.9)

    def test_missing_answer_is_loud(self):
        """Source: coding.md#failure: a missing answer fails loudly."""
        response = response_body(**CLEAR_BILLING)
        del response["answers"]["urgency"]
        with self.assertRaisesRegex(ValueError, "answers"):
            decide(lambda body: response, "x", QUESTION_SET, "jev-test-model")

    def test_raw_answers_logged(self):
        """Source: coding.md#typed-decisions-jev: log raw answers with a wording hash."""
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "jev.jsonl"
            decide(lambda body: response_body(**CLEAR_BILLING), {"ticket": {"text": "x"}}, QUESTION_SET, "jev-test-model", log)
            row = json.loads(log.read_text())
            self.assertEqual((row["set"], row["v"]), ("ticket_triage", 1))
            self.assertIn("probabilities", row["response"]["answers"]["urgency"])


if __name__ == "__main__":
    unittest.main()
