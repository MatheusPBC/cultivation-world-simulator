import { httpClient } from '../http'
import type { InstitutionalChainResponseDTO, InstitutionalOwnerKindDTO } from '@/types/api'
import { mapInstitutionalChainDTO } from '../mappers/institutionalChain'

export const institutionalChainApi = {
  async fetch(ownerKind: InstitutionalOwnerKindDTO, ownerId: string, params: { commitmentCursor?: string | null; eventCursor?: string | null; limit?: number; signal?: AbortSignal } = {}) {
    const query = new URLSearchParams({ owner_kind: ownerKind, owner_id: ownerId })
    if (params.commitmentCursor) query.set('commitment_cursor', params.commitmentCursor)
    if (params.eventCursor) query.set('event_cursor', params.eventCursor)
    if (params.limit) query.set('limit', String(params.limit))
    return mapInstitutionalChainDTO(await httpClient.get<InstitutionalChainResponseDTO>(`/api/v1/query/world/institutional-chain?${query}`, { signal: params.signal }))
  },
}
