# services/config_loader.py
# Single entry point for all context/ YAML config files.
# Each loader validates on load and raises loudly on missing file,
# malformed YAML, or missing required keys. Services read from the
# returned Pydantic objects, never from raw dicts.

from pathlib import Path

import yaml
from pydantic import BaseModel

from schemas.room_taxonomy import RoomTaxonomy

_CONTEXT_DIR = Path(__file__).parent.parent / "context"


# ---------------------------------------------------------------------------
# Style profiles
# ---------------------------------------------------------------------------

class StyleProfileEntry(BaseModel):
    id: str
    display_name: str
    keywords: list[str]
    sourcing_terms: list[str] = []  # Product-name-friendly terms for adapter scoring
    color_palette: list[str]
    mood: str


class StyleProfilesConfig(BaseModel):
    version: int
    profiles: list[StyleProfileEntry]


# ---------------------------------------------------------------------------
# Category spec rules
# ---------------------------------------------------------------------------

class SlotSpecRule(BaseModel):
    required: list[str]
    valid_bed_size: list[str] | None = None


class CategorySpecRules(BaseModel):
    version: int
    slots: dict[str, SlotSpecRule]


# ---------------------------------------------------------------------------
# Freshness policies
# ---------------------------------------------------------------------------

class FreshnessPolicies(BaseModel):
    version: int
    price_freshness_hours: int
    link_check_on_display: bool
    refresh_cron: str
    stale_design_warn_hours: int


# ---------------------------------------------------------------------------
# Budget policies
# ---------------------------------------------------------------------------

class BudgetPolicies(BaseModel):
    version: int
    minimum_room_multiplier: float


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    """Read and parse a YAML file; raise clearly on any failure."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    try:
        with path.open() as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping at top level in {path}")
    return data


def load_room_taxonomy(path: Path | None = None) -> RoomTaxonomy:
    """Load and validate context/slot_taxonomy.yaml (v2 grouped format)."""
    path = path or _CONTEXT_DIR / "slot_taxonomy.yaml"
    data = _load_yaml(path)
    try:
        return RoomTaxonomy.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Invalid slot taxonomy in {path}: {exc}") from exc


def load_style_profiles(path: Path | None = None) -> StyleProfilesConfig:
    """Load and validate context/style_profiles.yaml."""
    path = path or _CONTEXT_DIR / "style_profiles.yaml"
    data = _load_yaml(path)
    try:
        return StyleProfilesConfig.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Invalid style profiles in {path}: {exc}") from exc


def load_category_spec_rules(path: Path | None = None) -> CategorySpecRules:
    """Load and validate context/category_spec_rules.yaml.

    The YAML uses a flat structure where slot IDs are top-level keys alongside
    'version'. We extract version separately and build the slots dict from the
    remaining keys.
    """
    path = path or _CONTEXT_DIR / "category_spec_rules.yaml"
    data = _load_yaml(path)
    if "version" not in data:
        raise ValueError(f"Missing required key 'version' in {path}")
    version = data["version"]
    slots_raw = {k: v for k, v in data.items() if k != "version"}
    try:
        return CategorySpecRules.model_validate({"version": version, "slots": slots_raw})
    except Exception as exc:
        raise ValueError(f"Invalid category spec rules in {path}: {exc}") from exc


def load_freshness_policies(path: Path | None = None) -> FreshnessPolicies:
    """Load and validate context/freshness_policies.yaml."""
    path = path or _CONTEXT_DIR / "freshness_policies.yaml"
    data = _load_yaml(path)
    try:
        return FreshnessPolicies.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Invalid freshness policies in {path}: {exc}") from exc


def load_budget_policies(path: Path | None = None) -> BudgetPolicies:
    """Load and validate context/budget_policies.yaml."""
    path = path or _CONTEXT_DIR / "budget_policies.yaml"
    data = _load_yaml(path)
    try:
        return BudgetPolicies.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Invalid budget policies in {path}: {exc}") from exc
