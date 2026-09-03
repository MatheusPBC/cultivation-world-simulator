from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field
from src.i18n.locale_registry import get_default_locale


DEFAULT_LOCALE = get_default_locale()


class AudioSettings(BaseModel):
    bgm_volume: float = 0.5
    sfx_volume: float = 0.5


class AudioSettingsPatch(BaseModel):
    bgm_volume: Optional[float] = None
    sfx_volume: Optional[float] = None


class UISettings(BaseModel):
    locale: str = DEFAULT_LOCALE
    audio: AudioSettings = Field(default_factory=AudioSettings)


class UISettingsPatch(BaseModel):
    locale: Optional[str] = None
    audio: Optional[AudioSettingsPatch] = None


class SimulationSettings(BaseModel):
    auto_save_enabled: bool = False
    max_auto_saves: int = 5


class SimulationSettingsPatch(BaseModel):
    auto_save_enabled: Optional[bool] = None
    max_auto_saves: Optional[int] = None


class LLMProfile(BaseModel):
    base_url: str = ""
    model_name: str = ""
    fast_model_name: str = ""
    mode: str = "default"
    max_concurrent_requests: int = Field(default=10, ge=1, le=50)
    has_api_key: bool = False
    use_separate_fast_config: bool = False
    fast_base_url: str = ""
    fast_api_format: str = "openai"
    has_fast_api_key: bool = False
    api_format: str = "openai"  # "openai" 或 "anthropic"


class LLMConfigView(LLMProfile):
    pass


class LLMSettings(BaseModel):
    profile: LLMProfile = Field(default_factory=LLMProfile)


class LLMSecrets(BaseModel):
    api_key: str = ""
    fast_api_key: str = ""


class LLMSettingsUpdate(BaseModel):
    base_url: str
    api_key: Optional[str] = None
    model_name: str
    fast_model_name: str
    mode: str
    max_concurrent_requests: int = Field(default=10, ge=1, le=50)
    clear_api_key: bool = False
    use_separate_fast_config: bool = False
    fast_base_url: str = ""
    fast_api_key: Optional[str] = None
    fast_api_format: str = "openai"
    clear_fast_api_key: bool = False
    api_format: str = "openai"  # "openai" 或 "anthropic"


class NewGameDefaults(BaseModel):
    content_locale: str = DEFAULT_LOCALE
    map_id: str = "classic"
    init_npc_num: int = 9
    sect_num: int = 3
    npc_awakening_rate_per_month: float = 0.01
    world_lore: str = ""
    world_secret_id: str = "none"
    test_mode: bool = False


class NewGameDefaultsPatch(BaseModel):
    content_locale: Optional[str] = None
    map_id: Optional[str] = None
    init_npc_num: Optional[int] = None
    sect_num: Optional[int] = None
    npc_awakening_rate_per_month: Optional[float] = None
    world_lore: Optional[str] = None
    world_secret_id: Optional[str] = None
    test_mode: Optional[bool] = None


class RunConfig(NewGameDefaults):
    semantic_discovery_budget_per_month: int = Field(default=2, ge=0, le=20)
    semantic_evaluation_budget_per_month: int = Field(default=256, ge=1, le=10000)
    semantic_max_ast_nodes: int = Field(default=32, ge=4, le=256)
    semantic_max_ast_depth: int = Field(default=8, ge=2, le=32)
    semantic_dormant_after_months: int = Field(default=24, ge=1, le=1200)
    semantic_discovery_retry_after_months: int = Field(default=12, ge=1, le=1200)
    population_interpreter_llm_budget_per_month: int = Field(default=2, ge=0, le=20)
    population_reaction_evaluation_budget_per_month: int = Field(
        default=8, ge=1, le=256
    )
    domain_interpreter_budget_per_month: int = Field(default=8, ge=0, le=256)
    causal_propagation_budget_per_month: int = Field(default=32, ge=1, le=4096)
    domain_mutation_budget_per_month: int = Field(default=32, ge=1, le=4096)
    population_transfer_max_fraction_per_reaction: float = Field(
        default=0.20, ge=0.0, le=1.0
    )
    population_failed_transfer_retry_after_months: int = Field(
        default=12, ge=1, le=1200
    )
    economy_interpreter_llm_budget_per_month: int = Field(default=2, ge=0, le=20)
    economy_reaction_evaluation_budget_per_month: int = Field(default=8, ge=1, le=256)
    city_interpreter_llm_budget_per_month: int = Field(default=2, ge=0, le=20)
    city_reaction_evaluation_budget_per_month: int = Field(default=8, ge=1, le=256)
    city_blocked_retry_months: int = Field(default=12, ge=1, le=1200)
    government_interpreter_llm_budget_per_month: int = Field(default=2, ge=0, le=20)
    government_reaction_evaluation_budget_per_month: int = Field(
        default=8, ge=1, le=256
    )
    government_blocked_project_retry_months: int = Field(default=12, ge=1, le=1200)
    government_blocked_maintenance_retry_months: int = Field(default=1, ge=1, le=1200)
    organization_interpreter_llm_budget_per_month: int = Field(default=2, ge=0, le=20)
    organization_reaction_evaluation_budget_per_month: int = Field(
        default=8, ge=1, le=256
    )


class AppSettings(BaseModel):
    schema_version: int = 2
    ui: UISettings = Field(default_factory=UISettings)
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    new_game_defaults: NewGameDefaults = Field(default_factory=NewGameDefaults)


class AppSettingsPatch(BaseModel):
    ui: Optional[UISettingsPatch] = None
    simulation: Optional[SimulationSettingsPatch] = None
    new_game_defaults: Optional[NewGameDefaultsPatch] = None


class AppSettingsView(AppSettings):
    pass
