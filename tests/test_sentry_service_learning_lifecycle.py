"""Core-owned lifecycle coverage for automatic household learning reviews."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

import anima_ha.learning_review_runner as learning_review_runner
from anima_ha.sentry_service import _start_learning_review_runner


def test_core_starts_one_learning_runner_for_the_shared_socket_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[SimpleNamespace, object, UUID, bool] | str] = []

    class FakeRunner:
        def __init__(
            self, core: SimpleNamespace, learning: object, household_id: UUID, *, reconcile: bool
        ) -> None:
            calls.append((core, learning, household_id, reconcile))

        def start(self) -> None:
            calls.append("started")

    monkeypatch.setattr(learning_review_runner, "LearningReviewRunner", FakeRunner)
    core = SimpleNamespace(learning_service=object())
    household_id = uuid4()

    runner = _start_learning_review_runner(core, household_id)

    assert isinstance(runner, FakeRunner)
    assert calls == [(core, core.learning_service, household_id, True), "started"]


def test_core_without_learning_service_does_not_create_a_scheduler() -> None:
    assert _start_learning_review_runner(SimpleNamespace(), uuid4()) is None
