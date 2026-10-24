"""Server-side configuration. Runtime mode is server policy, never a browser toggle."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class RuntimeMode(StrEnum):
    SAMPLE = "sample"
    CONNECTED_DEMO = "connected_demo"
    REPLAY = "replay"


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def _bool(name: str) -> bool:
    return (_env(name, "false") or "false").lower() in ("1", "true", "yes")


def _decimal(name: str) -> Decimal | None:
    v = _env(name)
    if v is None:
        return None
    d = Decimal(v)
    if not d.is_finite() or d < 0:
        raise ValueError(f"{name} must be a finite non-negative decimal")
    return d


def parse_dotenv_value(raw: str) -> str:
    """Defined grammar (audit A09): quoted values are literal; unquoted values end at a whitespace-preceded '#'."""
    v = raw.strip()
    if len(v) >= 2 and v[0] in "'\"":
        q = v[0]
        end = v.find(q, 1)
        if end == -1:
            raise ValueError(f"unterminated quoted value: {raw!r}")
        return v[1:end]
    for i, ch in enumerate(v):
        if ch == "#" and (i == 0 or v[i - 1] in " \t"):
            return v[:i].rstrip()
    return v


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal .env reader; existing environment wins. ponytail: no python-dotenv dependency."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), parse_dotenv_value(v))


@dataclass(frozen=True)
class Settings:
    app_env: str
    runtime_mode: RuntimeMode
    database_url: str
    tenant_id: str
    # Evidence sources
    zetaris_base_url: str | None
    zetaris_org_id: str | None
    zetaris_auth_mode: str | None  # api_key | login_id_token
    zetaris_api_key: str | None
    zetaris_username: str | None
    zetaris_password: str | None
    zetaris_page_limit: int
    source_names: dict[str, str]  # logical source -> qualified catalog/schema prefix
    sample_source_url: str
    # Model
    model_base_url: str
    model_id: str | None
    model_api_key: str | None
    # Memory sidecar
    memory_base_url: str
    memory_auth_token: str | None
    # Execution
    sandbox_writes_enabled: bool
    allowed_target_ids: tuple[str, ...]
    sandbox_dir: Path
    # Budgets
    max_run_cost_usd: Decimal | None
    max_daily_cost_usd: Decimal | None
    max_model_calls_per_run: int
    max_trial_seconds: int
    policy_version: str
    data_manifest_id: str
    carbon_method_version: str | None
    evaluator_dir: Path
    extra: dict = field(default_factory=dict)

    @property
    def zetaris_configured(self) -> bool:
        has_auth = (self.zetaris_auth_mode == "api_key" and self.zetaris_api_key) or (
            self.zetaris_auth_mode == "login_id_token" and self.zetaris_username and self.zetaris_password
        )
        return bool(self.zetaris_base_url and self.zetaris_org_id and has_auth)

    @property
    def model_configured(self) -> bool:
        return bool(self.model_id and self.model_api_key)


def get_settings() -> Settings:
    load_dotenv()
    mode = RuntimeMode(_env("RUNTIME_MODE", "sample"))
    return Settings(
        app_env=_env("APP_ENV", "sandbox"),
        runtime_mode=mode,
        database_url=_env("DATABASE_URL", "postgresql+psycopg://greenops@127.0.0.1:55432/greenops_app"),
        tenant_id=_env("TENANT_ID", "sandbox-tenant"),
        zetaris_base_url=_env("ZETARIS_API_BASE_URL", "https://api.saas.enterprise.zetaris.com"),
        zetaris_org_id=_env("ZETARIS_ORG_ID"),
        zetaris_auth_mode=_env("ZETARIS_AUTH_MODE"),
        zetaris_api_key=_env("ZETARIS_API_KEY"),
        zetaris_username=_env("ZETARIS_USERNAME"),
        zetaris_password=_env("ZETARIS_PASSWORD"),
        zetaris_page_limit=int(_env("ZETARIS_PAGE_LIMIT", "100")),
        source_names={
            "cloud": _env("ZETARIS_SOURCE_CLOUD", "cloud_src.public"),
            "ai": _env("ZETARIS_SOURCE_AI", "ai_src.public"),
            "ref": _env("ZETARIS_SOURCE_REF", "cloud_src.ref"),
        },
        sample_source_url=_env("SAMPLE_SOURCE_URL", "postgresql://greenops@127.0.0.1:55432/greenops_sample_src"),
        model_base_url=_env("MODEL_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        model_id=_env("MODEL_ID"),
        model_api_key=_env("MODEL_API_KEY"),
        memory_base_url=_env("MEMORY_BASE_URL", "http://127.0.0.1:7410"),
        memory_auth_token=_env("MEMORY_AUTH_TOKEN"),
        sandbox_writes_enabled=_bool("SANDBOX_WRITES_ENABLED"),
        allowed_target_ids=tuple(
            t.strip() for t in (_env("ALLOWED_TARGET_IDS", "local/sandbox/support-worker-stg,local/sandbox/support-ai-workflow") or "").split(",") if t.strip()
        ),
        sandbox_dir=Path(_env("SANDBOX_DIR", str(ROOT / "var" / "sandbox"))),
        max_run_cost_usd=_decimal("MAX_RUN_COST_USD"),
        max_daily_cost_usd=_decimal("MAX_DAILY_COST_USD"),
        max_model_calls_per_run=int(_env("MAX_MODEL_CALLS_PER_RUN", "400")),
        max_trial_seconds=int(_env("MAX_TRIAL_SECONDS", "900")),
        policy_version=_env("POLICY_VERSION", "pol-v1"),
        data_manifest_id=_env("DATA_MANIFEST_ID", "support-demo-data-v1"),
        carbon_method_version=_env("CARBON_METHOD_VERSION", "greenops-synthetic-ops-v1"),
        evaluator_dir=Path(_env("EVALUATOR_DIR", str(ROOT / ".evaluator"))),
    )
