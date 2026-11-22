"""Runtime configuration, read once from environment variables.

Every setting has a safe default so the API boots with no configuration at all
(sample data, template answers). Add LLM keys to switch on AI explanations.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


try:  # read backend/.env automatically (python-dotenv ships with uvicorn[standard])
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:  # pragma: no cover
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class ProviderConfig:
    """One OpenAI-compatible chat endpoint in the fallback chain."""

    name: str
    base_url: str
    api_key: str
    model: str
    kind: str = "openai"  # "openai", "azure" or "gemini" (native)
    api_version: str = ""


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    allowed_origins: list[str]
    rate_limit: str
    rate_limit_analyze: str
    rate_limit_cas: str
    rate_limit_chat: str
    max_upload_mb: int
    llm_timeout_s: float
    breaker_failures: int
    breaker_cooldown_s: float
    default_return: float
    default_retire_age: int
    providers: list[ProviderConfig] = field(default_factory=list)

    @property
    def ai_enabled(self) -> bool:
        return bool(self.providers)


def _providers() -> list[ProviderConfig]:
    """Build the LLM fallback chain from whichever keys are present.

    Order = priority. Model names are env-driven on purpose: provider model
    names change often, so set them to whatever is current when you deploy.
    """
    chain: list[ProviderConfig] = []
    if _env("AZURE_OPENAI_ENDPOINT") and _env("AZURE_OPENAI_API_KEY"):
        chain.append(
            ProviderConfig(
                name="azure-openai",
                base_url=_env("AZURE_OPENAI_ENDPOINT").rstrip("/"),
                api_key=_env("AZURE_OPENAI_API_KEY"),
                model=_env("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini"),
                kind="azure",
                api_version=_env("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            )
        )
    if _env("GEMINI_API_KEY"):
        chain.append(
            ProviderConfig(
                name="gemini",
                base_url="https://generativelanguage.googleapis.com/v1beta",
                api_key=_env("GEMINI_API_KEY"),
                model=_env("GEMINI_MODEL", "gemini-flash-latest"),
                kind="gemini",  # native API: works with both AIza… and newer AQ.… keys
            )
        )
    if _env("GROQ_API_KEY"):
        chain.append(
            ProviderConfig(
                name="groq",
                base_url="https://api.groq.com/openai/v1",
                api_key=_env("GROQ_API_KEY"),
                model=_env("GROQ_MODEL", "openai/gpt-oss-120b"),
            )
        )
    if _env("MISTRAL_API_KEY"):
        chain.append(
            ProviderConfig(
                name="mistral",
                base_url="https://api.mistral.ai/v1",
                api_key=_env("MISTRAL_API_KEY"),
                model=_env("MISTRAL_MODEL", "mistral-small-latest"),
            )
        )
    if _env("OPENAI_COMPAT_BASE_URL"):
        chain.append(
            ProviderConfig(
                name=_env("OPENAI_COMPAT_NAME", "openai-compatible"),
                base_url=_env("OPENAI_COMPAT_BASE_URL").rstrip("/"),
                api_key=_env("OPENAI_COMPAT_API_KEY", "none"),
                model=_env("OPENAI_COMPAT_MODEL", "llama3.1"),
            )
        )
    if _env("OLLAMA_URL"):
        chain.append(
            ProviderConfig(
                name="ollama-local",
                base_url=_env("OLLAMA_URL").rstrip("/") + "/v1",
                api_key="ollama",
                model=_env("OLLAMA_MODEL", "qwen2.5:7b-instruct"),
            )
        )
    # LLM_ORDER=groq,gemini puts the named providers first; the rest keep their default order.
    order = [n.strip().lower() for n in _env("LLM_ORDER", "").split(",") if n.strip()]
    if order:
        rank = {n: i for i, n in enumerate(order)}
        chain.sort(key=lambda c: rank.get(c.name, len(order)))
    return chain


def load_settings() -> Settings:
    here = Path(__file__).resolve().parent.parent
    origins = _env("ALLOWED_ORIGINS", "http://localhost:3000")
    return Settings(
        data_dir=Path(_env("DATA_DIR", str(here / "data"))),
        allowed_origins=[o.strip() for o in origins.split(",") if o.strip()],
        rate_limit=_env("RATE_LIMIT", "60/minute"),
        rate_limit_analyze=_env("RATE_LIMIT_ANALYZE", "30/minute"),
        rate_limit_cas=_env("RATE_LIMIT_CAS", "10/minute"),
        rate_limit_chat=_env("RATE_LIMIT_CHAT", "20/minute"),
        max_upload_mb=_env_int("MAX_UPLOAD_MB", 10),
        llm_timeout_s=_env_float("LLM_TIMEOUT_S", 20.0),
        breaker_failures=_env_int("BREAKER_FAILURES", 3),
        breaker_cooldown_s=_env_float("BREAKER_COOLDOWN_S", 60.0),
        default_return=_env_float("DEFAULT_GROSS_RETURN", 0.12),
        default_retire_age=_env_int("DEFAULT_RETIRE_AGE", 60),
        providers=_providers(),
    )


settings = load_settings()
