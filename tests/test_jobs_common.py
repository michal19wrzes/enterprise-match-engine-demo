from jobs_common import build_manual_entry_fingerprint, floor_2, round_2


def test_manual_entry_fingerprint_ignores_details_changes():
    first = build_manual_entry_fingerprint("T-1", "Missing mapping", "old details")
    second = build_manual_entry_fingerprint("T-1", "Missing mapping", "new details")
    assert first == second


def test_round_2_uses_half_up():
    assert round_2(1.235) == 1.24


def test_floor_2_truncates_down_to_two_decimals():
    assert floor_2(1.239) == 1.23
