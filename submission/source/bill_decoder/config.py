"""Configuration read from environment variables (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # python-dotenv is optional at import time
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


@dataclass(frozen=True)
class Config:
    model_provider: str
    model_name: str
    api_key: str
    min_seconds_between_calls: float
    max_retries: int
    request_timeout_s: float
    max_image_side: int  # 0 = do not downscale
    seed: int = 0
    backoff_seconds: tuple[float, ...] = (5.0, 10.0, 20.0)


def load_config() -> Config:
    return Config(
        model_provider=os.getenv("MODEL_PROVIDER", "google"),
        model_name=os.getenv("MODEL_NAME", "gemini-3.1-flash-lite"),
        api_key=os.getenv("API_KEY", ""),
        min_seconds_between_calls=float(os.getenv("MIN_SECONDS_BETWEEN_CALLS", "4.5")),
        max_retries=int(os.getenv("MAX_RETRIES", "2")),
        request_timeout_s=float(os.getenv("REQUEST_TIMEOUT_S", "60")),
        max_image_side=int(os.getenv("MAX_IMAGE_SIDE", "0")),
    )
