"""WebSocket message schema validation tests.

Tests that workflow path sends messages with identical structure to legacy path.
Focus: Message types, required fields, metadata completeness.
"""
import pytest
from uuid import UUID


class TestMessageSchemaParity:
    """Validate WebSocket message formats match between legacy and workflow."""

    @pytest.mark.asyncio
    async def test_question_message_schema(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test main question message has required fields."""
        interview_id = test_interview["interview"]["id"]
        answers = ["Async/await allows concurrent execution"]

        # Run both paths
        legacy_result = await legacy_runner(interview_id, answers, container)
        workflow_result = await workflow_runner(interview_id, answers, container)

        # Get first question message from each path
        legacy_questions = [
            msg for msg in legacy_result["messages"] if msg.get("type") == "question"
        ]
        workflow_questions = workflow_result["questions"]

        assert len(legacy_questions) > 0, "Legacy path sent no question messages"
        assert len(workflow_questions) > 0, "Workflow path sent no question messages"

        legacy_q = legacy_questions[0]
        workflow_q = workflow_questions[0]

        # Assert required fields present
        required_fields = {"type", "question_id", "text"}
        assert required_fields.issubset(
            legacy_q.keys()
        ), f"Legacy missing fields: {required_fields - legacy_q.keys()}"
        assert required_fields.issubset(
            workflow_q.keys()
        ), f"Workflow missing fields: {required_fields - workflow_q.keys()}"

        # Assert field types
        assert isinstance(legacy_q["text"], str)
        assert isinstance(workflow_q["text"], str)

        # Assert question_id is UUID-like
        assert isinstance(legacy_q["question_id"], (str, UUID))
        assert isinstance(workflow_q["question_id"], (str, UUID))

    @pytest.mark.asyncio
    async def test_followup_message_schema(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test follow-up question message has required metadata fields."""
        interview_id = test_interview["interview"]["id"]
        # Provide brief answer to trigger follow-up
        answers = ["Async is concurrent"]

        # Run both paths
        legacy_result = await legacy_runner(interview_id, answers, container)
        workflow_result = await workflow_runner(interview_id, answers, container)

        # Get follow-up messages
        legacy_followups = legacy_result["followups"]
        workflow_followups = workflow_result["followups"]

        # Only validate if both paths generated follow-ups
        if len(legacy_followups) > 0 and len(workflow_followups) > 0:
            legacy_fu = legacy_followups[0]
            workflow_fu = workflow_followups[0]

            # Assert follow-up specific fields
            followup_fields = {
                "type",
                "question_id",
                "parent_question_id",
                "text",
                "generated_reason",
            }

            assert followup_fields.issubset(
                legacy_fu.keys()
            ), f"Legacy follow-up missing: {followup_fields - legacy_fu.keys()}"
            assert followup_fields.issubset(
                workflow_fu.keys()
            ), f"Workflow follow-up missing: {followup_fields - workflow_fu.keys()}"

            # Assert message type is correct
            assert legacy_fu["type"] == "follow_up_question"
            assert workflow_fu["type"] == "follow_up_question"

            # Assert parent_question_id is present
            assert legacy_fu["parent_question_id"] is not None
            assert workflow_fu["parent_question_id"] is not None

            # Assert generated_reason is string
            assert isinstance(legacy_fu["generated_reason"], str)
            assert isinstance(workflow_fu["generated_reason"], str)

    @pytest.mark.asyncio
    async def test_evaluation_message_schema(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test evaluation message has required feedback fields."""
        interview_id = test_interview["interview"]["id"]
        answers = ["Async/await enables asynchronous programming using coroutines"]

        # Run both paths
        legacy_result = await legacy_runner(interview_id, answers, container)
        workflow_result = await workflow_runner(interview_id, answers, container)

        # Get evaluation messages
        legacy_evals = legacy_result["evaluations"]
        workflow_evals = workflow_result["evaluations"]

        assert len(legacy_evals) > 0, "Legacy sent no evaluation messages"
        assert len(workflow_evals) > 0, "Workflow sent no evaluation messages"

        legacy_eval = legacy_evals[0]
        workflow_eval = workflow_evals[0]

        # Assert required evaluation fields
        eval_fields = {"score", "feedback", "strengths", "weaknesses", "gaps"}

        assert eval_fields.issubset(
            legacy_eval.keys()
        ), f"Legacy eval missing: {eval_fields - legacy_eval.keys()}"
        assert eval_fields.issubset(
            workflow_eval.keys()
        ), f"Workflow eval missing: {eval_fields - workflow_eval.keys()}"

        # Assert field types
        assert isinstance(legacy_eval["score"], (int, float))
        assert isinstance(workflow_eval["score"], (int, float))

        assert isinstance(legacy_eval["feedback"], str)
        assert isinstance(workflow_eval["feedback"], str)

        assert isinstance(legacy_eval["strengths"], list)
        assert isinstance(workflow_eval["strengths"], list)

        assert isinstance(legacy_eval["weaknesses"], list)
        assert isinstance(workflow_eval["weaknesses"], list)

        assert isinstance(legacy_eval["gaps"], list)
        assert isinstance(workflow_eval["gaps"], list)

    @pytest.mark.asyncio
    async def test_tts_audio_present(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test TTS audio_data present in question messages."""
        interview_id = test_interview["interview"]["id"]
        answers = ["Test answer"]

        # Run both paths
        legacy_result = await legacy_runner(interview_id, answers, container)
        workflow_result = await workflow_runner(interview_id, answers, container)

        # Get question messages
        legacy_questions = [
            msg for msg in legacy_result["messages"] if msg.get("type") == "question"
        ]
        workflow_questions = workflow_result["questions"]

        # Check legacy has audio_data
        for question in legacy_questions:
            assert (
                "audio_data" in question
            ), "Legacy question missing audio_data field"
            # Audio may be None if TTS fails, but field should exist
            if question["audio_data"]:
                assert isinstance(question["audio_data"], str)

        # Check workflow has audio_data
        for question in workflow_questions:
            assert (
                "audio_data" in question
            ), "Workflow question missing audio_data field"
            if question["audio_data"]:
                assert isinstance(question["audio_data"], str)

    @pytest.mark.asyncio
    async def test_message_ordering(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test message sequences match between paths."""
        interview_id = test_interview["interview"]["id"]
        answers = ["Answer 1", "Answer 2"]

        # Run both paths
        legacy_result = await legacy_runner(interview_id, answers, container)
        workflow_result = await workflow_runner(interview_id, answers, container)

        # Extract message type sequences
        legacy_sequence = [msg["type"] for msg in legacy_result["messages"]]
        workflow_sequence = [
            result.get("type", "unknown") for result in workflow_result["results"]
        ]

        # Both should have evaluation after each answer
        assert (
            "evaluation" in legacy_sequence
        ), "Legacy missing evaluation in sequence"
        assert (
            "evaluation" in workflow_sequence
        ), "Workflow missing evaluation in sequence"

        # Count evaluations
        legacy_eval_count = legacy_sequence.count("evaluation")
        workflow_eval_count = workflow_sequence.count("evaluation")

        assert (
            legacy_eval_count == len(answers)
        ), f"Legacy eval count mismatch: {legacy_eval_count} != {len(answers)}"
        assert (
            workflow_eval_count == len(answers)
        ), f"Workflow eval count mismatch: {workflow_eval_count} != {len(answers)}"

    @pytest.mark.asyncio
    async def test_metadata_completeness(
        self, test_interview, legacy_runner, workflow_runner, container
    ):
        """Test all metadata fields present in both paths."""
        interview_id = test_interview["interview"]["id"]
        answers = ["Brief answer"]  # Trigger follow-up

        # Run both paths
        legacy_result = await legacy_runner(interview_id, answers, container)
        workflow_result = await workflow_runner(interview_id, answers, container)

        # Check if follow-ups generated
        if len(legacy_result["followups"]) > 0 and len(workflow_result["followups"]) > 0:
            legacy_fu = legacy_result["followups"][0]
            workflow_fu = workflow_result["followups"][0]

            # Metadata fields from Phase 2
            metadata_fields = {
                "parent_question_id",
                "generated_reason",
                "order_in_sequence",
            }

            # Legacy should have all metadata
            for field in metadata_fields:
                assert field in legacy_fu, f"Legacy follow-up missing {field}"

            # Workflow should have all metadata
            for field in metadata_fields:
                assert field in workflow_fu, f"Workflow follow-up missing {field}"

            # Validate order_in_sequence is integer
            if "order_in_sequence" in legacy_fu:
                assert isinstance(legacy_fu["order_in_sequence"], int)
            if "order_in_sequence" in workflow_fu:
                assert isinstance(workflow_fu["order_in_sequence"], int)


class TestMessageTypeDistinction:
    """Test that main questions and follow-ups have distinct message types."""

    @pytest.mark.asyncio
    async def test_main_question_type(
        self, test_interview, workflow_runner, container
    ):
        """Test main questions use 'question' type."""
        interview_id = test_interview["interview"]["id"]
        answers = ["Complete answer with all details"]

        workflow_result = await workflow_runner(interview_id, answers, container)
        questions = workflow_result["questions"]

        # First question should be main question
        if len(questions) > 0:
            first_q = questions[0]
            assert first_q["type"] == "question", (
                f"Main question has wrong type: {first_q['type']}"
            )

    @pytest.mark.asyncio
    async def test_followup_type_distinction(
        self, test_interview, workflow_runner, container
    ):
        """Test follow-up questions use 'follow_up_question' type."""
        interview_id = test_interview["interview"]["id"]
        answers = ["Brief"]  # Trigger follow-up

        workflow_result = await workflow_runner(interview_id, answers, container)
        followups = workflow_result["followups"]

        # If follow-up generated, check type
        if len(followups) > 0:
            fu = followups[0]
            assert fu["type"] == "follow_up_question", (
                f"Follow-up has wrong type: {fu['type']}"
            )
