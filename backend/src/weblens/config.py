"""Centralised configuration.

Every tunable in WebLens lives here. Nothing outside this module reads ``os.environ``,
so the set of knobs is discoverable in one place and a typo in an env var name fails
loudly at startup instead of silently changing behaviour.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ALLOWED_PORTS = frozenset({80, 443})

# Query-string parameter names whose values are replaced before evidence is created.
# Redaction happens at collection time so a secret never enters the evidence graph at all.
SENSITIVE_QUERY_PARAMS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "auth",
        "code",
        "credential",
        "id_token",
        "key",
        "password",
        "pwd",
        "refresh_token",
        "secret",
        "session",
        "sig",
        "signature",
        "token",
    }
)

# Request headers that are never captured into evidence, in either direction.
NEVER_CAPTURED_HEADERS = frozenset(
    {
        "authorization",
        "cookie",
        "proxy-authorization",
        "set-cookie",  # parsed into attribute observations instead; values are dropped
        "x-api-key",
        "x-auth-token",
        "x-csrf-token",
    }
)


class Settings(BaseSettings):
    """Runtime configuration, populated from ``WEBLENS_*`` environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="WEBLENS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server ---
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173", "http://localhost:5173"]
    )

    # --- Logging ---
    log_format: str = Field(default="text", pattern="^(text|json)$")
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    # --- Scan budgets (milliseconds) ---
    navigation_timeout_ms: int = Field(default=30_000, ge=1_000, le=120_000)
    settle_timeout_ms: int = Field(default=5_000, ge=0, le=30_000)
    total_scan_budget_ms: int = Field(default=90_000, ge=5_000, le=600_000)
    http_timeout_ms: int = Field(default=15_000, ge=1_000, le=60_000)
    analyzer_timeout_ms: int = Field(default=5_000, ge=100, le=60_000)

    # --- Politeness and concurrency ---
    max_concurrent_scans: int = Field(default=2, ge=1, le=16)
    max_concurrent_scans_per_host: int = Field(default=1, ge=1, le=4)
    min_host_interval_seconds: float = Field(default=5.0, ge=0.0, le=300.0)
    respect_robots: bool = True
    max_redirects: int = Field(default=5, ge=0, le=20)
    probe_http_downgrade: bool = True

    # --- Evidence caps ---
    max_body_bytes: int = Field(default=2 * 1024 * 1024, ge=1024)
    max_network_requests_recorded: int = Field(default=400, ge=10)
    max_style_samples: int = Field(default=1500, ge=50)

    # --- Result buffer ---
    result_ttl_seconds: int = Field(default=900, ge=30, le=86_400)
    max_retained_results: int = Field(default=25, ge=1, le=500)

    # --- Target guard ---
    allowed_extra_ports: list[int] = Field(default_factory=list)
    allow_private_targets: bool = False
    """TEST ONLY. Permits loopback/private targets so the live suite can scan a local
    dev server. Enabling this on a reachable deployment turns the API into an internal
    network probe."""

    # --- Security scoring ---
    minimum_applicable_points: float = Field(default=40.0, ge=0.0, le=100.0)

    # --- Optional AI layer ---
    ai_provider: str = Field(default="none", pattern="^(none)$")
    """Only ``none`` is accepted in V1. The provider protocol exists; no implementation
    ships in the default install path."""

    # --- V2: Research and inference ---
    search_provider: str = Field(default="none")
    """Public research search provider name. ``none`` means research is skipped.
    Supported: ``none``, ``brave``."""

    brave_api_key: str = Field(default="")
    """API key for Brave Search. Required when search_provider is 'brave'."""

    inference_provider: str = Field(default="none")
    """AI inference provider name. ``none`` means inference is skipped."""

    inference_api_key: str = Field(default="")
    """API key for the AI inference provider (e.g., OpenAI, Groq)."""

    inference_model: str = Field(default="")
    """Model name for the inference provider."""

    traffic_provider: str = Field(default="none")
    """Traffic data provider name. ``none`` means traffic data is unavailable."""

    @field_validator("cors_origins", "allowed_extra_ports", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Accept comma-separated env values as well as JSON lists."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return value
            return [part.strip() for part in stripped.split(",") if part.strip()]
        return value

    @property
    def allowed_ports(self) -> frozenset[int]:
        return DEFAULT_ALLOWED_PORTS | frozenset(self.allowed_extra_ports)

    @property
    def http_timeout_seconds(self) -> float:
        return self.http_timeout_ms / 1000

    @property
    def total_scan_budget_seconds(self) -> float:
        return self.total_scan_budget_ms / 1000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings singleton (FastAPI dependency and internal callers)."""
    return Settings()
