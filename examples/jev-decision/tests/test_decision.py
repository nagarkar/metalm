import json, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from jevkit import Decision, QuestionSet, Uncalibrated, decide
from apps import department_router, pager, route, spam_filter

QS = QuestionSet.load(ROOT / "questions/ticket_triage_v1.json")

def resp(noul, choice, cprobs, uprobs):
    """Response in the documented /v1/systemone shape. Confidence recomputed with the documented formulas."""
    n = len(cprobs); cconf = (max(cprobs.values()) - 1/n) / (1 - 1/n)
    m = max(uprobs, key=uprobs.get); L = len(uprobs)
    mad = sum(abs(i - (L-1)/2) for i in range(L)) / L
    uconf = max(0.0, 1 - sum(p * abs(int(k) - int(m)) for k, p in uprobs.items()) / mad)
    return {"model": "jev-test", "usage": {"input_tokens": 1, "output_tokens": 1}, "answers": {
        "is_spam": {"type": "noul", "noul": noul},
        "department": {"type": "choice", "choice": choice, "probabilities": cprobs, "confidence": cconf},
        "urgency": {"type": "score", "score": sum(int(k)*p for k, p in uprobs.items()),
                    "legend": {str(i): s for i, s in enumerate(QS.questions["urgency"]["criteria"])},
                    "probabilities": uprobs, "confidence": uconf}}}

def D(**kw):
    sent = []
    d = decide(lambda body: (sent.append(body), resp(**kw))[1], {"ticket": {"text": "x"}}, QS)
    return d, sent[0]

CLEAR_BILLING = dict(noul=0.01, choice="billing",
                     cprobs={"billing": .9, "technical": .05, "sales": .03, "none_of_these": .02},
                     uprobs={"0": 0, "1": .02, "2": .08, "3": .9})

class Request(unittest.TestCase):
    def test_one_batched_call_with_full_question_text(self):
        _, body = D(**CLEAR_BILLING)
        self.assertEqual(set(body["questions"]), {"is_spam", "department", "urgency"})
        self.assertIn("`ticket.text`", body["questions"]["department"]["instructions"])
        self.assertEqual(len(body["questions"]["urgency"]["criteria"]), 4)

class Noul(unittest.TestCase):
    def test_confident_spam_archives(self):
        d, _ = D(**{**CLEAR_BILLING, "noul": 0.99})
        self.assertEqual(spam_filter(d, QS), "archive")
    def test_confident_not_spam_keeps(self):
        self.assertEqual(spam_filter(D(**CLEAR_BILLING)[0], QS), "keep")
    def test_undecided_goes_to_human(self):
        for p in (0.5, 0.9, 0.1):          # 0.9 is "probably spam" but below the 0.98 archive bar
            self.assertEqual(spam_filter(D(**{**CLEAR_BILLING, "noul": p})[0], QS), "human", p)

class Choice(unittest.TestCase):
    def test_confident_team_routes(self):
        for team in ("billing", "technical", "sales"):
            probs = {k: (.85 if k == team else .05) for k in CLEAR_BILLING["cprobs"]}
            self.assertEqual(department_router(D(**{**CLEAR_BILLING, "choice": team, "cprobs": probs})[0], QS),
                             f"queue:{team}")
    def test_flat_distribution_goes_to_human(self):
        probs = {"billing": .4, "technical": .35, "sales": .15, "none_of_these": .1}   # confidence 0.2
        self.assertEqual(department_router(D(**{**CLEAR_BILLING, "cprobs": probs})[0], QS), "human")
    def test_none_of_these_goes_to_human(self):
        probs = {"billing": .02, "technical": .02, "sales": .01, "none_of_these": .95}
        self.assertEqual(department_router(D(**{**CLEAR_BILLING, "choice": "none_of_these", "cprobs": probs})[0], QS), "human")

class Score(unittest.TestCase):
    def test_mass_at_top_pages(self):
        self.assertTrue(pager(D(**CLEAR_BILLING)[0], QS))
    def test_weighted_score_between_levels_does_not_page(self):
        # score = 2.5 looks "above 2", but only half the mass is at level 3
        u = {"0": 0, "1": 0, "2": .5, "3": .5}
        d = D(**{**CLEAR_BILLING, "uprobs": u})[0]
        self.assertAlmostEqual(d.answers["urgency"]["score"], 2.5)
        self.assertFalse(pager(d, QS))
    def test_level_none_when_spread(self):
        u = {"0": .25, "1": .25, "2": .25, "3": .25}
        self.assertIsNone(D(**{**CLEAR_BILLING, "uprobs": u})[0].level("urgency", 0.5))

class Combined(unittest.TestCase):
    def test_route(self):
        self.assertEqual(route(D(**CLEAR_BILLING)[0], QS), ["queue:billing", "page_manager"])

class Guards(unittest.TestCase):
    def test_uncalibrated_bars_send_everything_to_a_person(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "q.json"
            d = json.loads((ROOT / "questions/ticket_triage_v1.json").read_text())
            d["bars_status"] = "uncalibrated (wording changed in v2)"
            p.write_text(json.dumps(d))
            qs = QuestionSet.load(p)
            self.assertEqual(route(D(**CLEAR_BILLING)[0], qs), ["human"])
    def test_bars_never_sent_to_jev(self):
        _, body = D(**CLEAR_BILLING)
        self.assertFalse(any("bars" in q for q in body["questions"].values()))
    def test_retuning_a_bar_keeps_the_wording_hash(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "q.json"
            d = json.loads((ROOT / "questions/ticket_triage_v1.json").read_text())
            d["questions"]["is_spam"]["bars"]["archive"] = 0.9
            p.write_text(json.dumps(d))
            self.assertEqual(QuestionSet.load(p).wording_hash, QS.wording_hash)
            d["questions"]["is_spam"]["instructions"] += " "
            p.write_text(json.dumps(d))
            self.assertNotEqual(QuestionSet.load(p).wording_hash, QS.wording_hash)
    def test_wrong_type_read_is_loud(self):
        with self.assertRaises(TypeError):
            D(**CLEAR_BILLING)[0].yes("department", 0.9)
    def test_missing_answer_is_loud(self):
        r = resp(**CLEAR_BILLING); del r["answers"]["urgency"]
        with self.assertRaisesRegex(ValueError, "answers"):
            decide(lambda b: r, "x", QS)
    def test_raw_answers_logged(self):
        with tempfile.TemporaryDirectory() as t:
            log = Path(t) / "jev.jsonl"
            decide(lambda b: resp(**CLEAR_BILLING), {"ticket": {"text": "x"}}, QS, log)
            row = json.loads(log.read_text())
            self.assertEqual((row["set"], row["v"]), ("ticket_triage", 1))
            self.assertIn("probabilities", row["response"]["answers"]["urgency"])

if __name__ == "__main__":
    unittest.main()
