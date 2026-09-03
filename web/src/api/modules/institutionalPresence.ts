import { httpClient } from '../http'
import type { InstitutionalPresenceResponseDTO } from '@/types/api'
import { mapInstitutionalPresenceDTO } from '../mappers/institutionalPresence'

export const institutionalPresenceApi = {
  async fetch() {
    const data = await httpClient.get<InstitutionalPresenceResponseDTO>(
      '/api/v1/query/world/institutional-presence',
    )
    return mapInstitutionalPresenceDTO(data)
  },
}
