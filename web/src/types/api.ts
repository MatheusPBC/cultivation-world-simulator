/**
 * API 数据传输对象 (Data Transfer Objects)
 * 这些类型严格对应后端接口返回的 JSON 结构。
 */

import type { AppLocale } from '../locales/registry';
import type {
  MapMatrix,
  CelestialPhenomenon,
  HiddenDomainInfo,
  AvatarDetail,
  RegionDetail,
  SectDetail,
  POIDetail,
  EffectEntity,
  CultivationDisplay,
  SemanticReading,
} from './core';

// --- 通用响应 ---

export interface ApiResponse<T> {
  status: 'ok' | 'error';
  message?: string;
  data?: T; // 有些接口直接把数据铺平在顶层，需根据实际情况调整
}

export type InstitutionalOwnerKindDTO = 'region' | 'sect' | 'dynasty';
export interface InstitutionalChainResponseDTO {
  owner: { kind: 'city' | 'sect' | 'dynasty'; id: string; institution_id: string; name: string; region_id: string | null };
  current_month: number;
  authority: { institution_id: string; office_ids: string[]; active_claim_ids: string[]; material_control: Record<string, boolean> };
  institutions: Array<{ id: string; kind: string; name: string; scope: 'owner' | 'party' | 'governed_city' }>;
  commitments: Array<{ id: string; party_ids: string[]; opened_month: number; closed_month: number | null; aggregate_status: string; owner_institution_id: string; control_scope: 'direct' | 'governed_city'; origin_event_id: string; terms: Array<{ id: string; index: number; kind: string; obligor_institution_id: string; beneficiary_institution_id: string; subject: EntityReferenceDTO; status: string; proposed_month: number; due_month: number | null; breached_month: number | null; resolved_month: number | null; parameters: Record<string, string | number | boolean | null>; evidence_event_ids: string[]; breach_event_ids: string[]; remediation_of_term_id: string | null }> }>;
  events: Array<{ event_id: string; content: string; event_type: string; month_stamp: number; fact_kind: FactKindDTO; causal_origin: CausalOriginDTO; commitment_id: string | null; term_id: string | null; relation: CausalRelationDTO | null; source_event_ids: string[]; decision: { actor_kind: string; actor_id: string; action: string; reason: string } | null }>;
  memories: Array<{ id: string; institution_id: string; event_id: string; salience: number; recorded_month: number; last_reinforced_month: number; effective_salience: number; factors: Record<string, number> }>;
  cursor: { commitments: { next: string | null; has_more: boolean }; events: { next: string | null; has_more: boolean } };
}

// --- 具体接口响应 ---

export interface InitialStateDTO {
  status: 'ok' | 'error';
  year: number;
  month: number;
  avatars?: Array<{
    id: string;
    name?: string;
    x: number;
    y: number;
    action?: string;
    gender?: string;
    race?: string;
    pic_id?: number;
    realm?: string;
    cultivation?: CultivationDisplay;
    cultivation_display?: string;
  }>;
  events?: EventDTO[];
  phenomenon?: CelestialPhenomenon | null;
  active_domains?: HiddenDomainInfo[];
  world_revision?: number;
  is_paused?: boolean;
}

export interface TickPayloadDTO {
  type: 'tick';
  year: number;
  month: number;
  avatars?: Array<Partial<InitialStateDTO['avatars'] extends (infer U)[] ? U : never>>;
  removed_avatar_ids?: string[];
  world_revision?: number;
  events?: EventDTO[];
  poi_updates?: POIUpdateDTO[];
  site_updates?: InfrastructureSiteUpdateDTO[];
  route_updates?: RouteUpdateDTO[];
  phenomenon?: CelestialPhenomenon | null;
  active_domains?: HiddenDomainInfo[];
}

export interface AvatarDeltaSocketMessage {
  type: 'avatar_delta';
  avatars?: TickPayloadDTO['avatars'];
  removed_avatar_ids?: string[];
  world_revision: number;
}

export interface MapResponseDTO {
  map_id?: string;
  map_name?: string;
  preset_version?: number;
  width?: number;
  height?: number;
  data: MapMatrix;
  territory_rows: number[][];
  routes: RouteDTO[];
  geography: PhysicalGeographyDTO;
  regions: Array<{
    id: string | number;
    name: string;
    x: number;
    y: number;
    type: string;
    sect_id?: number;
    sect_name?: string;
    sect_is_active?: boolean;
    sect_color?: string;
    sub_type?: string;
  }>;
  infrastructure_sites: InfrastructureSiteDTO[];
  pois?: Array<{
    id: string;
    kind: string;
    name: string;
    x: number;
    y: number;
    icon_key?: string;
    clickable?: boolean;
    deceased_avatar_id?: string;
  }>;
  render_config?: MapRenderConfigDTO;
}

export interface EntityReferenceDTO {
  kind: string;
  id: string;
}

export interface InfrastructureSiteDTO {
  id: string;
  kind: string;
  name: string;
  cell_refs: Array<[number, number]>;
  region_ids: number[];
  route_ids: string[];
  water_body_ids: string[];
  capability_ids: string[];
  owner_ref: EntityReferenceDTO | null;
  maintainer_ref: EntityReferenceDTO | null;
  integrity: number;
  enabled: boolean;
  status: 'active' | 'impaired' | 'destroyed';
  x: number;
  y: number;
  clickable: boolean;
  last_event_id: string | null;
}

export type InfrastructureSiteUpdateDTO =
  | { op: 'upsert'; site: InfrastructureSiteDTO }
  | { op: 'remove'; id: string };

export interface RouteDTO {
  id: string;
  endpoint_region_ids: [number, number];
  mode: string;
  capacity: number;
  operational_capacity: number;
  quality: number;
  enabled: boolean;
  allowed_resource_ids: string[];
  dependency_site_ids: string[];
}

export interface RouteUpdateDTO {
  id: string;
  operational_capacity: number;
  dependency_site_ids: string[];
}

export interface WaterBodyDTO {
  id: string;
  kind: 'river' | 'lake' | 'sea' | string;
  cell_refs: Array<[number, number]>;
  navigable: boolean;
  region_id?: number;
  flow_direction?: [number, number];
}

export interface PhysicalGeographyDTO {
  elevation_rows: number[][];
  water_bodies: WaterBodyDTO[];
}

export type POIUpdateDTO =
  | {
      op: 'upsert';
      poi: {
        id: string;
        kind: string;
        name: string;
        x: number;
        y: number;
        icon_key?: string;
        clickable?: boolean;
        deceased_avatar_id?: string;
      };
    }
  | {
      op: 'remove';
      id: string;
    };

// --- Detail 接口 ---

// 目前后端 /api/v1/query/detail 直接返回 Avatar/Region/Sect 的结构化信息，
// 在 P0 阶段我们先复用前端领域模型作为 DTO 类型，后续若后端结构调整再拆分。
export type AvatarDetailDTO = AvatarDetail;
export type RegionDetailDTO = RegionDetail;
export type SectDetailDTO = SectDetail;
export type POIDetailDTO = POIDetail;
export interface InfrastructureSiteDetailDTO extends InfrastructureSiteDTO {
  desc?: string;
  source_event_ids?: string[];
}

export interface RouteDetailDTO extends RouteDTO {
  source_event_ids: string[];
}

export type MetricReadingDTO = SemanticReading;

export type DetailResponseDTO =
  | AvatarDetailDTO
  | RegionDetailDTO
  | SectDetailDTO
  | POIDetailDTO
  | InfrastructureSiteDetailDTO
  | RouteDetailDTO;

export interface MapRenderConfigDTO {
  water_speed?: 'none' | 'low' | 'medium' | 'high';
  cloud_frequency?: 'none' | 'low' | 'high';
}

export interface SaveFileDTO {
  filename: string;
  save_time: string;
  game_time: string;
  version: string;
  // 新增字段。
  language: string;
  avatar_count: number;
  alive_count: number;
  dead_count: number;
  custom_name: string | null;
  event_count: number;
  is_auto_save: boolean;
  playthrough_id?: string;
  map_id?: string;
  map_name?: string;
}

// --- Game Data Metadata ---

export interface GameDataDTO {
  sects: Array<{ id: number; name: string; alignment: string; accepts_yao: boolean }>;
  races?: Array<{ id: string; label: string; is_yao: boolean }>;
  personas: Array<{ id: number; name: string; desc: string; rarity: string }>;
  realms: string[];
  techniques: Array<{ id: number; name: string; grade: string; attribute: string; sect: string | null }>;
  weapons: Array<{ id: number; name: string; grade: string; type: string }>;
  auxiliaries: Array<{ id: number; name: string; grade: string }>;
  alignments: Array<{ value: string; label: string }>;
  avatar_creation: {
    age: {
      min: number;
      max_by_realm: Record<string, number>;
    };
  };
}

export interface SimpleAvatarDTO {
  id: string;
  name: string;
  sect_name: string;
  realm: string;
  cultivation?: CultivationDisplay;
  cultivation_display?: string;
  gender: string;
  age: number;
  race?: string;
}

export interface CreateAvatarParams {
  surname?: string;
  given_name?: string;
  gender?: string;
  age?: number;
  level?: number;
  sect_id?: number;
  persona_ids?: number[];
  pic_id?: number;
  technique_id?: number;
  weapon_id?: number;
  auxiliary_id?: number;
  alignment?: string;
  appearance?: number;
  race?: string;
  relations?: Array<{ target_id: string; relation: string }>;
}

export interface AvatarAdjustOptionDTO extends EffectEntity {
  id: string;
}

export interface AvatarAdjustCatalogDTO {
  techniques: AvatarAdjustOptionDTO[];
  weapons: AvatarAdjustOptionDTO[];
  auxiliaries: AvatarAdjustOptionDTO[];
  personas: AvatarAdjustOptionDTO[];
  goldfingers: AvatarAdjustOptionDTO[];
}

export interface UpdateAvatarAdjustmentParams {
  avatar_id: string;
  category: 'technique' | 'weapon' | 'auxiliary' | 'personas' | 'goldfinger';
  target_id?: number | null;
  persona_ids?: number[];
}

export interface UpdateAvatarPortraitParams {
  avatar_id: string;
  pic_id: number;
}

export interface GenerateCustomContentParams {
  category: 'technique' | 'weapon' | 'auxiliary' | 'goldfinger';
  realm?: string;
  user_prompt: string;
}

export interface CustomContentDraftDTO extends AvatarAdjustOptionDTO {
  category: 'technique' | 'weapon' | 'auxiliary' | 'goldfinger';
  realm?: string;
  effects: Record<string, number | boolean>;
  weapon_type?: string;
  story_prompt?: string;
  mechanism_type?: string;
  is_custom?: boolean;
}

export interface CreateCustomContentParams {
  category: 'technique' | 'weapon' | 'auxiliary' | 'goldfinger';
  draft: CustomContentDraftDTO;
}

export interface PhenomenonDTO {
  id: number;
  name: string;
  desc: string;
  rarity: string;
  duration_years: number;
  effect_desc: string;
}

// --- Config ---

export interface AudioSettingsDTO {
  bgm_volume: number;
  sfx_volume: number;
}

export interface UISettingsDTO {
  locale: AppLocale | string;
  audio: AudioSettingsDTO;
}

export interface SimulationSettingsDTO {
  auto_save_enabled: boolean;
  max_auto_saves: number;
}

export interface LLMConfigViewDTO {
  base_url: string;
  model_name: string;
  fast_model_name: string;
  mode: string;
  max_concurrent_requests: number;
  has_api_key: boolean;
  api_format: string;
  use_separate_fast_config: boolean;
  fast_base_url: string;
  fast_api_format: string;
  has_fast_api_key: boolean;
}

export interface LLMConfigDTO {
  base_url: string;
  api_key?: string;
  model_name: string;
  fast_model_name: string;
  mode: string;
  max_concurrent_requests: number;
  clear_api_key?: boolean;
  api_format: string;
  use_separate_fast_config: boolean;
  fast_base_url: string;
  fast_api_key?: string;
  fast_api_format: string;
  clear_fast_api_key?: boolean;
}

export interface LLMStatusDTO {
  configured: boolean;
  requires_config?: boolean;
  last_failure?: string;
}

export interface RunConfigDTO {
  content_locale: AppLocale | string;
  map_id: string;
  init_npc_num: number;
  sect_num: number;
  npc_awakening_rate_per_month: number;
  world_lore?: string;
  world_secret_id?: string;
  test_mode: boolean;
}

export interface WorldSecretOptionDTO {
  id: string;
  title: string;
}

export interface WorldSecretMetaResponseDTO {
  options: WorldSecretOptionDTO[];
}

export interface WorldSecretAvatarRefDTO {
  id: string;
  name: string;
  is_dead?: boolean;
}

export interface WorldSecretFragmentOverviewDTO {
  id: string;
  order: number;
  angle: string;
  text: string;
  known_by: WorldSecretAvatarRefDTO[];
}

export interface WorldSecretAvatarOverviewDTO extends WorldSecretAvatarRefDTO {
  known_fragment_count: number;
  fragment_count: number;
  knows_full_secret: boolean;
  decision?: string | null;
}

export interface WorldSecretOverviewResponseDTO {
  active_secret: {
    id: string;
    title: string;
    secret: string;
    fragment_count: number;
  };
  public_revealed: boolean;
  public_revealed_month?: number | null;
  public_revealed_by?: WorldSecretAvatarRefDTO | null;
  fragments: WorldSecretFragmentOverviewDTO[];
  avatars: WorldSecretAvatarOverviewDTO[];
}

export interface MapPresetDTO {
  id: string;
  name: string;
  desc: string;
  size_label?: string;
  version?: number;
  is_default?: boolean;
}

export interface MapPresetsResponseDTO {
  maps: MapPresetDTO[];
}

export interface AppSettingsDTO {
  schema_version: number;
  ui: UISettingsDTO;
  simulation: SimulationSettingsDTO;
  llm: {
    profile: LLMConfigViewDTO;
  };
  new_game_defaults: RunConfigDTO;
}

export interface AppSettingsPatchDTO {
  ui?: {
    locale?: UISettingsDTO['locale'];
    audio?: Partial<AudioSettingsDTO>;
  };
  simulation?: Partial<SimulationSettingsDTO>;
  new_game_defaults?: Partial<RunConfigDTO>;
}

// --- Events ---

export type EventSubjectDTO =
  | {
      type: 'avatar';
      id: string;
      name: string;
      color?: string | null;
      is_dead?: boolean;
    }
  | {
      type: 'sect';
      id: number;
      name: string;
      color?: string | null;
      is_active?: boolean;
    }

export type FactKindDTO = 'occurrence' | 'state_transition' | 'derived_condition' | 'decision';
export type CausalOriginDTO =
  | 'deterministic'
  | 'llm_interpretation'
  | 'actor_decision'
  | 'derived_condition'
  | 'external_event';

export interface EventDTO {
  id: string;
  text: string;
  content: string;
  year: number;
  month: number;
  month_stamp: number;
  related_avatar_ids: string[];
  related_sects?: number[];
  subjects?: EventSubjectDTO[];
  is_major: boolean;
  is_story: boolean;
  render_key?: string;
  render_params?: Record<string, string | number | boolean | null>;
  created_at: number;
  fact_kind: FactKindDTO;
  causal_origin: CausalOriginDTO;
}

export interface EventsResponseDTO {
  events: EventDTO[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface FetchEventsParams {
  avatar_id?: string;
  avatar_id_1?: string;
  avatar_id_2?: string;
  sect_id?: number;
  major_scope?: 'all' | 'major' | 'minor';
  cursor?: string;
  limit?: number;
}

export type WorldJournalPeriodMonths = 1 | 3 | 12;

export interface WorldJournalActivityDTO {
  total_events: number;
  major_events: number;
  story_events: number;
  routine_events: number;
  active_avatar_count: number;
}

export interface WorldJournalOngoingDTO {
  avatar_id: string;
  avatar_name: string;
  action: string;
  event_count: number;
  short_term_objective: string;
  long_term_objective: string;
}

export type WorldSituationKindDTO =
  | 'hazard'
  | 'condition'
  | 'project'
  | 'infrastructure'
  | 'crisis'
  | 'petition';

export type WorldSituationSeverityDTO = 'critical' | 'major' | 'notable';

export interface WorldSituationSubjectDTO {
  kind: 'avatar' | 'sect' | 'region' | 'site';
  id: string;
  name: string;
}

export interface WorldSituationResponseDTO {
  event_id: string;
  decision: 'maintain' | 'act';
  reason: string;
  actor: WorldSituationSubjectDTO | null;
  rejected: Array<{ action_name: string; reason: string }>;
}

export interface WorldSituationDTO {
  id: string;
  kind: WorldSituationKindDTO;
  severity: WorldSituationSeverityDTO;
  status: string;
  started_month: number;
  age_months: number;
  title?: string;
  title_key: string;
  title_params: Record<string, string | number>;
  summary?: string;
  summary_key: string;
  summary_params: Record<string, string | number>;
  primary_event_id: string;
  source_event_ids: string[];
  subjects: WorldSituationSubjectDTO[];
  direct_action: 'dao_petition' | null;
  latest_response: WorldSituationResponseDTO | null;
  latest_event: EventDTO | null;
}

export interface WorldJournalResponseDTO {
  period: {
    months: WorldJournalPeriodMonths;
    start_month_stamp: number;
    end_month_stamp: number;
  };
  activity: WorldJournalActivityDTO;
  highlights: EventDTO[];
  stories: EventDTO[];
  stories_truncated: boolean;
  ongoing: WorldJournalOngoingDTO[];
  situations: WorldSituationDTO[];
}

// --- Live Guide ---

export type LiveGuideSeverityDTO = 'critical' | 'major' | 'notable';
export type LiveGuideSubjectKindDTO = 'avatar' | 'sect';

export interface LiveGuideSubjectDTO {
  kind: LiveGuideSubjectKindDTO;
  id: string;
  name: string;
}

export interface LiveGuideThreadDTO {
  id: string;
  title: string;
  summary: string;
  severity: LiveGuideSeverityDTO;
  primary_event_id: string;
  source_event_ids: string[];
  subjects: LiveGuideSubjectDTO[];
}

export interface LiveGuidePersonDTO {
  avatar_id: string;
  name: string;
  current_action: string;
  ambition: string;
  event_count: number;
}

export interface LiveGuideResponseDTO {
  date: {
    month_stamp: number;
    year: number;
    month: number;
  };
  headline: string;
  source_event_ids: string[];
  threads: LiveGuideThreadDTO[];
  people: LiveGuidePersonDTO[];
  concept: {
    term_key: string;
    source_event_ids: string[];
  };
}

export interface LiveGuideAnswerDTO {
  answer: string;
  source_event_ids: string[];
  mode: 'generated' | 'fallback' | 'unavailable';
}

export type DaoPetitionStatusDTO = 'pending' | 'silenced' | 'signed' | 'favored';

export interface DaoPetitionDTO {
  id: string;
  initiator_kind: 'avatar' | 'sect' | 'court';
  initiator_id: string;
  initiator_name: string;
  region_id: number;
  tradition: string;
  motivated_event_ids: string[];
  rite_event_ids: string[];
  content: string;
  created_month: number;
  status: DaoPetitionStatusDTO;
  response_event_id: string;
  response_content: string;
  favor_expires_month: number | null;
}

export interface DaoPetitionsResponseDTO {
  pending: DaoPetitionDTO[];
  history: DaoPetitionDTO[];
}

// --- World Chronicle ---

export type ChronicleTriggerDTO = 'major_event' | 'max_interval';
export type ChronicleClaimKindDTO = 'fact' | 'inference';
export type ChronicleReferenceKindDTO = 'avatar' | 'sect' | 'region' | 'event';

export interface ChronicleReferenceDTO {
  id: string;
  kind: ChronicleReferenceKindDTO;
  label: string;
  target_id: string | null;
  claim_kind: ChronicleClaimKindDTO | null;
  source_event_ids: string[];
}

export interface ChronicleSegmentDTO {
  text: string;
  reference: ChronicleReferenceDTO | null;
}

export interface ChronicleParagraphDTO {
  segments: ChronicleSegmentDTO[];
  source_event_ids: string[];
}

export interface ChronicleChapterDTO {
  id: string;
  start_month_stamp: number;
  end_month_stamp: number;
  trigger: ChronicleTriggerDTO;
  title: string;
  paragraphs: ChronicleParagraphDTO[];
  source_event_ids: string[];
  created_at: number;
}

export interface WorldChronicleResponseDTO {
  chapters: ChronicleChapterDTO[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface ChronicleDossierResponseDTO {
  chapter_id: string;
  anchor: ChronicleReferenceDTO;
  focal_event: EventDTO | null;
  sequence: EventDTO[];
  pruned_source_ids: string[];
  truncated: boolean;
}

export interface FetchWorldChronicleParams {
  cursor?: string | null;
  limit?: number;
}

export interface FetchChronicleDossierParams {
  depth?: number;
  limit?: number;
}

// --- Causal "why" drill-down ---

export type CausalRelationDTO =
  | 'triggered_by'
  | 'enabled_by'
  | 'motivated_by'
  | 'response_to'
  | 'resolves'
  | 'prevented_by'
  | 'contributed_to';

export interface CausalEdgeDTO {
  relation: CausalRelationDTO;
  weight: number;
  note_key: string | null;
  note_params: Record<string, string | number | boolean | null> | null;
  depth: number;
  event: EventDTO | null;
  pruned: boolean;
}

export interface StateDeltaDTO {
  id: string;
  event_id: string;
  owner_kind: string;
  owner_id: string;
  aspect: string;
  before: string | null;
  after: string | null;
  magnitude: number | null;
}

export interface AgentDecisionRejectedDTO {
  action_name: string;
  params: Record<string, unknown>;
  reason: string;
}

export interface AgentDecisionChosenDTO {
  action_name: string;
  params: Record<string, unknown>;
  appraisal_ids?: string[];
}

export interface DecisionAppraisalDTO {
  appraisal_id: string;
  // True when the citation survived in the decision's chosen_chain but the
  // appraisal row itself was removed by the source event's ON DELETE CASCADE.
  // The placeholder keeps the audit trail from silently shrinking, so the
  // display fields below are null/empty and the row must not be interactive.
  pruned: boolean;
  focus_avatar_id: string;
  focus_avatar_name: string;
  // Raw enum value, kept only for machine semantics -- the frontend has no
  // locale entries for tokens like "emotion_angry". Use `emotion` to render.
  primary_emotion: string;
  emotion: {
    name: string;
    emoji: string;
    desc: string;
  } | null;
  summary: string | null;
  valence: number | null;
  source_event_id: string;
  source_event_date: string;
}

export interface AgentDecisionDTO {
  id: string;
  month_stamp: number;
  subject_kind: string;
  subject_id: string;
  source: string;
  considered_count: number;
  chosen_chain: AgentDecisionChosenDTO[];
  thinking: string;
  short_term_objective: string;
  rejected: AgentDecisionRejectedDTO[];
}

export interface EventCausalDetailDTO {
  event: EventDTO;
  causes: CausalEdgeDTO[];
  effects: CausalEdgeDTO[];
  deltas: StateDeltaDTO[];
  measurements: MetricReadingDTO[];
  decision: AgentDecisionDTO | null;
  decision_appraisals: DecisionAppraisalDTO[];
  truncated: boolean;
}

export interface FetchEventCausalDetailParams {
  depth?: number;
  limit?: number;
}

// --- Status ---

export interface InitStatusDTO {
  status: 'idle' | 'pending' | 'in_progress' | 'ready' | 'error';
  phase: number;
  phase_name: string;
  progress: number;
  elapsed_seconds: number;
  error: string | null;
  version?: string;
  llm_check_failed: boolean;
  llm_error_message: string;
  llm_check_pending?: boolean;
  is_paused?: boolean;
  pause_reason?: string;
  roleplay?: RoleplaySessionDTO | null;
}

export type RoleplayPromptRequestType = 'decision' | 'choice' | 'conversation';
export type RoleplayChoiceVariant = 'accept' | 'reject' | 'default';
export type RoleplaySessionStatus =
  | 'inactive'
  | 'observing'
  | 'awaiting_decision'
  | 'awaiting_choice'
  | 'conversing'
  | 'submitting';
export type RoleplayInteractionRecordType =
  | 'command'
  | 'action_chain'
  | 'error'
  | 'choice_prompt'
  | 'choice'
  | 'conversation_player'
  | 'conversation_assistant'
  | 'conversation_summary'
  | 'local_feedback';

export interface RoleplayPromptRequestDTO {
  request_id: string;
  type: RoleplayPromptRequestType;
  avatar_id: string;
  target_avatar_id?: string;
  title: string;
  description: string;
  options?: Array<{
    key: string;
    title: string;
    description: string;
    variant?: RoleplayChoiceVariant;
  }>;
  messages?: RoleplayConversationMessageDTO[];
  can_end?: boolean;
  created_at: number;
}

export interface RoleplayConversationMessageDTO {
  id: string;
  role: 'player' | 'assistant';
  speaker_avatar_id?: string;
  speaker_name: string;
  content: string;
  created_at: number;
}

export interface RoleplayConversationSessionDTO {
  session_id: string;
  request_id: string;
  avatar_id: string;
  target_avatar_id: string;
  initiator_avatar_id: string;
  status: 'awaiting_player' | 'generating_reply' | 'awaiting_continue' | 'completed' | 'cancelled';
  messages: RoleplayConversationMessageDTO[];
  started_at: number;
  last_summary?: {
    summary?: string;
    relation_hint?: string;
    story_hint?: string;
  } | null;
  last_ai_thinking?: string;
}

export interface RoleplayActionDisplayTokenDTO {
  kind: 'verb' | 'arg';
  text: string;
}

export interface RoleplayInteractionRecordDTO {
  type: RoleplayInteractionRecordType;
  created_at: number;
  text?: string;
  actions?: Array<{
    action_name: string;
    tokens: RoleplayActionDisplayTokenDTO[];
  }>;
}

export interface RoleplaySessionDTO {
  controlled_avatar_id: string | null;
  status: RoleplaySessionStatus;
  pending_request: RoleplayPromptRequestDTO | null;
  last_prompt_context: Record<string, unknown> | null;
  conversation_session?: RoleplayConversationSessionDTO | null;
  interaction_history?: RoleplayInteractionRecordDTO[];
}

export interface RankingAvatarDTO {
  id: string;
  name: string;
  sect: string;
  sect_id?: string;
  realm: string;
  stage: string;
  cultivation?: CultivationDisplay;
  cultivation_display?: string;
  power: number;
}

export interface RankingSectDTO {
  id: string;
  name: string;
  alignment: string;
  member_count: number;
  total_power: number;
}

export interface TournamentSummaryDTO {
  next_year: number;
  heaven_first?: { id: string; name: string };
  earth_first?: { id: string; name: string };
  human_first?: { id: string; name: string };
}

export interface RankingsDTO {
  heaven: RankingAvatarDTO[];
  earth: RankingAvatarDTO[];
  human: RankingAvatarDTO[];
  sect: RankingSectDTO[];
  tournament?: TournamentSummaryDTO;
}

// --- Sect Relations ---

export interface SectRelationDTO {
  sect_a_id: number;
  sect_a_name: string;
  sect_b_id: number;
  sect_b_name: string;
  value: number;        // -100 ~ 100
  diplomacy_status: 'war' | 'peace' | string;
  diplomacy_duration_months: number;
  reason_breakdown: Array<{
    reason: string;     // 枚举字符串，如 ALIGNMENT_OPPOSITE
    delta: number;      // 本事由对关系值的增减
    meta?: Record<string, unknown>;
  }>;
}

export interface SectRelationsResponseDTO {
  relations: SectRelationDTO[];
}

export interface SectTerritorySummaryDTO {
  id: number;
  name: string;
  color: string;
  influence_radius: number;
  is_active: boolean;
  owned_tiles: Array<{
    x: number;
    y: number;
  }>;
  boundary_edges: Array<{
    x: number;
    y: number;
    side: 'left' | 'right' | 'top' | 'bottom' | string;
  }>;
}

export interface SectTerritoriesResponseDTO {
  sects: SectTerritorySummaryDTO[];
}

export interface InstitutionalPresenceGovernanceDTO {
  controller_kind: string;
  controller_id: string;
  administrative_capacity: number;
}

export interface InstitutionalPresenceSectInfluenceDTO {
  sect_id: number;
  sect_name: string;
  color: string;
  owned_tile_count: number;
  share: number;
}

export interface InstitutionalPresenceRegionDTO {
  region_id: number;
  region_name: string;
  region_type: string;
  tile_count: number;
  governance: InstitutionalPresenceGovernanceDTO | null;
  sect_influences: InstitutionalPresenceSectInfluenceDTO[];
  dominant_sect_id: number | null;
}

export interface InstitutionalPresenceResponseDTO {
  regions: InstitutionalPresenceRegionDTO[];
}

export interface TrackedMortalDTO {
  id: string;
  name: string;
  gender: string;
  age: number;
  born_region_id: number;
  born_region_name: string;
  parents: string[];
  is_awakening_candidate: boolean;
}

export interface MortalCityOverviewDTO {
  id: number;
  name: string;
  population: number;
  population_capacity: number;
  natural_growth: number;
}

export interface MortalOverviewResponseDTO {
  summary: {
    total_population: number;
    total_population_capacity: number;
    total_natural_growth: number;
    tracked_mortal_count: number;
    awakening_candidate_count: number;
  };
  cities: MortalCityOverviewDTO[];
  tracked_mortals: TrackedMortalDTO[];
}

export interface DynastyOverviewResponseDTO {
  name: string;
  title: string;
  royal_surname: string;
  royal_house_name: string;
  desc: string;
  effect_desc: string;
  style_tag: string;
  official_preference_label: string;
  is_low_magic: boolean;
  current_emperor?: {
    id: string;
    name: string;
    age: number;
    max_age: number;
    is_mortal: boolean;
  } | null;
  royal_house_member_ids: string[];
  royal_blood_member_ids: string[];
}

export interface DynastyOfficialDTO {
  id: string;
  name: string;
  realm: string;
  official_rank_key: string;
  official_rank_name: string;
  court_reputation: number;
  sect_name: string;
}

export interface DynastyDetailResponseDTO {
  overview: DynastyOverviewResponseDTO;
  summary: {
    official_count: number;
    top_official_rank_name: string;
  };
  officials: DynastyOfficialDTO[];
  imperial_crisis: {
    kind: 'challenge' | 'succession' | string;
    status: string;
    opened_month: number;
    incumbent: { id: string; name: string } | null;
    claims: Array<{
      candidate: { id: string; name: string };
      position: string;
      status: string;
      winner: boolean;
      support_count: number;
      supporters: Array<{ id: string; name: string }>;
      political_positions: Record<string, string>;
      evaluations: Array<Record<string, unknown>>;
      evidence_event_ids: string[];
    }>;
  } | null;
}

// --- Deceased Characters ---

export interface DeceasedRecordDTO {
  id: string;
  name: string;
  gender: string;
  age_at_death: number;
  realm_at_death: string;
  stage_at_death: string;
  death_reason: string;
  death_time: number;
  sect_name_at_death: string;
  alignment_at_death: string;
  backstory: string | null;
  custom_pic_id: number | null;
}

export interface DeceasedListResponseDTO {
  deceased: DeceasedRecordDTO[];
}

export interface AvatarOverviewSummaryDTO {
  total_count: number;
  alive_count: number;
  dead_count: number;
  sect_member_count: number;
  rogue_count: number;
}

export interface AvatarRealmDistributionItemDTO {
  realm: string;
  realm_id?: string;
  count: number;
}

export interface AvatarOverviewResponseDTO {
  summary: AvatarOverviewSummaryDTO;
  realm_distribution: AvatarRealmDistributionItemDTO[];
}

export type ToastLevel = 'error' | 'warning' | 'success' | 'info' | string;
export type AppLanguage = AppLocale | string;

export interface ToastSocketMessage {
  type: 'toast';
  level: ToastLevel;
  message: string;
  language?: AppLanguage;
}

export interface LLMConfigRequiredSocketMessage {
  type: 'llm_config_required';
  error?: string;
}

export interface GameReinitializedSocketMessage {
  type: 'game_reinitialized';
  message?: string;
}

export interface PongSocketMessage {
  type: 'pong';
}

export type SocketMessageDTO =
  | TickPayloadDTO
  | AvatarDeltaSocketMessage
  | ToastSocketMessage
  | LLMConfigRequiredSocketMessage
  | GameReinitializedSocketMessage;

export type SocketServerMessageDTO = SocketMessageDTO | PongSocketMessage;
