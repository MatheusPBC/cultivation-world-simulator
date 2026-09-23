import type { CausalView, CreateRequest, EventsView, LoadRequest, ObservatoryView, OptionsView,
  SaveRequest, SaveView, SpeedRequest, StatusView, ResearchView, DiplomacyView, DossierView } from '../types/medieval-api'

type Queries = { status: StatusView; options: OptionsView; observatory: ObservatoryView; research: ResearchView; diplomacy: DiplomacyView; saves: SaveView[]; events: EventsView }
type Commands = { create: CreateRequest; step: Record<string, never>; pause: Record<string, never>;
  resume: Record<string, never>; speed: SpeedRequest; save: SaveRequest; load: LoadRequest }
export type Command = keyof Commands
export type Reply<T> = { ok: true; data: T; revision: number }
export class ApiError extends Error {
  readonly code: string
  constructor(code: string, message: string) { super(message); this.code = code }
}
export function asError(error: unknown): ApiError {
  return error instanceof ApiError ? error : new ApiError('NETWORK_ERROR', 'Sem conexão com o mundo. Tente atualizar novamente.')
}
async function request<T>(path: string, body?: unknown): Promise<Reply<T>> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 30000)
  try {
    const response = await fetch('/api/v2/' + path, {
      method: body === undefined ? 'GET' : 'POST', signal: controller.signal,
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    let value: unknown
    try { value = await response.json() } catch { throw new ApiError('INVALID_RESPONSE', 'Resposta inválida do servidor.') }
    if (!value || typeof value !== 'object') throw new ApiError('INVALID_RESPONSE', 'Resposta inválida do servidor.')
    const envelope = value as { ok?: boolean; revision?: number; data?: T; error?: { code?: string; message?: string } }
    if (!response.ok || envelope.ok !== true) throw new ApiError(
      envelope.error?.code ?? 'HTTP_ERROR', envelope.error?.message ?? 'Não foi possível concluir a operação.')
    if (!Number.isInteger(envelope.revision) || envelope.data === undefined) throw new ApiError('INVALID_RESPONSE', 'Resposta incompleta do servidor.')
    return envelope as Reply<T>
  } catch (error) { throw asError(error) } finally { clearTimeout(timeout) }
}
export const api = {
  query<K extends keyof Queries>(name: K, params = '') { return request<Queries[K]>('query/' + name + params) },
  causal(id: string, after = 0) { return request<CausalView>('query/causal/' + encodeURIComponent(id) + '?after=' + after) },
  dossier(actorKind: string, actorId: string) {
    return request<DossierView>('query/dossier/' + encodeURIComponent(actorKind) + '/' + encodeURIComponent(actorId))
  },
  command<K extends Command>(name: K, body: Commands[K]) { return request<StatusView>('command/' + name, body) },
}
