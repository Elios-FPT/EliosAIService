"""Evaluation parity tests between legacy and workflow paths.

Tests that workflow evaluation outputs match legacy evaluation outputs.
Focus: Score accuracy, feedback consistency, gap detection.
"""
import pytest
from tests.parity.conftest import (
    extract_gap_concepts,
    compare_scores,
    compare_feedback_fields,
)


class TestEvaluationParity:
    """Compare evaluation outputs between legacy and workflow paths."""

    @pytest.mark.asyncio
    async def test_evaluation_scores_match(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test evaluation scores match within tolerance (+/- 2 points)."""
        interview_id = test_interview["interview"]["id"]
        answer_text = "Async/await allows concurrent execution using coroutines"

        # Run both paths
        legacy_result = await legacy_runner(interview_id, [answer_text], container)
        workflow_result = await workflow_runner(interview_id, [answer_text], container)

        # Extract evaluations
        legacy_evals = legacy_result["evaluations"]
        workflow_evals = workflow_result["evaluations"]

        assert len(legacy_evals) > 0, "Legacy path returned no evaluations"
        assert len(workflow_evals) > 0, "Workflow path returned no evaluations"

        legacy_eval = legacy_evals[0]
        workflow_eval = workflow_evals[0]

        # Assert scores within tolerance
        legacy_score = float(legacy_eval["score"])
        workflow_score = float(workflow_eval["score"])

        assert compare_scores(legacy_score, workflow_score, tolerance=2.0), (
            f"Score mismatch exceeds tolerance: "
            f"legacy={legacy_score}, workflow={workflow_score}, "
            f"diff={abs(legacy_score - workflow_score)}"
        )

    @pytest.mark.asyncio
    async def test_evaluation_feedback_consistency(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test feedback fields present and similar structure."""
        interview_id = test_interview["interview"]["id"]
        answer_text = "Brief answer with gaps"

        # Run both paths
        legacy_result = await legacy_runner(interview_id, [answer_text], container)
        workflow_result = await workflow_runner(interview_id, [answer_text], container)

        legacy_eval = legacy_result["evaluations"][0]
        workflow_eval = workflow_result["evaluations"][0]

        # Compare feedback field presence
        comparison = compare_feedback_fields(legacy_eval, workflow_eval)

        assert comparison["has_feedback"], "Feedback field mismatch"
        assert comparison["has_strengths"], "Strengths field mismatch"
        assert comparison["has_weaknesses"], "Weaknesses field mismatch"
        assert comparison["has_gaps"], "Gaps field mismatch"

        # Assert both have non-empty feedback
        assert len(legacy_eval["feedback"]) > 0, "Legacy feedback is empty"
        assert len(workflow_eval["feedback"]) > 0, "Workflow feedback is empty"

        # Assert strengths/weaknesses are lists
        assert isinstance(legacy_eval["strengths"], list)
        assert isinstance(workflow_eval["strengths"], list)
        assert isinstance(legacy_eval["weaknesses"], list)
        assert isinstance(workflow_eval["weaknesses"], list)

    @pytest.mark.asyncio
    async def test_gap_detection_parity(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test gap detection produces same concepts (order-independent)."""
        interview_id = test_interview["interview"]["id"]
        # Provide incomplete answer to trigger gap detection
        answer_text = "Async is concurrent"

        # Run both paths
        legacy_result = await legacy_runner(interview_id, [answer_text], container)
        workflow_result = await workflow_runner(interview_id, [answer_text], container)

        legacy_eval = legacy_result["evaluations"][0]
        workflow_eval = workflow_result["evaluations"][0]

        # Extract gap concepts
        legacy_gaps = extract_gap_concepts(legacy_eval)
        workflow_gaps = extract_gap_concepts(workflow_eval)

        # Assert same gap concepts (order doesn't matter)
        # Allow some flexibility - gaps should overlap significantly
        if len(legacy_gaps) > 0 and len(workflow_gaps) > 0:
            overlap = legacy_gaps.intersection(workflow_gaps)
            legacy_only = legacy_gaps - workflow_gaps
            workflow_only = workflow_gaps - legacy_gaps

            # At least 50% overlap expected
            min_gap_count = min(len(legacy_gaps), len(workflow_gaps))
            overlap_ratio = len(overlap) / min_gap_count if min_gap_count > 0 else 0

            assert overlap_ratio >= 0.5, (
                f"Gap concept mismatch: overlap={overlap_ratio:.1%}, "
                f"legacy_gaps={legacy_gaps}, workflow_gaps={workflow_gaps}, "
                f"legacy_only={legacy_only}, workflow_only={workflow_only}"
            )

    @pytest.mark.asyncio
    async def test_strengths_detected(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test both paths detect answer strengths."""
        interview_id = test_interview["interview"]["id"]
        # Provide good answer
        answer_text = (
            "Async/await in Python enables asynchronous programming using coroutines. "
            "It allows concurrent execution without blocking threads, improving performance "
            "for I/O-bound operations like API calls and database queries."
        )

        # Run both paths
        legacy_result = await legacy_runner(interview_id, [answer_text], container)
        workflow_result = await workflow_runner(interview_id, [answer_text], container)

        legacy_eval = legacy_result["evaluations"][0]
        workflow_eval = workflow_result["evaluations"][0]

        # Both should detect strengths
        legacy_strengths = legacy_eval.get("strengths", [])
        workflow_strengths = workflow_eval.get("strengths", [])

        assert isinstance(legacy_strengths, list), "Legacy strengths not a list"
        assert isinstance(workflow_strengths, list), "Workflow strengths not a list"

        # For good answer, expect at least one strength
        assert len(legacy_strengths) > 0, "Legacy detected no strengths"
        assert len(workflow_strengths) > 0, "Workflow detected no strengths"

    @pytest.mark.asyncio
    async def test_weaknesses_detected(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test both paths detect answer weaknesses."""
        interview_id = test_interview["interview"]["id"]
        # Provide weak answer
        answer_text = "Async is about doing things concurrently"

        # Run both paths
        legacy_result = await legacy_runner(interview_id, [answer_text], container)
        workflow_result = await workflow_runner(interview_id, [answer_text], container)

        legacy_eval = legacy_result["evaluations"][0]
        workflow_eval = workflow_result["evaluations"][0]

        # Both should detect weaknesses
        legacy_weaknesses = legacy_eval.get("weaknesses", [])
        workflow_weaknesses = workflow_eval.get("weaknesses", [])

        assert isinstance(legacy_weaknesses, list), "Legacy weaknesses not a list"
        assert isinstance(workflow_weaknesses, list), "Workflow weaknesses not a list"

        # For weak answer, expect at least one weakness
        assert len(legacy_weaknesses) > 0, "Legacy detected no weaknesses"
        assert len(workflow_weaknesses) > 0, "Workflow detected no weaknesses"

    @pytest.mark.asyncio
    async def test_multiple_evaluations(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test evaluation consistency across multiple answers."""
        interview_id = test_interview["interview"]["id"]
        answers = [
            "Async/await enables asynchronous programming",
            "The GIL prevents true parallelism in Python",
            "Decorators modify function behavior without changing code",
        ]

        # Run both paths
        legacy_result = await legacy_runner(interview_id, answers, container)
        workflow_result = await workflow_runner(interview_id, answers, container)

        legacy_evals = legacy_result["evaluations"]
        workflow_evals = workflow_result["evaluations"]

        # Both should produce same number of evaluations
        assert len(legacy_evals) == len(answers), (
            f"Legacy eval count mismatch: {len(legacy_evals)} != {len(answers)}"
        )
        assert len(workflow_evals) == len(answers), (
            f"Workflow eval count mismatch: {len(workflow_evals)} != {len(answers)}"
        )

        # Compare each evaluation pair
        for i, (legacy_eval, workflow_eval) in enumerate(
            zip(legacy_evals, workflow_evals)
        ):
            legacy_score = float(legacy_eval["score"])
            workflow_score = float(workflow_eval["score"])

            assert compare_scores(legacy_score, workflow_score, tolerance=2.0), (
                f"Evaluation {i+1} score mismatch: "
                f"legacy={legacy_score}, workflow={workflow_score}"
            )


class TestEvaluationEdgeCases:
    """Test evaluation edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_answer_evaluation(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test evaluation handles empty/minimal answers."""
        interview_id = test_interview["interview"]["id"]
        answer_text = ""

        # Run both paths
        legacy_result = await legacy_runner(interview_id, [answer_text], container)
        workflow_result = await workflow_runner(interview_id, [answer_text], container)

        # Both should still produce evaluations
        assert len(legacy_result["evaluations"]) > 0, "Legacy failed on empty answer"
        assert len(workflow_result["evaluations"]) > 0, "Workflow failed on empty answer"

        # Scores should be low but within tolerance
        legacy_score = float(legacy_result["evaluations"][0]["score"])
        workflow_score = float(workflow_result["evaluations"][0]["score"])

        assert compare_scores(legacy_score, workflow_score, tolerance=2.0)

    @pytest.mark.asyncio
    async def test_very_long_answer_evaluation(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test evaluation handles very long answers."""
        interview_id = test_interview["interview"]["id"]
        # Create long answer (500 words)
        answer_text = (
            "Async/await in Python is a powerful feature. " * 100
        )  # ~500 words

        # Run both paths
        legacy_result = await legacy_runner(interview_id, [answer_text], container)
        workflow_result = await workflow_runner(interview_id, [answer_text], container)

        # Both should handle long answers
        assert len(legacy_result["evaluations"]) > 0
        assert len(workflow_result["evaluations"]) > 0

        # Scores should be comparable
        legacy_score = float(legacy_result["evaluations"][0]["score"])
        workflow_score = float(workflow_result["evaluations"][0]["score"])

        assert compare_scores(legacy_score, workflow_score, tolerance=2.0)

    @pytest.mark.asyncio
    async def test_irrelevant_answer_evaluation(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test evaluation detects completely irrelevant answers."""
        interview_id = test_interview["interview"]["id"]
        # Question is about async/await, answer is about unrelated topic
        answer_text = "The weather today is sunny and warm"

        # Run both paths
        legacy_result = await legacy_runner(interview_id, [answer_text], container)
        workflow_result = await workflow_runner(interview_id, [answer_text], container)

        legacy_eval = legacy_result["evaluations"][0]
        workflow_eval = workflow_result["evaluations"][0]

        # Both should give low scores for irrelevant answer
        legacy_score = float(legacy_eval["score"])
        workflow_score = float(workflow_eval["score"])

        assert legacy_score < 50, "Legacy didn't penalize irrelevant answer"
        assert workflow_score < 50, "Workflow didn't penalize irrelevant answer"

        # Scores should be comparable
        assert compare_scores(legacy_score, workflow_score, tolerance=2.0)
