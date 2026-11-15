import logging
import psutil
from backend.db.models import HardwareTier

logger = logging.getLogger(__name__)

def detect_hardware_profile() -> dict:
    ram_bytes = psutil.virtual_memory().total
    ram_gb = round(ram_bytes / (1024 ** 3), 2)
    vram_gb = 0.0
    tier = HardwareTier.TIER_LOW

    # 1. Probe NVIDIA GPU via pynvml
    try:
        import pynvml
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        if device_count > 0:
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            vram_gb = round(mem_info.total / (1024 ** 3), 2)
            if vram_gb >= 12.0:
                tier = HardwareTier.TIER_HIGH
            elif vram_gb >= 6.0:
                tier = HardwareTier.TIER_MID
            else:
                tier = HardwareTier.TIER_LOW
            pynvml.nvmlShutdown()
            return {
                "hardware_tier": tier,
                "tier": tier,
                "vram_gb": vram_gb,
                "ram_gb": ram_gb,
            }
    except Exception as e:
        logger.debug("pynvml detection skipped or failed: %s", e)

    # 2. Check Apple Silicon MPS
    try:
        import torch
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            # Unified memory
            if ram_gb >= 16.0:
                tier = HardwareTier.TIER_MID
                vram_gb = ram_gb / 2.0
            else:
                tier = HardwareTier.TIER_LOW
                vram_gb = ram_gb / 2.0
            return {
                "hardware_tier": tier,
                "tier": tier,
                "vram_gb": vram_gb,
                "ram_gb": ram_gb,
            }
    except Exception as e:
        logger.debug("Torch MPS detection skipped: %s", e)

    # 3. Fallback
    return {
        "hardware_tier": HardwareTier.TIER_LOW,
        "tier": HardwareTier.TIER_LOW,
        "vram_gb": vram_gb,
        "ram_gb": ram_gb,
    }
