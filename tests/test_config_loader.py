# tests/test_config_loader.py
# Tests for services/config_loader.py (Stage 2).
# Covers: each file loads and returns the correct type; spot-check values;
# missing file raises; malformed YAML raises; missing required key raises.

import textwrap

import pytest

from schemas.room_taxonomy import RoomTaxonomy
from services.config_loader import (
    CategorySpecRules,
    FreshnessPolicies,
    StyleProfilesConfig,
    load_category_spec_rules,
    load_freshness_policies,
    load_room_taxonomy,
    load_style_profiles,
)

# ---------------------------------------------------------------------------
# load_room_taxonomy
# ---------------------------------------------------------------------------

class TestLoadRoomTaxonomy:
    def test_returns_room_taxonomy(self):
        result = load_room_taxonomy()
        assert isinstance(result, RoomTaxonomy)

    def test_version(self):
        result = load_room_taxonomy()
        assert result.version == 2

    def test_item_count(self):
        result = load_room_taxonomy()
        assert len(result.items) >= 20  # v2 has 30+ items

    def test_item_ids_present(self):
        result = load_room_taxonomy()
        ids = result.item_ids()
        assert "wall_art" in ids
        assert "bed_frame" in ids
        assert "sofa" in ids
        assert "mattress" in ids  # new in v2

    def test_slot_ids_alias(self):
        """slot_ids() is a backward-compat alias for item_ids()."""
        result = load_room_taxonomy()
        assert result.slot_ids() == result.item_ids()

    def test_item_by_id_fields(self):
        result = load_room_taxonomy()
        bed_frame = result.item_by_id("bed_frame")
        assert "bed_size" in bed_frame.required_specs

    def test_room_presets_exist(self):
        result = load_room_taxonomy()
        assert "bedroom" in result.room_presets
        assert "living_room" in result.room_presets

    def test_bedroom_preset_groups(self):
        result = load_room_taxonomy()
        bedroom = result.room_presets["bedroom"]
        assert "bed" in bedroom.groups
        assert "lighting" in bedroom.groups
        assert "bed_frame" in bedroom.groups["bed"].items

    def test_bedroom_required_items(self):
        result = load_room_taxonomy()
        bedroom = result.room_presets["bedroom"]
        required = bedroom.required_items()
        assert "bed_frame" in required
        assert "mattress" in required
        assert "rug" in required

    def test_flatten_weights_sums_to_one(self):
        result = load_room_taxonomy()
        bedroom = result.room_presets["bedroom"]
        weights = bedroom.flatten_weights()
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_budget_rules(self):
        result = load_room_taxonomy()
        assert result.budget_rules.min_slot_dollars == pytest.approx(15.0)
        assert result.budget_rules.max_slot_share == pytest.approx(0.40)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="not found"):
            load_room_taxonomy(path=tmp_path / "nonexistent.yaml")

    def test_malformed_yaml_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("items: [{\n  unclosed")
        with pytest.raises(ValueError, match="Malformed YAML"):
            load_room_taxonomy(path=bad)

    def test_missing_required_key_raises(self, tmp_path):
        # Missing 'version' — Pydantic should reject
        no_version = tmp_path / "no_version.yaml"
        no_version.write_text(textwrap.dedent("""\
            items: {}
            room_presets: {}
            budget_rules:
              min_slot_dollars: 15.0
              max_slot_share: 0.40
        """))
        with pytest.raises(ValueError):
            load_room_taxonomy(path=no_version)


# ---------------------------------------------------------------------------
# load_style_profiles
# ---------------------------------------------------------------------------

class TestLoadStyleProfiles:
    def test_returns_style_profiles_config(self):
        result = load_style_profiles()
        assert isinstance(result, StyleProfilesConfig)

    def test_version(self):
        result = load_style_profiles()
        assert result.version == 1

    def test_profile_count(self):
        result = load_style_profiles()
        assert len(result.profiles) == 5

    def test_warm_minimalist_present(self):
        result = load_style_profiles()
        ids = [p.id for p in result.profiles]
        assert "warm_minimalist" in ids

    def test_warm_minimalist_fields(self):
        result = load_style_profiles()
        profile = next(p for p in result.profiles if p.id == "warm_minimalist")
        assert profile.display_name == "Warm Minimalist"
        assert "natural wood" in profile.keywords
        assert "cream" in profile.color_palette

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_style_profiles(path=tmp_path / "nonexistent.yaml")

    def test_malformed_yaml_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("profiles: [{\n  unclosed")
        with pytest.raises(ValueError, match="Malformed YAML"):
            load_style_profiles(path=bad)

    def test_missing_required_key_raises(self, tmp_path):
        # Profile entry missing 'id'
        no_id = tmp_path / "no_id.yaml"
        no_id.write_text(textwrap.dedent("""\
            version: 1
            profiles:
              - display_name: Test
                keywords: [a]
                color_palette: [b]
                mood: calm
        """))
        with pytest.raises(ValueError):
            load_style_profiles(path=no_id)


# ---------------------------------------------------------------------------
# load_category_spec_rules
# ---------------------------------------------------------------------------

class TestLoadCategorySpecRules:
    def test_returns_category_spec_rules(self):
        result = load_category_spec_rules()
        assert isinstance(result, CategorySpecRules)

    def test_version(self):
        result = load_category_spec_rules()
        assert result.version == 1

    def test_bedding_required_specs(self):
        result = load_category_spec_rules()
        assert "bed_size" in result.slots["bedding"].required

    def test_bedding_valid_bed_size(self):
        result = load_category_spec_rules()
        assert "queen" in result.slots["bedding"].valid_bed_size

    def test_tv_required_specs(self):
        result = load_category_spec_rules()
        assert "screen_size" in result.slots["tv"].required

    def test_wall_art_no_required(self):
        result = load_category_spec_rules()
        assert result.slots["wall_art"].required == []

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_category_spec_rules(path=tmp_path / "nonexistent.yaml")

    def test_malformed_yaml_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("bedding: [{\n  unclosed")
        with pytest.raises(ValueError, match="Malformed YAML"):
            load_category_spec_rules(path=bad)

    def test_missing_version_raises(self, tmp_path):
        no_version = tmp_path / "no_version.yaml"
        no_version.write_text(textwrap.dedent("""\
            bedding:
              required: [bed_size]
        """))
        with pytest.raises(ValueError, match="version"):
            load_category_spec_rules(path=no_version)


# ---------------------------------------------------------------------------
# load_freshness_policies
# ---------------------------------------------------------------------------

class TestLoadFreshnessPolicies:
    def test_returns_freshness_policies(self):
        result = load_freshness_policies()
        assert isinstance(result, FreshnessPolicies)

    def test_version(self):
        result = load_freshness_policies()
        assert result.version == 1

    def test_price_freshness_hours(self):
        result = load_freshness_policies()
        assert result.price_freshness_hours == 24

    def test_link_check_on_display(self):
        result = load_freshness_policies()
        assert result.link_check_on_display is True

    def test_refresh_cron(self):
        result = load_freshness_policies()
        assert result.refresh_cron == "0 */6 * * *"

    def test_stale_design_warn_hours(self):
        result = load_freshness_policies()
        assert result.stale_design_warn_hours == 168

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_freshness_policies(path=tmp_path / "nonexistent.yaml")

    def test_malformed_yaml_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("price_freshness_hours: [{\n  unclosed")
        with pytest.raises(ValueError, match="Malformed YAML"):
            load_freshness_policies(path=bad)

    def test_missing_required_key_raises(self, tmp_path):
        # Missing price_freshness_hours
        incomplete = tmp_path / "incomplete.yaml"
        incomplete.write_text(textwrap.dedent("""\
            version: 1
            link_check_on_display: true
            refresh_cron: "0 */6 * * *"
            stale_design_warn_hours: 168
        """))
        with pytest.raises(ValueError):
            load_freshness_policies(path=incomplete)
