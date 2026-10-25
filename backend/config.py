"""Portkey client. Every agent uses gpt-6-luna and no other model."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from models import MODEL_NAME

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent

load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / "Lecture 2" / ".env")

PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")
# gpt-6-luna rejects function tools when a reasoning effort is turned on.
LUNA_SETTINGS = {
    "openai_reasoning_effort": "none",
    "parallel_tool_calls": False,
}


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Add it to .env.")
    return key


def build_model():
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider

    api_key = require_api_key()
    provider_name = os.getenv("PORTKEY_PROVIDER", "openai")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=PORTKEY_BASE_URL,
        default_headers={
            "x-portkey-api-key": api_key,
            "x-portkey-provider": provider_name,
        },
    )
    return OpenAIChatModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
