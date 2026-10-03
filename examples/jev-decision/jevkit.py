"""Minimal Jev decision wrapper: one batched call, raw answers kept, confidence-gated reads."""
from __future__ import annotations
import hashlib, json, time, urllib.request, urllib.error
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

API = "https://api.typesafe.ai/v1/systemone"
Transport = Callable[[dict], dict]          # request body -> response body


@dataclass(frozen=True, slots=True)
class QuestionSet:
    """One decision: model-facing questions plus the bars that act on their answers."""
    id: str
    version: int
    calibrated: bool
    questions: Mapping[str, dict]          # exactly what is sent to Jev (bars stripped)
    bars: Mapping[str, Mapping[str, Any]]  # question key -> action -> bar

    @classmethod
    def load(cls, path: Path) -> "QuestionSet":
        d = json.loads(path.read_text())
        sent = {k: {f: v for f, v in q.items() if f != "bars"} for k, q in d["questions"].items()}
        bars = {k: MappingProxyType(q.get("bars", {})) for k, q in d["questions"].items()}
        return cls(d["id"], d["version"], d["bars_status"].startswith("calibrated"),
                   MappingProxyType(sent), MappingProxyType(bars))

    @property
    def wording_hash(self) -> str:         # cache/log key: changes with wording, never with bars
        return hashlib.sha256(json.dumps(dict(self.questions), sort_keys=True).encode()).hexdigest()[:16]

    def bar(self, key: str, action: str) -> Any:
        if not self.calibrated:
            raise Uncalibrated(f"{self.id} v{self.version}: bars not calibrated; send to a person")
        return self.bars[key][action]      # KeyError names a missing action


class Uncalibrated(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Decision:
    """Raw answers from one batched call. No I/O; build from stored JSON in tests."""
    question_set: str
    version: int
    model: str
    answers: Mapping[str, dict]

    def _a(self, key: str, kind: str) -> dict:
        a = self.answers[key]                     # KeyError names a typo'd key
        if a["type"] != kind:
            raise TypeError(f"{key} is {a['type']}, not {kind}")
        return a

    # Noul: the probability is the confidence. 0.5 = undecided.
    def yes(self, key: str, bar: float) -> bool:
        return self._a(key, "noul")["noul"] >= bar

    def no(self, key: str, bar: float) -> bool:
        return self._a(key, "noul")["noul"] <= 1 - bar

    # Choice: the option, or None when not sure.
    def choice(self, key: str, bar: float) -> str | None:
        a = self._a(key, "choice")
        return a["choice"] if a["confidence"] >= bar else None

    # Score: probability mass at or above a level (levels are ordered), so no off-by-one on `score`.
    def p_at_least(self, key: str, level: int) -> float:
        a = self._a(key, "score")
        return sum(p for k, p in a["probabilities"].items() if int(k) >= level)

    def at_least(self, key: str, level: int, bar: float) -> bool:
        return self.p_at_least(key, level) >= bar

    # Score: the most likely level, or None when not sure.
    def level(self, key: str, bar: float) -> int | None:
        a = self._a(key, "score")
        if a["confidence"] < bar:
            return None
        return int(max(a["probabilities"], key=a["probabilities"].get))


def http_transport(api_key: str, retries: int = 3) -> Transport:
    def send(body: dict) -> dict:
        req = urllib.request.Request(API, json.dumps(body).encode(), method="POST", headers={
            "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:      # retry only 429/529; anything else fails the step
                if e.code in (429, 529) and attempt < retries:
                    time.sleep(2 ** attempt); continue
                raise RuntimeError(f"jev {e.code}: {e.read()[:300]!r}") from None
        raise AssertionError("unreachable")
    return send


def decide(transport: Transport, state: Any, qs: QuestionSet, log: Path | None = None) -> Decision:
    resp = transport({"state": state, "model": "jev-latest", "questions": dict(qs.questions)})
    if set(resp["answers"]) != set(qs.questions):
        raise ValueError(f"answers {sorted(resp['answers'])} != questions {sorted(qs.questions)}")
    if log:                                        # raw answers kept: bars can be re-tuned without new calls
        with log.open("a") as f:
            f.write(json.dumps({"set": qs.id, "v": qs.version, "wording": qs.wording_hash, "state": state, "response": resp}) + "\n")
    return Decision(qs.id, qs.version, resp["model"], MappingProxyType(resp["answers"]))
