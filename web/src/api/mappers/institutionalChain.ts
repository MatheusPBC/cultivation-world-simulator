import type { InstitutionalChainResponseDTO } from '@/types/api'

export interface InstitutionalChain {
  owner: { kind: string; id: string; institutionId: string; name: string; regionId: string | null }
  currentMonth: number
  institutions: InstitutionalChainResponseDTO['institutions']
  commitments: InstitutionalChainResponseDTO['commitments']
  events: InstitutionalChainResponseDTO['events']
  memories: InstitutionalChainResponseDTO['memories']
  commitmentCursor: { next: string | null; hasMore: boolean }
  eventCursor: { next: string | null; hasMore: boolean }
}

export function mapInstitutionalChainDTO(value: InstitutionalChainResponseDTO): InstitutionalChain {
  if (!value?.owner || !Array.isArray(value.institutions) || !Array.isArray(value.commitments) || !Array.isArray(value.events) || !Array.isArray(value.memories) || !value.cursor?.commitments || !value.cursor?.events || typeof value.current_month !== 'number') throw new Error('Cadeia institucional inválida')
  return { owner: { kind: value.owner.kind, id: value.owner.id, institutionId: value.owner.institution_id, name: value.owner.name, regionId: value.owner.region_id }, currentMonth: value.current_month, institutions: value.institutions ?? [], commitments: value.commitments, events: value.events, memories: value.memories ?? [], commitmentCursor: { next: value.cursor?.commitments?.next ?? null, hasMore: Boolean(value.cursor?.commitments?.has_more) }, eventCursor: { next: value.cursor?.events?.next ?? null, hasMore: Boolean(value.cursor?.events?.has_more) } }
}
