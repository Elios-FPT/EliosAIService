from uuid import UUID

import pytest

from tests.bot.answer_strategy import AnswerStrategyEngine


QUESTION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _default_factory():
    return "fallback"


def test_ideal_strategy_returns_exact_answer():
    engine = AnswerStrategyEngine(
        scenario_id="mock-001",
        strategy_config={"type": "ideal"},
        ideal_answers={str(QUESTION_ID): "Ideal text"},
        question_map=None,
    )

    answer = engine.get_answer(QUESTION_ID, "question", _default_factory)

    assert answer == "Ideal text"


def test_degraded_strategy_removes_portion_of_answer():
    long_answer = (
        "Sentence one explains the topic. "
        "Sentence two adds detail. "
        "Sentence three gives an example."
    )
    engine = AnswerStrategyEngine(
        scenario_id="mock-002",
        strategy_config={"type": "degraded", "degrade_profile": {"keep_ratio": 0.4}},
        ideal_answers={str(QUESTION_ID): long_answer},
        question_map=None,
    )

    answer = engine.get_answer(QUESTION_ID, "question", _default_factory)

    assert len(answer.split(".")) <= len(long_answer.split("."))
    assert answer.strip() != ""


def test_scripted_strategy_accepts_fixture_ids_and_macros():
    fixture_question_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    actual_question_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    second_question_id = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    engine = AnswerStrategyEngine(
        scenario_id="mock-003",
        strategy_config={
            "type": "scripted",
            "scripted_answers": {
                str(fixture_question_id): "EMPTY",
                str(second_question_id): "LONG_50",
            },
        },
        ideal_answers={},
        question_map={fixture_question_id: actual_question_id},
    )

    empty_answer = engine.get_answer(actual_question_id, "question", _default_factory)
    long_answer = engine.get_answer(second_question_id, "question", _default_factory)

    assert empty_answer == ""
    assert len(long_answer) == 50


def test_strategy_disabled_falls_back_to_default():
    engine = AnswerStrategyEngine(
        scenario_id="mock-004",
        strategy_config=None,
        ideal_answers={},
        question_map=None,
    )

    answer = engine.get_answer(QUESTION_ID, "question", lambda: "generated")

    assert answer == "generated"

