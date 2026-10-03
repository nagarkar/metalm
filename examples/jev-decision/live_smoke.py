"""Live smoke (billed): 4 tickets, one batched call each. Needs TYPESAFE_API_KEY in the environment."""
import json, os
from pathlib import Path
from jevkit import QuestionSet, decide, http_transport
from apps import route

key = os.environ["TYPESAFE_API_KEY"]
qs = QuestionSet.load(Path(__file__).parent / "questions/ticket_triage_v1.json")
send = http_transport(key)
tickets = {
    "spam": "CONGRATULATIONS!!! You won a $500 gift card. Click bit.ly/xx9 to claim now!!!",
    "billing_outage": "All our customer payouts have failed since Monday. We cannot pay our drivers today. Please fix this now.",
    "vague": "hi, something seems off, can someone look",
    "sales": "We're a 40-person team considering the Enterprise plan. Could you send a quote and tell us about annual discounts?",
}
usage = [0, 0]
for name, text in tickets.items():
    d = decide(send, {"ticket": {"text": text}}, qs, log=Path(__file__).parent / "live.jsonl")
    a = d.answers
    u = json.loads(Path(__file__).parent.joinpath("live.jsonl").read_text().splitlines()[-1])["response"]["usage"]
    usage[0] += u["input_tokens"]; usage[1] += u["output_tokens"]
    print(f"{name:15} spam={a['is_spam']['noul']:.3f}  dept={a['department']['choice']}"
          f"(conf {a['department']['confidence']:.2f})  urgency score={a['urgency']['score']:.2f} "
          f"conf={a['urgency']['confidence']:.2f} P(>=3)={d.p_at_least('urgency', 3):.2f}  -> {route(d, qs)}")
print(f"model={d.model} tokens in={usage[0]} out={usage[1]}")
