from gpu_gateway.health import heartbeat_age, heartbeat_is_fresh, heartbeat_is_stale


def test_heartbeat_threshold_is_shared_and_inclusive_for_recovery():
    now = 1_800_000_000

    assert heartbeat_age(now, now - 14) == 14
    assert heartbeat_is_fresh(now, now - 14)
    assert not heartbeat_is_stale(now, now - 14)

    assert heartbeat_age(now, now - 15) == 15
    assert not heartbeat_is_fresh(now, now - 15)
    assert heartbeat_is_stale(now, now - 15)


def test_heartbeat_future_skew_is_fresh_but_missing_or_invalid_is_not():
    now = 1_800_000_000

    assert heartbeat_age(now, now + 5) == -5
    assert heartbeat_is_fresh(now, now + 5)
    assert not heartbeat_is_fresh(now, now + 6)
    assert heartbeat_age(now, 0) is None
    assert not heartbeat_is_fresh(now, None)
    assert not heartbeat_is_stale(now, None)
