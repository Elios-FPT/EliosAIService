from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Callable, Mapping
from uuid import UUID


class AnswerStrategyEngine:
    """Deterministic answer selection for scenarios."""

    def __init__(
        self,
        scenario_id: str,
        strategy_config: dict | None,
        ideal_answers: Mapping[str, str],
        question_map: Mapping[UUID, UUID] | None = None,
    ):
        self.scenario_id = scenario_id
        self._config = strategy_config or {}
        self._strategy_type = (self._config.get("type") or "").lower()
        self._ideal_answers = dict(ideal_answers or {})
        self._question_map = dict(question_map or {})
        self._degrade_profile = self._config.get("degrade_profile") or {}
        self._scripted_answers = self._normalize_scripted_answers(
            self._config.get("scripted_answers") or {}
        )

    @property
    def enabled(self) -> bool:
        return bool(self._strategy_type)

    def get_answer(
        self,
        question_id: UUID,
        question_text: str,
        default_factory: Callable[[], str],
    ) -> str:
        """Return deterministic answer for given question or fallback."""
        if not self.enabled:
            return default_factory()

        match self._strategy_type:
            case "ideal":
                return self._require_ideal_answer(question_id)
            case "degraded":
                ideal = self._require_ideal_answer(question_id)
                return self._degrade_answer(question_id, ideal)
            case "scripted":
                return self._script_answer(question_id)
            case _:
                return default_factory()

    def _require_ideal_answer(self, question_id: UUID) -> str:
        key = str(question_id)
        if key not in self._ideal_answers:
            raise ValueError(
                f"No ideal answer available for question {question_id} "
                "(ensure question fixture includes ideal_answer)"
            )
        return self._ideal_answers[key]

    def _degrade_answer(self, question_id: UUID, text: str) -> str:
        keep_ratio = float(self._degrade_profile.get("keep_ratio", 0.5))
        keep_ratio = min(max(keep_ratio, 0.1), 1.0)
        min_sentences = int(self._degrade_profile.get("min_sentences", 1))
        rng = random.Random(f"{self.scenario_id}:{question_id}")

        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", text)
            if sentence.strip()
        ]
        if not sentences:
            return text[: max(1, len(text) // 4)]

        rng.shuffle(sentences)
        keep_count = max(min_sentences, int(len(sentences) * keep_ratio))
        keep_count = min(keep_count, len(sentences))
        degraded = " ".join(sentences[:keep_count]).strip()
        return degraded or sentences[0]

    def _script_answer(self, question_id: UUID) -> str:
        key = str(question_id)
        if key not in self._scripted_answers:
            raise ValueError(
                f"No scripted answer configured for question {question_id}"
            )
        value = self._scripted_answers[key]
        if isinstance(value, str):
            return self._expand_macro(value)
        if isinstance(value, dict) and "text" in value:
            text = value["text"]
            length = value.get("repeat_to_length")
            if isinstance(length, int) and length > 0:
                return self._repeat_text(text, length)
            return text
        raise ValueError(
            f"Unsupported scripted answer format for question {question_id}: {value}"
        )

    def _expand_macro(self, raw: str) -> str:
        upper = raw.upper()
        if upper == "EMPTY":
            return ""
        if upper.startswith("LONG_"):
            try:
                target_len = int(upper.split("_", 1)[1])
            except ValueError as exc:
                raise ValueError(f"Invalid LONG_ macro: {raw}") from exc
            return self._repeat_text(
                "This is an intentionally long answer to test length constraints. ",
                target_len,
            )
        return raw

    def _repeat_text(self, base: str, target_len: int) -> str:
        repeated = (base * ((target_len // len(base)) + 2))[:target_len]
        return repeated

    def _normalize_scripted_answers(
        self, raw_answers: Mapping[str, str]
    ) -> dict[str, str | dict]:
        normalized: dict[str, str | dict] = {}
        for key, value in raw_answers.items():
            actual_id = self._resolve_question_id(key)
            normalized[str(actual_id)] = value
        return normalized

    def _resolve_question_id(self, raw_id: str) -> UUID:
        candidate = UUID(raw_id)
        return self._question_map.get(candidate, candidate)


__all__ = ["AnswerStrategyEngine"]

