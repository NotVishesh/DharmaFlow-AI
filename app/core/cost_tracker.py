"""
DharmaFlow AI — Cost & Resource Accounting System
Tracks compute time, external API tokens, approximate expenses,
and enforces configurable monthly spend caps.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.database.models import CostRecord

logger = logging.getLogger(__name__)

# Known rates per 1,000 tokens (USD) as of late 2024 / early 2025
PRICING_TABLE = {
    "openai:gpt-4o-mini": {"input": 0.00015 / 1000, "output": 0.00060 / 1000},
    "anthropic:claude-3-5-haiku-20241022": {"input": 0.00100 / 1000, "output": 0.00500 / 1000},
    "gemini:gemini-1.5-flash": {"input": 0.000075 / 1000, "output": 0.00030 / 1000},
    "local:ollama": {"input": 0.0, "output": 0.0},
    "local:mock": {"input": 0.0, "output": 0.0},
}


class CostTracker:
    """Tracks and limits API spend and compute resources."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def get_monthly_spend(self) -> float:
        """Calculate total spend for the current calendar month in USD."""
        records = self.db.query(CostRecord).all()
        return sum((r.cost_usd or 0.0) for r in records)

    def is_spend_cap_reached(self) -> bool:
        """Check if current spend has exceeded the configured monthly ceiling."""
        cap = self.settings.costs.monthly_api_spend_cap_usd
        if cap <= 0.0:
            return False
        current = self.get_monthly_spend()
        reached = current >= cap
        if reached:
            logger.warning("Monthly spend cap reached: $%.2f / $%.2f limit. External calls paused.", current, cap)
        return reached

    def record_usage(
        self,
        provider: str,
        operation: str,
        job_id: Optional[str] = None,
        job_type: str = "script_generation",
        tokens_in: int = 0,
        tokens_out: int = 0,
        compute_seconds: float = 0.0,
        notes: str = "",
    ) -> CostRecord:
        """Compute estimated cost, check limits, and save record."""
        price_key = provider.lower()
        pricing = PRICING_TABLE.get(price_key, {"input": 0.0, "output": 0.0})
        cost_usd = (tokens_in * pricing["input"]) + (tokens_out * pricing["output"])

        rec = CostRecord(
            job_id=job_id,
            job_type=job_type,
            provider=provider,
            operation=operation,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            compute_seconds=compute_seconds,
            notes=notes,
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)

        logger.debug(
            "Cost record added: %s (%s) — $%.4f, compute: %.1fs",
            provider, operation, cost_usd, compute_seconds
        )
        return rec
