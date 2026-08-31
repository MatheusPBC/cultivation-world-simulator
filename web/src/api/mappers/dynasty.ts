import type { DynastyDetailResponseDTO, DynastyOverviewResponseDTO } from '@/types/api'
import type { DynastyDetail, DynastyOverview } from '@/types/core'

export function normalizeDynastyOverview(input: DynastyOverviewResponseDTO | null | undefined): DynastyOverview {
  return {
    name: String(input?.name ?? ''),
    title: String(input?.title ?? ''),
    royal_surname: String(input?.royal_surname ?? ''),
    royal_house_name: String(input?.royal_house_name ?? ''),
    desc: String(input?.desc ?? ''),
    effect_desc: String(input?.effect_desc ?? ''),
    style_tag: String(input?.style_tag ?? ''),
    official_preference_label: String(input?.official_preference_label ?? ''),
    is_low_magic: Boolean(input?.is_low_magic ?? true),
    current_emperor: input?.current_emperor
        ? {
          id: String(input.current_emperor.id ?? ''),
          name: String(input.current_emperor.name ?? ''),
          age: Number(input.current_emperor.age ?? 0),
          max_age: Number(input.current_emperor.max_age ?? 80),
          is_mortal: Boolean(input.current_emperor.is_mortal ?? true),
        }
      : null,
  }
}

export function normalizeDynastyDetail(input: DynastyDetailResponseDTO | null | undefined): DynastyDetail {
  return {
    overview: normalizeDynastyOverview(input?.overview),
    summary: {
      officialCount: Number(input?.summary?.official_count ?? 0),
      topOfficialRankName: String(input?.summary?.top_official_rank_name ?? ''),
    },
    officials: (input?.officials ?? []).map((item) => ({
      id: String(item?.id ?? ''),
      name: String(item?.name ?? ''),
      realm: String(item?.realm ?? ''),
      officialRankKey: String(item?.official_rank_key ?? ''),
      officialRankName: String(item?.official_rank_name ?? ''),
      courtReputation: Number(item?.court_reputation ?? 0),
      sectName: String(item?.sect_name ?? ''),
    })),
    imperialCrisis: input?.imperial_crisis ? {
      status: String(input.imperial_crisis.status ?? ''),
      openedMonth: Number(input.imperial_crisis.opened_month ?? 0),
      emperor: { id: String(input.imperial_crisis.emperor?.id ?? ''), name: String(input.imperial_crisis.emperor?.name ?? '') },
      claimant: { id: String(input.imperial_crisis.claimant?.id ?? ''), name: String(input.imperial_crisis.claimant?.name ?? '') },
      supportCount: Number(input.imperial_crisis.support_count ?? 0),
      supporters: (input.imperial_crisis.supporters ?? []).map((supporter) => ({
        id: String(supporter?.id ?? ''),
        name: String(supporter?.name ?? ''),
      })),
      evidenceEventIds: input.imperial_crisis.evidence_event_ids ?? [],
      legitimacyFactors: input.imperial_crisis.legitimacy_factors ?? {},
    } : null,
  }
}
