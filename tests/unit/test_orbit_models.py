from __future__ import annotations

from datetime import UTC, datetime

import pytest

from orbit.models import FeedbackRequest, RetrieveRequest, TimeRange


def test_time_range_requires_end_after_start() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2025, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError):
        TimeRange(start=start, end=end)


def test_feedback_request_outcome_range() -> None:
    with pytest.raises(ValueError):
        FeedbackRequest(memory_id="mem_1", helpful=True, outcome_value=2.0)


def test_retrieve_limit_bounds() -> None:
    with pytest.raises(ValueError):
        RetrieveRequest(query="hello", limit=101)
