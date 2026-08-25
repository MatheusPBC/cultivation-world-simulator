import { describe, it, expect } from 'vitest'
import { normalizeEventCausalDetail } from '@/api/mappers/event'
import type { DecisionAppraisalDTO, EventCausalDetailDTO, EventDTO } from '@/types/api'

const baseEvent = { id: 'e1' } as EventDTO

describe('normalizeEventCausalDetail', () => {
  it('returns null when input has no event', () => {
    expect(normalizeEventCausalDetail(null)).toBeNull()
    expect(normalizeEventCausalDetail(undefined)).toBeNull()
    expect(normalizeEventCausalDetail({} as unknown as EventCausalDetailDTO)).toBeNull()
  })

  it('defaults decision_appraisals to an empty array when missing', () => {
    const input = {
      event: baseEvent,
      causes: [],
      effects: [],
      deltas: [],
      decision: null,
    } as unknown as EventCausalDetailDTO

    const result = normalizeEventCausalDetail(input)

    expect(result?.decision_appraisals).toEqual([])
  })

  it('passes through a well-formed decision_appraisals list', () => {
    const decisionAppraisals: DecisionAppraisalDTO[] = [
      {
        appraisal_id: 'ap-1',
        pruned: false,
        focus_avatar_id: 'a2',
        focus_avatar_name: 'Beta',
        primary_emotion: 'emotion_angry',
        emotion: { name: 'Anger', emoji: '😡', desc: 'Anger' },
        summary: 'He humiliated me.',
        valence: -0.8,
        source_event_id: 'ev-1',
        source_event_date: '100年1月',
      },
      {
        appraisal_id: 'ap-pruned',
        pruned: true,
        focus_avatar_id: '',
        focus_avatar_name: '',
        primary_emotion: '',
        emotion: null,
        summary: null,
        valence: null,
        source_event_id: '',
        source_event_date: '',
      },
    ]
    const input: EventCausalDetailDTO = {
      event: baseEvent,
      causes: [],
      effects: [],
      deltas: [],
      decision: null,
      decision_appraisals: decisionAppraisals,
      truncated: false,
    }

    const result = normalizeEventCausalDetail(input)

    expect(result?.decision_appraisals).toEqual(decisionAppraisals)
  })

  it('discards a non-array decision_appraisals value rather than throwing', () => {
    const input = {
      event: baseEvent,
      causes: [],
      effects: [],
      deltas: [],
      decision: null,
      decision_appraisals: 'not-an-array',
    } as unknown as EventCausalDetailDTO

    const result = normalizeEventCausalDetail(input)

    expect(result?.decision_appraisals).toEqual([])
  })
})
