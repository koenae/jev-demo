"""Environment, keys and LLM provider configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from jevdemo.errors import MissingKeyError

ROOT = Path(__file__).resolve().parent.parent
RECORDINGS_DIR = ROOT / "recordings"
ENV_FILE = ROOT / ".env"

TYPESAFE_KEY_ENV = "TYPESAFE_API_KEY"
Provider = Literal["openai", "anthropic", "azure_openai"]
PROVIDERS: tuple[Provider, ...] = ("openai", "anthropic", "azure_openai")

PACKAGES = (
    "typesafe-sdk",
    "langchain",
    "langchain-core",
    "langchain-typesafe",
    "langchain-openai",
    "langchain-anthropic",
    "langgraph",
    "marimo",
    "rich",
    "python-dotenv",
)


def load_env() -> None:
    """Load `.env` from the repo root without overriding real environment variables."""
    load_dotenv(ENV_FILE, override=False)


def require_env(name: str, purpose: str) -> str:
    load_env()
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingKeyError(
            f"{name} is not set ({purpose}).",
            hint=f"Copy .env.example to .env and fill in {name}, or run with --offline.",
        )
    return value


def typesafe_api_key() -> str:
    return require_env(TYPESAFE_KEY_ENV, "TypeSafe early-access key for Jev")


@dataclass(frozen=True)
class LLMSettings:
    provider: Provider
    model: str
    api_key: str
    base_url: str | None = None  # OpenAI-compatible gateways, e.g. Microsoft Foundry /openai/v1
    azure_endpoint: str | None = None
    azure_api_version: str | None = None

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


def llm_settings() -> LLMSettings:
    """Read the LLM configuration for demo 3 (agent) from the environment."""
    load_env()
    provider = os.environ.get("LLM_PROVIDER", "openai").strip().lower()
    if provider not in PROVIDERS:
        raise MissingKeyError(
            f"LLM_PROVIDER={provider!r} is not supported.",
            hint=f"Use one of: {', '.join(PROVIDERS)}.",
        )
    model = require_env("LLM_MODEL", "chat model (or Azure deployment name) for the agent")
    if provider == "openai":
        return LLMSettings(
            "openai",
            model,
            require_env("OPENAI_API_KEY", "OpenAI (or Foundry) key for demo 3"),
            base_url=os.environ.get("OPENAI_BASE_URL", "").strip() or None,
        )
    if provider == "anthropic":
        return LLMSettings(
            "anthropic", model, require_env("ANTHROPIC_API_KEY", "Anthropic key for demo 3")
        )
    return LLMSettings(
        "azure_openai",
        model,
        require_env("AZURE_OPENAI_API_KEY", "Azure OpenAI key for demo 3"),
        azure_endpoint=require_env("AZURE_OPENAI_ENDPOINT", "Azure OpenAI endpoint"),
        azure_api_version=require_env("AZURE_OPENAI_API_VERSION", "Azure OpenAI API version"),
    )


def build_chat_model(settings: LLMSettings | None = None):
    """Create the LangChain chat model for the agent in demo 3."""
    from langchain.chat_models import init_chat_model

    settings = settings or llm_settings()
    if settings.provider == "azure_openai":
        return init_chat_model(
            settings.model,
            model_provider="azure_openai",
            azure_deployment=settings.model,
            azure_endpoint=settings.azure_endpoint,
            api_version=settings.azure_api_version,
            api_key=settings.api_key,
        )
    kwargs = {"api_key": settings.api_key}
    if settings.base_url:
        kwargs["base_url"] = settings.base_url
    return init_chat_model(settings.model, model_provider=settings.provider, **kwargs)


@cache
def package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in PACKAGES:
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = "not installed"
    return versions
