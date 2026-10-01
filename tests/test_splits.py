"""Guards for reproducible, disjoint dataset splits."""
import pandas as pd

from aerotwin.simulator.generate_dataset import _fault_split, _healthy_split


def test_fault_split_is_reproducible():
    a_df, a_log = _fault_split("x", [8], 1, seed_base=5)
    b_df, b_log = _fault_split("x", [8], 1, seed_base=5)
    pd.testing.assert_frame_equal(a_log, b_log)
    pd.testing.assert_frame_equal(a_df.reset_index(drop=True), b_df.reset_index(drop=True))


def test_every_fault_flight_has_its_own_seed():
    _, log = _fault_split("x", [8, 9], 2, seed_base=5)
    assert log["seed"].is_unique


def test_split_seed_blocks_are_disjoint():
    # seed = base * 100_000 + airframe * 1000 + ... ; bases 1-5 never overlap
    blocks = {base: set(range(base * 100_000, (base + 1) * 100_000)) for base in range(1, 6)}
    _, val_log = _fault_split("v", [11], 1, seed_base=4)
    _, test_log = _fault_split("t", [8], 1, seed_base=5)
    assert set(val_log["seed"]) <= blocks[4] and set(test_log["seed"]) <= blocks[5]


def test_healthy_split_is_reproducible():
    a = _healthy_split("t", [8], [0], "hot_weather", seed_base=3)
    b = _healthy_split("t", [8], [0], "hot_weather", seed_base=3)
    pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True))
