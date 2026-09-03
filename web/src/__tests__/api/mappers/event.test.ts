import { describe, it, expect } from 'vitest'
import { mapEventDtoToGameEvent, normalizeEventCausalDetail } from '@/api/mappers/event'
import type { DecisionAppraisalDTO, EventCausalDetailDTO, EventDTO, MetricReadingDTO } from '@/types/api'

const baseEvent = { id: 'e1' } as EventDTO

describe('mapEventDtoToGameEvent', () => {
  it('preserves fact kind and causal origin', () => {
    const event = {
      id: 'event-1',
      text: 'An actor changed the world',
      content: 'An actor changed the world',
      year: 1,
      month: 1,
      month_stamp: 12,
      related_avatar_ids: [],
      subjects: [],
      is_major: false,
      is_story: false,
      created_at: 1,
      fact_kind: 'state_transition',
      causal_origin: 'actor_decision',
    } satisfies EventDTO

    const mapped = mapEventDtoToGameEvent(event)

    expect(mapped.factKind).toBe('state_transition')
    expect(mapped.causalOrigin).toBe('actor_decision')
  })
})

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
    expect(result?.measurements).toEqual([])
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
      measurements: [],
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

  it('passes through a well-formed measurements list', () => {
    const measurements: MetricReadingDTO[] = [{
      key: { dimension: 'load', subject_kind: 'region', subject_id: 'r1', concept_id: 'settlement' },
      derived_from: [],
      value: 0.75,
      unit: 'ratio',
      availability: 'measurable',
      reading_kind: 'derived',
      confidence: null,
      state_refs: ['region:r1:population'],
      source_event_ids: ['event-1'],
    }]
    const input: EventCausalDetailDTO = {
      event: baseEvent,
      causes: [],
      effects: [],
      deltas: [],
      measurements,
      decision: null,
      decision_appraisals: [],
      truncated: false,
    }

    const result = normalizeEventCausalDetail(input)

    expect(result?.measurements).toEqual(measurements)
  })

  it('defaults a non-array measurements value to an empty array', () => {
    const input = {
      event: baseEvent,
      causes: [],
      effects: [],
      deltas: [],
      decision: null,
      measurements: { value: 1 },
    } as unknown as EventCausalDetailDTO

    const result = normalizeEventCausalDetail(input)

    expect(result?.measurements).toEqual([])
  })
})
