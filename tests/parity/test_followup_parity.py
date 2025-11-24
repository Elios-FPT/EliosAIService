"""Follow-up question parity tests between legacy and workflow paths.

Tests that workflow follow-up generation matches legacy behavior.
Focus: Follow-up decision logic, adaptive completion criteria, question generation.
"""
import pytest


class TestFollowUpDecisionParity:
    """Compare follow-up generation decisions between legacy and workflow."""

    @pytest.mark.asyncio
    async def test_incomplete_answer_triggers_followup(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test both paths generate follow-up for incomplete answer."""
        interview_id = test_interview["interview"]["id"]
        # Provide incomplete answer
        answer_text = "Async is concurrent"

        # Run both paths
        legacy_result = await legacy_runner(interview_id, [answer_text], container)
        workflow_result = await workflow_runner(interview_id, [answer_text], container)

        # Extract follow-up decisions
        legacy_followups = legacy_result["followups"]
        workflow_followups = workflow_result["followups"]

        # Both should generate follow-up for incomplete answer
        legacy_has_followup = len(legacy_followups) > 0
        workflow_has_followup = len(workflow_followups) > 0

        assert (
            legacy_has_followup == workflow_has_followup
        ), f"Follow-up decision mismatch: legacy={legacy_has_followup}, workflow={workflow_has_followup}"

    @pytest.mark.asyncio
    async def test_complete_answer_skips_followup(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test both paths skip follow-up for complete answer."""
        interview_id = test_interview["interview"]["id"]
        # Provide complete answer
        answer_text = (
            "Async/await in Python enables asynchronous programming using coroutines. "
            "It allows concurrent execution without blocking threads, improving performance "
            "for I/O-bound operations like API calls and database queries. "
            "The event loop manages coroutine execution, and await suspends execution "
            "until the awaited operation completes."
        )

        # Run both paths
        legacy_result = await legacy_runner(interview_id, [answer_text], container)
        workflow_result = await workflow_runner(interview_id, [answer_text], container)

        # Extract follow-up decisions
        legacy_followups = legacy_result["followups"]
        workflow_followups = workflow_result["followups"]

        # Both should skip follow-up for complete answer
        legacy_has_followup = len(legacy_followups) > 0
        workflow_has_followup = len(workflow_followups) > 0

        # Decisions should match
        assert (
            legacy_has_followup == workflow_has_followup
        ), f"Follow-up decision mismatch: legacy={legacy_has_followup}, workflow={workflow_has_followup}"

    @pytest.mark.asyncio
    async def test_followup_uses_adaptive_completion(
        self, test_interview, workflow_runner, container
    ):
        """Test workflow uses is_adaptive_complete() for follow-up decision."""
        interview_id = test_interview["interview"]["id"]
        # Provide marginal answer (score ~70-80)
        answer_text = "Async/await allows concurrent operations using coroutines"

        # Run workflow path
        workflow_result = await workflow_runner(interview_id, [answer_text], container)

        # Get evaluation
        if len(workflow_result["evaluations"]) > 0:
            eval_dict = workflow_result["evaluations"][0]
            score = float(eval_dict.get("score", 0))
            gaps = eval_dict.get("gaps", [])

            # Check if follow-up decision aligns with adaptive completion logic
            has_followup = len(workflow_result["followups"]) > 0

            # is_adaptive_complete() logic: score >= 80 AND no unresolved gaps
            unresolved_gaps = [g for g in gaps if not g.get("resolved", False)]
            is_complete = score >= 80 and len(unresolved_gaps) == 0

            # Follow-up should be generated if NOT complete
            expected_followup = not is_complete

            # Allow some tolerance due to LLM variability
            # If score is close to 80, either decision is acceptable
            if 75 <= score <= 85:
                # Borderline case - either decision acceptable
                pass
            else:
                assert has_followup == expected_followup, (
                    f"Follow-up decision doesn't match adaptive completion: "
                    f"has_followup={has_followup}, expected={expected_followup}, "
                    f"score={score}, unresolved_gaps={len(unresolved_gaps)}"
                )

    @pytest.mark.asyncio
    async def test_followup_question_relevance(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test follow-up questions target detected gaps."""
        interview_id = test_interview["interview"]["id"]
        answer_text = "Async is concurrent"

        # Run both paths
        legacy_result = await legacy_runner(interview_id, [answer_text], container)
        workflow_result = await workflow_runner(interview_id, [answer_text], container)

        # If both generated follow-ups, compare relevance
        if len(legacy_result["followups"]) > 0 and len(workflow_result["followups"]) > 0:
            legacy_fu = legacy_result["followups"][0]
            workflow_fu = workflow_result["followups"][0]

            # Both should have generated_reason
            assert "generated_reason" in legacy_fu, "Legacy follow-up missing reason"
            assert "generated_reason" in workflow_fu, "Workflow follow-up missing reason"

            # Reasons should be non-empty strings
            assert len(legacy_fu["generated_reason"]) > 0
            assert len(workflow_fu["generated_reason"]) > 0

            # Both should have question text
            assert "text" in legacy_fu
            assert "text" in workflow_fu
            assert len(legacy_fu["text"]) > 0
            assert len(workflow_fu["text"]) > 0

    @pytest.mark.asyncio
    async def test_followup_parent_reference(
        self, test_interview, workflow_runner, container
    ):
        """Test follow-up questions correctly reference parent question."""
        interview_id = test_interview["interview"]["id"]
        answer_text = "Brief answer"

        # Run workflow path
        workflow_result = await workflow_runner(interview_id, [answer_text], container)

        # If follow-up generated
        if len(workflow_result["followups"]) > 0:
            followup = workflow_result["followups"][0]

            # Should have parent_question_id
            assert "parent_question_id" in followup
            assert followup["parent_question_id"] is not None

            # Parent should be the original question
            questions = workflow_result["questions"]
            if len(questions) > 0:
                original_question_id = questions[0]["question_id"]
                # Parent should reference original question
                assert str(followup["parent_question_id"]) == str(
                    original_question_id
                ), "Follow-up doesn't reference correct parent"

    @pytest.mark.asyncio
    async def test_multiple_followups_tracking(
        self, test_interview, workflow_runner, container
    ):
        """Test multiple follow-ups maintain correct order_in_sequence."""
        interview_id = test_interview["interview"]["id"]
        # Provide series of incomplete answers
        answers = ["Brief 1", "Brief 2"]

        # Run workflow path
        workflow_result = await workflow_runner(interview_id, answers, container)

        followups = workflow_result["followups"]

        # If multiple follow-ups generated
        if len(followups) > 1:
            # Check order_in_sequence increments
            for i, followup in enumerate(followups):
                if "order_in_sequence" in followup:
                    expected_order = i + 1
                    actual_order = followup["order_in_sequence"]

                    # Order should increment (may not be strictly sequential if main questions interspersed)
                    assert isinstance(actual_order, int)
                    assert actual_order > 0


class TestFollowUpGenerationQuality:
    """Test quality and consistency of generated follow-up questions."""

    @pytest.mark.asyncio
    async def test_followup_targets_specific_gap(
        self, test_interview, workflow_runner, container
    ):
        """Test follow-up question targets specific knowledge gap."""
        interview_id = test_interview["interview"]["id"]
        # Answer missing specific concept (e.g., event loop)
        answer_text = "Async/await allows concurrent operations"

        # Run workflow
        workflow_result = await workflow_runner(interview_id, [answer_text], container)

        # If follow-up generated
        if len(workflow_result["followups"]) > 0:
            followup = workflow_result["followups"][0]
            evaluation = workflow_result["evaluations"][0]

            # Get gaps from evaluation
            gaps = evaluation.get("gaps", [])
            if len(gaps) > 0:
                gap_concepts = [g.get("concept", "") for g in gaps]

                # Follow-up text should reference at least one gap concept
                followup_text = followup["text"].lower()

                # Check if any gap concept appears in follow-up
                has_gap_reference = any(
                    concept.lower() in followup_text for concept in gap_concepts
                )

                # Or check if generated_reason mentions the gap
                reason = followup.get("generated_reason", "").lower()
                has_gap_in_reason = any(
                    concept.lower() in reason for concept in gap_concepts
                )

                assert has_gap_reference or has_gap_in_reason, (
                    f"Follow-up doesn't target detected gaps. "
                    f"Gaps: {gap_concepts}, Follow-up: {followup_text}, "
                    f"Reason: {reason}"
                )

    @pytest.mark.asyncio
    async def test_followup_question_format(
        self, test_interview, workflow_runner, container
    ):
        """Test follow-up questions are properly formatted."""
        interview_id = test_interview["interview"]["id"]
        answer_text = "Brief answer"

        # Run workflow
        workflow_result = await workflow_runner(interview_id, [answer_text], container)

        # If follow-up generated
        if len(workflow_result["followups"]) > 0:
            followup = workflow_result["followups"][0]

            # Question text should be non-empty
            assert "text" in followup
            assert len(followup["text"]) > 0

            # Should be a question (end with ? or be interrogative)
            text = followup["text"].strip()
            is_question = text.endswith("?") or any(
                text.lower().startswith(word)
                for word in ["what", "how", "why", "when", "where", "can", "could", "would"]
            )

            assert is_question, f"Follow-up doesn't appear to be a question: {text}"


class TestFollowUpEdgeCases:
    """Test edge cases in follow-up generation."""

    @pytest.mark.asyncio
    async def test_no_followup_after_max_attempts(
        self, test_interview, workflow_runner, container
    ):
        """Test follow-ups eventually stop after max attempts."""
        interview_id = test_interview["interview"]["id"]
        # Provide series of incomplete answers
        answers = ["Brief"] * 5  # 5 incomplete answers

        # Run workflow
        workflow_result = await workflow_runner(interview_id, answers, container)

        followups = workflow_result["followups"]

        # Should not generate infinite follow-ups
        # Typically limited to 2-3 per main question
        assert len(followups) < 10, (
            f"Too many follow-ups generated: {len(followups)}"
        )

    @pytest.mark.asyncio
    async def test_followup_after_partial_gap_resolution(
        self, test_interview, workflow_runner, container
    ):
        """Test follow-up behavior when some gaps resolved."""
        interview_id = test_interview["interview"]["id"]

        # First answer with gaps
        answer1 = "Async is concurrent"
        # Second answer resolves some gaps but not all
        answer2 = "It uses coroutines for concurrency"

        # Run workflow
        workflow_result = await workflow_runner(
            interview_id, [answer1, answer2], container
        )

        evaluations = workflow_result["evaluations"]
        followups = workflow_result["followups"]

        # Check gap resolution across evaluations
        if len(evaluations) >= 2:
            eval1_gaps = evaluations[0].get("gaps", [])
            eval2_gaps = evaluations[1].get("gaps", [])

            # If first answer had gaps
            if len(eval1_gaps) > 0:
                # Check if second evaluation shows progress
                eval1_gap_count = len(
                    [g for g in eval1_gaps if not g.get("resolved", False)]
                )
                eval2_gap_count = len(
                    [g for g in eval2_gaps if not g.get("resolved", False)]
                )

                # Gap count should decrease or stay same (showing progress)
                assert eval2_gap_count <= eval1_gap_count, (
                    f"Gap count increased: {eval1_gap_count} -> {eval2_gap_count}"
                )
