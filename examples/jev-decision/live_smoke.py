"""Live smoke (billed): 4 tickets, one batched call each.

Runs only with METALM_LIVE=1 and TYPESAFE_API_KEY in the environment; the model comes from config.toml.
"""

import json
import os
import sys
import tomllib
from pathlib import Path

from apps import route
from jevkit import QuestionSet, decide, http_transport

HERE = Path(__file__).parent
if os.environ.get("METALM_LIVE") != "1":
    sys.exit("error: live smoke makes billed calls. Run: METALM_LIVE=1 python live_smoke.py")
model = tomllib.loads((HERE / "config.toml").read_text())["ticket_triage"]["model"]
question_set = QuestionSet.load(HERE / "questions/ticket_triage_v1.json")
send = http_transport(os.environ["TYPESAFE_API_KEY"])
log = HERE / "live.jsonl"
tickets = {
    "spam": "CONGRATULATIONS!!! You won a $500 gift card. Click bit.ly/xx9 to claim now!!!",
    "billing_outage": "All our customer payouts have failed since Monday. We cannot pay our drivers today. Please fix this now.",
    "vague": "hi, something seems off, can someone look",
    "sales": "We're a 40-person team considering the Enterprise plan. Could you send a quote and tell us about annual discounts?",
}
tokens_in = tokens_out = 0
for name, text in tickets.items():
    decision = decide(send, {"ticket": {"text": text}}, question_set, model, log=log)
    answers = decision.answers
    usage = json.loads(log.read_text().splitlines()[-1])["response"]["usage"]
    tokens_in += usage["input_tokens"]
    tokens_out += usage["output_tokens"]
    print(
        f"{name:15} spam={answers['is_spam']['noul']:.3f}  dept={answers['department']['choice']}"
        f"(conf {answers['department']['confidence']:.2f})  urgency score={answers['urgency']['score']:.2f} "
        f"conf={answers['urgency']['confidence']:.2f} P(>=3)={decision.p_at_least('urgency', 3):.2f}  -> {route(decision, question_set)}"
    )
print(f"model={decision.model} tokens in={tokens_in} out={tokens_out}")
