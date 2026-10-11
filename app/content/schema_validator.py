"""Missing schema_validator stub referenced by pipeline."""
from __future__ import annotations
from app.content.schemas import ScriptSchema


def validate_script_data(data: dict) -> ScriptSchema:
    return ScriptSchema.model_validate(data)
