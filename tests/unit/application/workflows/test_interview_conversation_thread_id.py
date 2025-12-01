from uuid import UUID

from src.application.workflows.interview_conversation_workflow import (
    InterviewConversationWorkflow,
)


def test_build_thread_id_is_deterministic():
    interview_id = UUID("12345678-1234-5678-9abc-def012345678")
    expected = "interview_12345678-1234-5678-9abc-def012345678"
    assert InterviewConversationWorkflow.build_thread_id(interview_id) == expected


