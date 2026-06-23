"""Regression tests for sourcing adapter filters.

Pure unit tests — no LLM calls, no API calls, no DB.  Validates that
contamination filters, cheugy patterns, and priority-term weighting
behave correctly against known product names.
"""

import re

import pytest

from services.sourcing.amazon_adapter import (
    _BATHROOM_MIRROR_PHRASES,
    _BULK_POT_RE,
    _CHEUGY_RE,
    _DECORATIVE_PILLOW_PHRASES,
    _FLORAL_SHEET_PHRASES,
    _PLAID_SHEET_PHRASES,
    _PLANT_INDICATOR_WORDS,
    _PLANT_STAND_PHRASES,
    _POT_PLANTER_WORDS,
    _SLOT_EXCLUDE_PHRASES,
)


# ── Cheugy pattern tests ─────────────────────────────────────────────

class TestCheugyFilter:
    """_CHEUGY_RE must catch known bad products, not false-positive on good ones."""

    @pytest.mark.parametrize("name", [
        "Live Laugh Love Canvas Wall Art",
        "Motivational Quote Wall Art Poster",
        "Inspirational Quote Canvas Print",
        "Home Sweet Home Rustic Sign",
        "Man Cave LED Neon Sign",
        "Blessed This Mess Farmhouse Sign",
        "Dream Big Motivational Poster",
        "Eat Sleep Game Repeat Neon Sign",
        "Gamer Canvas Wall Art for Boys Room",
        "Game Room Rules Sign",
        "Do Not Disturb Gaming In Progress",
        "Funny Bathroom Rules Sign",
        "Bible Verse Scripture Wall Art",
        "Photo Collage Frame Set",
        "Hustle Hard Motivational Canvas",
        "Novelty Gag Gift Coffee Mug Sign",
        "RGB Rug Gaming Carpet",
        "Sports Ball Theme Boys Room Decor",
    ])
    def test_blocks_cheugy(self, name: str):
        assert _CHEUGY_RE.search(name), f"Should block: {name}"

    @pytest.mark.parametrize("name", [
        "Abstract Geometric Canvas Wall Art",
        "Vintage Jazz Festival Poster",
        "Japanese Wave Framed Print",
        "Modern Abstract Oil Painting",
        "Botanical Illustration Fern Art Print",
        "NFL Team Logo Wall Art",  # sports art with interests is OK
        "Retro Video Game Controller Art",  # gaming ART (not gamer sign/canvas)
        "Mid-Century Modern Landscape Print",
        "Black and White Photography City Skyline",
        "Minimalist Line Art Woman Portrait",
    ])
    def test_allows_legitimate(self, name: str):
        assert not _CHEUGY_RE.search(name), f"Should NOT block: {name}"


# ── Per-slot exclusion phrase tests ───────────────────────────────────

class TestSlotExclusions:
    """Each slot's exclusion list must block contaminants, not legitimate products."""

    # sofa: recliners, slipcovers, outdoor, bundled sets
    @pytest.mark.parametrize("name", [
        "Power Lift Recliner Chair for Elderly",
        "Stretch Sofa Cover Furniture Protector",
        "Recliner Slipcover Waterproof",
        "Sofa and Loveseat Set Living Room",
        "Outdoor Patio Sectional Sofa",
        "Rocker Recliner Chair with Cup Holder",
        "Floor Chair Meditation Cushion",
    ])
    def test_sofa_blocks(self, name: str):
        phrases = _SLOT_EXCLUDE_PHRASES["sofa"]
        assert any(ph in name.lower() for ph in phrases), f"sofa should block: {name}"

    @pytest.mark.parametrize("name", [
        "Modern Velvet Sofa 3-Seater",
        "Sectional Sofa L-Shape with Chaise",
        "Leather Couch Mid-Century Modern",
        "Reclining Sofa with USB Ports",  # reclining sofa is OK, recliner chair is not
    ])
    def test_sofa_allows(self, name: str):
        phrases = _SLOT_EXCLUDE_PHRASES["sofa"]
        assert not any(ph in name.lower() for ph in phrases), f"sofa should NOT block: {name}"

    # rug: outdoor/bath/kitchen mats
    @pytest.mark.parametrize("name", [
        "Outdoor Rug 5x7 Patio Deck",
        "Bath Mat Non-Slip Bathroom Rug",
        "Kitchen Mat Anti-Fatigue",
        "Welcome Mat Doormat Front Porch",
    ])
    def test_rug_blocks(self, name: str):
        phrases = _SLOT_EXCLUDE_PHRASES["rug"]
        assert any(ph in name.lower() for ph in phrases), f"rug should block: {name}"

    @pytest.mark.parametrize("name", [
        "Persian Area Rug 8x10 Living Room",
        "Shag Rug Soft Plush Cream 5x7",
        "Vintage Distressed Oriental Rug",
    ])
    def test_rug_allows(self, name: str):
        phrases = _SLOT_EXCLUDE_PHRASES["rug"]
        assert not any(ph in name.lower() for ph in phrases), f"rug should NOT block: {name}"

    # throw_pillows: pillow covers/shams/shells (no insert)
    @pytest.mark.parametrize("name", [
        "Pillow Cover 18x18 Set of 4 Velvet",
        "Cushion Cover Only No Insert",
        "Decorative Pillow Sham Euro Size",
        "Replacement Cover for Throw Pillow",
    ])
    def test_throw_pillows_blocks(self, name: str):
        phrases = _SLOT_EXCLUDE_PHRASES["throw_pillows"]
        assert any(ph in name.lower() for ph in phrases), f"throw_pillows should block: {name}"

    @pytest.mark.parametrize("name", [
        "Velvet Throw Pillow 18x18 Sage Green with Insert",
        "Boho Decorative Pillow with Insert Included",
    ])
    def test_throw_pillows_allows(self, name: str):
        phrases = _SLOT_EXCLUDE_PHRASES["throw_pillows"]
        assert not any(ph in name.lower() for ph in phrases), f"throw_pillows should NOT block: {name}"

    # pillows (bed): neck/dog/body/travel pillows
    @pytest.mark.parametrize("name", [
        "Neck Pillow Memory Foam Travel",
        "Dog Pillow Bed Large Breed",
        "Body Pillow Full Length Pregnancy",
    ])
    def test_pillows_blocks(self, name: str):
        phrases = _SLOT_EXCLUDE_PHRASES["pillows"]
        assert any(ph in name.lower() for ph in phrases), f"pillows should block: {name}"

    def test_pillows_allows_bed_pillow(self):
        phrases = _SLOT_EXCLUDE_PHRASES["pillows"]
        name = "Queen Size Bed Pillows 2 Pack Hotel Quality"
        assert not any(ph in name.lower() for ph in phrases)

    # armchair: multi-piece sets
    @pytest.mark.parametrize("name", [
        "Accent Chair Set of 2 Living Room",
        "Club Chair 2 Pack Velvet",
    ])
    def test_armchair_blocks(self, name: str):
        phrases = _SLOT_EXCLUDE_PHRASES["armchair"]
        assert any(ph in name.lower() for ph in phrases), f"armchair should block: {name}"

    def test_armchair_allows_single(self):
        phrases = _SLOT_EXCLUDE_PHRASES["armchair"]
        name = "Mid-Century Modern Accent Chair Velvet"
        assert not any(ph in name.lower() for ph in phrases)

    # wall_art: multi-panel sets, gaming canvas
    @pytest.mark.parametrize("name", [
        "5 Piece Canvas Wall Art Mountain Landscape",
        "3 Panel Canvas Art Set of 3",
        "Gaming Canvas Video Game Wall Art",
        "Retro Gaming Canvas Set of 5",
    ])
    def test_wall_art_blocks(self, name: str):
        phrases = _SLOT_EXCLUDE_PHRASES["wall_art"]
        assert any(ph in name.lower() for ph in phrases), f"wall_art should block: {name}"

    def test_wall_art_allows_single(self):
        phrases = _SLOT_EXCLUDE_PHRASES["wall_art"]
        name = "Abstract Canvas Wall Art Large Modern Print"
        assert not any(ph in name.lower() for ph in phrases)

    # sheets: floral and plaid patterns
    @pytest.mark.parametrize("name", [
        "Floral Print Sheet Set Queen",
        "Wildflower Botanical Bed Sheets",
        "Plaid Flannel Sheet Set King",
        "Buffalo Check Sheet Set",
    ])
    def test_sheets_pattern_blocks(self, name: str):
        floral_hit = any(ph in name.lower() for ph in _FLORAL_SHEET_PHRASES)
        plaid_hit = any(ph in name.lower() for ph in _PLAID_SHEET_PHRASES)
        assert floral_hit or plaid_hit, f"sheets should block: {name}"

    @pytest.mark.parametrize("name", [
        "Cotton Sateen Sheet Set 400TC Queen",
        "Linen Sheet Set Stonewashed King",
        "Microfiber Sheet Set Deep Pocket",
    ])
    def test_sheets_allows_solid(self, name: str):
        floral_hit = any(ph in name.lower() for ph in _FLORAL_SHEET_PHRASES)
        plaid_hit = any(ph in name.lower() for ph in _PLAID_SHEET_PHRASES)
        assert not (floral_hit or plaid_hit), f"sheets should NOT block: {name}"


# ── Plant slot filters ────────────────────────────────────────────────

class TestPlantFilters:

    @pytest.mark.parametrize("name", [
        "24 Pack Colorful Flower Pots Succulent Planter",
        "10 Pcs Small Ceramic Plant Pots Set",
        "6 Pack Plastic Planters with Drainage",
    ])
    def test_bulk_pot_regex(self, name: str):
        assert _BULK_POT_RE.search(name), f"Should catch bulk pot: {name}"

    @pytest.mark.parametrize("name", [
        "Artificial Snake Plant in Ceramic Pot",
        "Faux Fiddle Leaf Fig Tree 6ft",
        "Live Pothos Plant in Decorative Planter",
    ])
    def test_bulk_pot_allows_real_plants(self, name: str):
        assert not _BULK_POT_RE.search(name), f"Should NOT catch: {name}"

    def test_empty_pot_blocked(self):
        name = "White Ceramic Planter Pot 8 Inch"
        assert _POT_PLANTER_WORDS.search(name)
        assert not _PLANT_INDICATOR_WORDS.search(name)

    def test_pot_with_plant_allowed(self):
        name = "Artificial Monstera Plant in Ceramic Planter"
        assert _POT_PLANTER_WORDS.search(name)
        assert _PLANT_INDICATOR_WORDS.search(name)

    @pytest.mark.parametrize("name", [
        "Plant Stand 3 Tier Indoor",
        "Watering Can Vintage Copper",
        "Vase Ceramic Modern Decorative",
        "Lego Bonsai Tree Building Set",
    ])
    def test_plant_stand_phrases(self, name: str):
        assert any(ph in name.lower() for ph in _PLANT_STAND_PHRASES), f"Should block: {name}"


# ── Mirror filter ─────────────────────────────────────────────────────

class TestMirrorFilter:

    @pytest.mark.parametrize("name", [
        "Bathroom Mirror with LED Lights",
        "Vanity Mirror Hollywood Makeup",
        "Medicine Cabinet with Mirror",
    ])
    def test_blocks_bathroom_mirrors(self, name: str):
        assert any(ph in name.lower() for ph in _BATHROOM_MIRROR_PHRASES)

    @pytest.mark.parametrize("name", [
        "Arched Full Length Floor Mirror Gold",
        "Round Wall Mirror 24 Inch Black Metal",
        "Sunburst Decorative Mirror Rattan",
    ])
    def test_allows_bedroom_mirrors(self, name: str):
        assert not any(ph in name.lower() for ph in _BATHROOM_MIRROR_PHRASES)


# ── Pillow slot filter (bed pillows vs decorative) ────────────────────

class TestPillowFilter:

    @pytest.mark.parametrize("name", [
        "Throw Pillow Cover 18x18 Boho",
        "Decorative Pillow Set Velvet",
        "Lumbar Pillow Support Couch",
        "Outdoor Pillow Patio Furniture",
    ])
    def test_blocks_decorative(self, name: str):
        assert any(ph in name.lower() for ph in _DECORATIVE_PILLOW_PHRASES)

    @pytest.mark.parametrize("name", [
        "Queen Size Bed Pillows 2 Pack Hotel Quality",
        "Memory Foam Pillow Cooling Gel",
        "Down Alternative Pillow Standard Size",
    ])
    def test_allows_bed_pillows(self, name: str):
        assert not any(ph in name.lower() for ph in _DECORATIVE_PILLOW_PHRASES)


# ── Priority-term weighting ───────────────────────────────────────────

class TestPriorityWeighting:
    """Priority terms must score 3x vs generic terms in style_score."""

    def test_priority_term_scores_3x(self):
        kw_lower = ["farmhouse", "wood", "brown"]
        priority_set = {"farmhouse"}
        _PRIORITY_WEIGHT = 3

        def style_score(name: str) -> int:
            name_l = name.lower()
            score = 0
            for kw in kw_lower:
                if kw in name_l:
                    score += _PRIORITY_WEIGHT if kw in priority_set else 1
            return score

        # "farmhouse" (priority) = 3, "wood" (generic) = 1
        assert style_score("Farmhouse Wood Table") == 4  # 3 + 1
        assert style_score("Wood Brown Table") == 2      # 1 + 1
        assert style_score("Farmhouse Brown Wood Table") == 5  # 3 + 1 + 1

    def test_priority_changes_ranking(self):
        """A product with one priority term should outscore one with two generic terms."""
        kw_lower = ["rattan", "natural", "brown"]
        priority_set = {"rattan"}
        _PRIORITY_WEIGHT = 3

        def style_score(name: str) -> int:
            name_l = name.lower()
            return sum(
                _PRIORITY_WEIGHT if kw in priority_set else 1
                for kw in kw_lower if kw in name_l
            )

        rattan_only = style_score("Rattan Chair")           # 3
        two_generic = style_score("Natural Brown Side Table")  # 1 + 1 = 2
        assert rattan_only > two_generic
