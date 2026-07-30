from __future__ import annotations

import pytest
from lineage_lifeboat.demo_guard import (
    DemoCapacityError,
    DemoConfirmationError,
    DemoMutationGuard,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_confirmation_is_one_time_operation_and_client_bound() -> None:
    clock = FakeClock()
    tokens = iter(("wrong-operation", "wrong-client", "valid"))
    guard = DemoMutationGuard(clock=clock, token_factory=lambda _size: next(tokens))

    wrong_operation, ttl = guard.issue_confirmation("judge-a", "outage")
    assert ttl == 120

    with pytest.raises(DemoConfirmationError):
        guard.begin_public("judge-a", "initialize", wrong_operation)

    wrong_client, _ = guard.issue_confirmation("judge-a", "outage")
    with pytest.raises(DemoConfirmationError):
        guard.begin_public("judge-b", "outage", wrong_client)

    valid, _ = guard.issue_confirmation("judge-a", "outage")
    guard.begin_public("judge-a", "outage", valid)
    guard.finish()

    with pytest.raises(DemoConfirmationError):
        guard.begin_public("judge-a", "outage", valid)


def test_public_mutations_are_single_flight_and_cooled_down() -> None:
    clock = FakeClock()
    tokens = iter(("first", "busy", "cooldown", "after"))
    guard = DemoMutationGuard(clock=clock, token_factory=lambda _size: next(tokens))

    first, _ = guard.issue_confirmation("judge-a", "execute")
    guard.begin_public("judge-a", "execute", first)

    busy, _ = guard.issue_confirmation("judge-b", "initialize")
    with pytest.raises(DemoCapacityError) as busy_error:
        guard.begin_public("judge-b", "initialize", busy)
    assert busy_error.value.retry_after_seconds == 1

    guard.finish()
    cooldown, _ = guard.issue_confirmation("judge-a", "outage")
    with pytest.raises(DemoCapacityError) as cooldown_error:
        guard.begin_public("judge-a", "outage", cooldown)
    assert cooldown_error.value.retry_after_seconds == 1

    clock.advance(1)
    after, _ = guard.issue_confirmation("judge-a", "outage")
    guard.begin_public("judge-a", "outage", after)
    guard.finish()


def test_confirmation_expires() -> None:
    clock = FakeClock()
    guard = DemoMutationGuard(clock=clock, token_factory=lambda _size: "short-lived")
    token, _ = guard.issue_confirmation("judge-a", "plan", ttl_seconds=5)
    clock.advance(5)

    with pytest.raises(DemoConfirmationError):
        guard.begin_public("judge-a", "plan", token)
