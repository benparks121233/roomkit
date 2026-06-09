# validators/spec_rules.py
# Owns: ensuring per-slot required specs are present on the chosen product.
# Spec requirements come from context/category_spec_rules.yaml.
# e.g. bedding needs bed_size; TV needs screen_size; rug needs dimensions.
# Stage 8: implement.


def validate_specs(product, slot_id: str, spec_rules: dict) -> tuple[bool, str | None]:
    """Return (True, None) if product satisfies all required specs for slot_id."""
    # Stage 8: check product.specs against spec_rules[slot_id]["required"].
    raise NotImplementedError("Stage 8")
