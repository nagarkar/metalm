"""Minimal Jev decision wrapper: one batched call, raw answers kept, confidence-gated reads."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

API = "https://api.typesafe.ai/v1/systemone"
Transport = Callable[[dict], dict]  # request body -> response body


@dataclass(frozen=True, slots=True)
class QuestionSet:
    """One decision: model-facing questions plus the bars that act on their answers."""

    id: str
    version: int
    calibrated: bool
    questions: Mapping[str, dict]  # exactly what is sent to Jev (bars stripped)
    bars: Mapping[str, Mapping[str, Any]]  # question key -> action -> bar

    @classmethod
    def load(cls, path: Path) -> QuestionSet:
        data = json.loads(path.read_text())
        questions = data["questions"].items()
        sent = {key: {field: value for field, value in question.items() if field != "bars"} for key, question in questions}
        bars = {key: MappingProxyType(question.get("bars", {})) for key, question in questions}
        calibrated = data["bars_status"].startswith("calibrated")
        return cls(data["id"], data["version"], calibrated, MappingProxyType(sent), MappingProxyType(bars))

    @property
    def wording_hash(self) -> str:  # cache/log key: changes with wording, never with bars
        return hashlib.sha256(json.dumps(dict(self.questions), sort_keys=True).encode()).hexdigest()[:16]

    def bar(self, key: str, action: str) -> Any:
        if not self.calibrated:
            raise Uncalibrated(f"{self.id} v{self.version}: bars not calibrated; send to a person")
        return self.bars[key][action]  # KeyError names a missing action


class Uncalibrated(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Decision:
    """Raw answers from one batched call. No I/O; build from stored JSON in tests."""

    question_set: str
    version: int
    model: str
    answers: Mapping[str, dict]

    def _answer(self, key: str, kind: str) -> dict:
        answer = self.answers[key]  # KeyError names a typo'd key
        if answer["type"] != kind:
            raise TypeError(f"{key} is {answer['type']}, not {kind}")
        return answer

    # Noul: the probability is the confidence. 0.5 = undecided.
    def yes(self, key: str, bar: float) -> bool:
        return self._answer(key, "noul")["noul"] >= bar

    def no(self, key: str, bar: float) -> bool:
        return self._answer(key, "noul")["noul"] <= 1 - bar

    # Choice: the option, or None when not sure.
    def choice(self, key: str, bar: float) -> str | None:
        answer = self._answer(key, "choice")
        return answer["choice"] if answer["confidence"] >= bar else None

    # Score: probability mass at or above a level (levels are ordered), so no off-by-one on `score`.
    def p_at_least(self, key: str, level: int) -> float:
        answer = self._answer(key, "score")
        return sum(probability for name, probability in answer["probabilities"].items() if int(name) >= level)

    def at_least(self, key: str, level: int, bar: float) -> bool:
        return self.p_at_least(key, level) >= bar

    # Score: the most likely level, or None when not sure.
    def level(self, key: str, bar: float) -> int | None:
        answer = self._answer(key, "score")
        if answer["confidence"] < bar:
            return None
        return int(max(answer["probabilities"], key=answer["probabilities"].get))


def http_transport(api_key: str, retries: int = 3) -> Transport:
    def send(body: dict) -> dict:
        request = urllib.request.Request(
            API, json.dumps(body).encode(), method="POST", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )
        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=60) as reply:
                    return json.load(reply)
            except urllib.error.HTTPError as error:  # retry only 429/529; anything else fails the step
                if error.code in (429, 529) and attempt < retries:
                    time.sleep(2**attempt)
                    continue
                raise RuntimeError(f"jev {error.code}: {error.read()[:300]!r}") from None
        raise AssertionError("unreachable")

    return send


def decide(transport: Transport, state: Any, question_set: QuestionSet, model: str, log: Path | None = None) -> Decision:
    """`model` comes from config (config.toml), never from code."""
    response = transport({"state": state, "model": model, "questions": dict(question_set.questions)})
    if set(response["answers"]) != set(question_set.questions):
        raise ValueError(f"answers {sorted(response['answers'])} != questions {sorted(question_set.questions)}")
    if log:  # raw answers kept: bars can be re-tuned without new calls
        with log.open("a") as log_file:
            log_file.write(
                json.dumps({"set": question_set.id, "v": question_set.version, "wording": question_set.wording_hash, "state": state, "response": response})
                + "\n"
            )
    return Decision(question_set.id, question_set.version, response["model"], MappingProxyType(response["answers"]))
