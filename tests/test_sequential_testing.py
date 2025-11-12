import pytest

from metamorphic_guard.sequential_testing import (
    SequentialTestConfig,
    apply_sequential_correction,
)


def test_apply_sequential_correction_recomputes_interval():
    config = SequentialTestConfig(
        method="pocock",
        alpha=0.05,
        max_looks=5,
        look_number=2,
    )

    captured_alpha = {}

    def recompute_ci(new_alpha: float):
        captured_alpha["value"] = new_alpha
        return [-0.1, 0.25]

    original_ci = [0.0, 0.2]
    adjusted_ci, adjusted_alpha = apply_sequential_correction(
        original_ci,
        config,
        recompute_ci=recompute_ci,
    )

    expected_alpha = pytest.approx(0.01)  # 0.05 / 5
    assert adjusted_alpha == expected_alpha
    assert captured_alpha["value"] == expected_alpha
    assert adjusted_ci == [-0.1, 0.25]


def test_apply_sequential_correction_requires_recompute_callable():
    config = SequentialTestConfig(
        method="obrien-fleming",
        alpha=0.05,
        max_looks=3,
        look_number=1,
    )

    with pytest.raises(ValueError):
        apply_sequential_correction([0.0, 0.2], config)

