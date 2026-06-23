"""Unit tests for TV-size dynamic entertainment reweight.

Pure math — no LLM calls, no API calls, no DB.  Validates that
_apply_tv_size_reweight() inflates entertainment correctly and caps
at 35%/45% to prevent room collapse.
"""

import pytest

from services.composition_service import (
    _apply_tv_size_reweight,
    _ENT_BASE_TOTAL,
    _ENT_MAX_SHARE,
    _ENT_MAX_SHARE_PRIORITY,
    _MOUNT_BASE_SHARE,
    _STAND_BASE_SHARE,
    _TV_PRICE_FLOORS,
)


def _make_weights() -> dict[str, float]:
    """Baseline living room weights (entertainment at 12%, rest fills to 1.0)."""
    return {
        "sofa": 0.33,
        "coffee_table": 0.078,
        "side_table": 0.042,
        "rug": 0.06,
        "wall_art": 0.036,
        "plants": 0.042,
        "floor_lamp": 0.032,
        "ceiling_light": 0.033,
        "curtains": 0.022,
        "throw_pillows": 0.011,
        "throw_blanket": 0.018,
        "armchair": 0.11,
        "bookshelf": 0.042,
        "tv": 0.06,
        "tv_stand": 0.042,
        "tv_mount": 0.018,
    }


class TestTvReweight:

    def test_no_reweight_when_budget_covers_floor(self):
        """High budget + small TV: default weights already fund it."""
        w = _make_weights()
        original = dict(w)
        result = _apply_tv_size_reweight(w, "small", 3000.0)
        assert result == original

    def test_unknown_screen_size_returns_unchanged(self):
        w = _make_weights()
        original = dict(w)
        result = _apply_tv_size_reweight(w, "jumbo", 1500.0)
        assert result == original

    def test_zero_budget_returns_unchanged(self):
        w = _make_weights()
        original = dict(w)
        result = _apply_tv_size_reweight(w, "large", 0)
        assert result == original

    @pytest.mark.parametrize("screen_size,floor", list(_TV_PRICE_FLOORS.items()))
    def test_tv_gets_at_least_floor_share(self, screen_size: str, floor: float):
        """TV slot weight must fund at least the price floor."""
        budget = 1500.0
        w = _make_weights()
        result = _apply_tv_size_reweight(w, screen_size, budget)
        tv_dollars = result["tv"] * budget
        if floor / budget + _STAND_BASE_SHARE + _MOUNT_BASE_SHARE > _ENT_MAX_SHARE:
            # Capped — TV gets whatever's left after cap minus stand/mount
            assert tv_dollars <= budget * _ENT_MAX_SHARE
        else:
            assert tv_dollars >= floor - 0.01  # float tolerance

    def test_stand_mount_stay_at_baseline(self):
        """tv_stand and tv_mount keep baseline dollar shares regardless of TV size."""
        w = _make_weights()
        result = _apply_tv_size_reweight(w, "xl", 1500.0)
        assert abs(result["tv_stand"] - _STAND_BASE_SHARE) < 1e-9
        assert abs(result["tv_mount"] - _MOUNT_BASE_SHARE) < 1e-9

    def test_cap_at_35_percent_normal(self):
        """Entertainment share never exceeds 35% without tv_priority."""
        w = _make_weights()
        result = _apply_tv_size_reweight(w, "xl", 800.0)
        ent_share = result["tv"] + result["tv_stand"] + result["tv_mount"]
        assert ent_share <= _ENT_MAX_SHARE + 1e-9

    def test_cap_at_45_percent_priority(self):
        """With tv_priority, cap rises to 45%."""
        w = _make_weights()
        result = _apply_tv_size_reweight(w, "xl", 800.0, tv_priority=True)
        ent_share = result["tv"] + result["tv_stand"] + result["tv_mount"]
        assert ent_share <= _ENT_MAX_SHARE_PRIORITY + 1e-9
        # Should be higher than without priority
        w2 = _make_weights()
        result_normal = _apply_tv_size_reweight(w2, "xl", 800.0)
        ent_normal = result_normal["tv"] + result_normal["tv_stand"] + result_normal["tv_mount"]
        assert ent_share >= ent_normal

    def test_non_ent_slots_scale_proportionally(self):
        """Non-entertainment slots shrink proportionally, preserving relative ratios."""
        w = _make_weights()
        result = _apply_tv_size_reweight(w, "large", 1200.0)

        non_ent_before = {k: v for k, v in w.items() if k not in {"tv", "tv_stand", "tv_mount"}}
        non_ent_after = {k: v for k, v in result.items() if k not in {"tv", "tv_stand", "tv_mount"}}

        # Ratios between non-ent slots should be preserved
        slots = list(non_ent_before.keys())
        for i in range(len(slots) - 1):
            a, b = slots[i], slots[i + 1]
            if non_ent_before[b] > 0 and non_ent_after[b] > 0:
                ratio_before = non_ent_before[a] / non_ent_before[b]
                ratio_after = non_ent_after[a] / non_ent_after[b]
                assert abs(ratio_before - ratio_after) < 1e-6

    def test_weights_sum_to_one(self):
        """Total weights must still sum to ~1.0 after reweight."""
        for size in _TV_PRICE_FLOORS:
            w = _make_weights()
            result = _apply_tv_size_reweight(w, size, 1200.0)
            total = sum(result.values())
            assert abs(total - 1.0) < 1e-6, f"size={size}, total={total}"

    def test_edge_case_budget_below_floor(self):
        """Budget so low that TV floor exceeds cap — should cap, not crash."""
        w = _make_weights()
        # $550 XL TV on $600 budget: floor share = 550/600 = 91.7%, way above cap
        result = _apply_tv_size_reweight(w, "xl", 600.0)
        ent_share = result["tv"] + result["tv_stand"] + result["tv_mount"]
        assert ent_share <= _ENT_MAX_SHARE + 1e-9
        assert sum(result.values()) > 0  # didn't produce garbage
