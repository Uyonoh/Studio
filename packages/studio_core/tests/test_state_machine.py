"""Tests for the job state machine: transitions, terminal immutability, and property testing."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from studio_core.models import JobStatus
from studio_core.state_machine import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    JobStateMachine,
    can_transition,
)


@given(
    st.sampled_from(list(JobStatus)),
    st.sampled_from(list(JobStatus)),
)
def test_property_state_machine_transitions(from_state: JobStatus, to_state: JobStatus) -> None:
    """Hypothesis property test: transitions match ALLOWED_TRANSITIONS table precisely."""
    expected = to_state in ALLOWED_TRANSITIONS[from_state]
    assert can_transition(from_state, to_state) is expected


@given(st.sampled_from(list(TERMINAL_STATES)), st.sampled_from(list(JobStatus)))
def test_terminal_states_never_transition(terminal: JobStatus, target: JobStatus) -> None:
    """Terminal states (succeeded, failed, canceled) are strictly immutable."""
    assert can_transition(terminal, target) is False


@pytest.mark.asyncio
async def test_illegal_transition_raises_value_error() -> None:
    conn = AsyncMock()
    sm = JobStateMachine(conn)
    job_id = uuid4()

    with pytest.raises(ValueError, match="Illegal job status transition"):
        await sm.transition(job_id, JobStatus.SUCCEEDED, JobStatus.RUNNING)


@pytest.mark.asyncio
async def test_concurrency_guard_fails_returns_none() -> None:
    """If another worker already transitioned the job, guarded update returns None."""
    conn = AsyncMock()
    # Simulates row not found / status didn't match
    conn.fetchrow.return_value = None
    sm = JobStateMachine(conn)

    job_id = uuid4()
    result = await sm.transition(job_id, JobStatus.RUNNING, JobStatus.FINALIZING)
    assert result is None
    # No event should be appended if guard failed
    conn.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_concurrent_transition_exactly_one_succeeds() -> None:
    """Simulate two workers racing to transition running -> finalizing concurrently."""
    state = {"status": "running"}
    lock = asyncio.Lock()

    async def mock_fetchrow(query: str, *params: object) -> dict[str, object] | None:
        async with lock:
            # First caller gets to update
            if "WHERE id = $1 AND status = 'running'" in query:
                if state["status"] == "running":
                    state["status"] = "finalizing"
                    return {
                        "id": params[0],
                        "workspace_id": uuid4(),
                        "project_id": uuid4(),
                        "created_by": uuid4(),
                        "model_id": uuid4(),
                        "task_type": "text_to_image",
                        "status": "finalizing",
                        "params": "{}",
                        "attempt": 0,
                        "max_attempts": 3,
                        "cost_credits": 1,
                        "queued_at": datetime.now(UTC),
                    }
                return None
            if "INSERT INTO public.job_events" in query:
                return {
                    "id": 1,
                    "job_id": params[0],
                    "type": params[1],
                    "from_status": params[2],
                    "to_status": params[3],
                    "payload": None,
                    "created_at": datetime.now(UTC),
                }
            return None

    conn = AsyncMock()
    conn.fetchrow.side_effect = mock_fetchrow

    sm1 = JobStateMachine(conn)
    sm2 = JobStateMachine(conn)
    job_id = uuid4()

    res1, res2 = await asyncio.gather(
        sm1.transition(job_id, JobStatus.RUNNING, JobStatus.FINALIZING),
        sm2.transition(job_id, JobStatus.RUNNING, JobStatus.FINALIZING),
    )

    # Exactly one succeeded, one returned None
    succeeded_count = sum(1 for r in (res1, res2) if r is not None)
    assert succeeded_count == 1
    assert (res1 is None) != (res2 is None)
