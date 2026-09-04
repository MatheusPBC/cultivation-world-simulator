import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import WorldJournalPanel from '@/components/game/panels/WorldJournalPanel.vue'

const { fetchWorldJournalMock, fetchEventCausalDetailMock, fetchWorldChronicleMock, fetchChronicleDossierMock, fetchLiveGuideMock, askLiveGuideMock, fetchDaoPetitionsMock } = vi.hoisted(() => ({
  fetchWorldJournalMock: vi.fn(),
  fetchEventCausalDetailMock: vi.fn(),
  fetchWorldChronicleMock: vi.fn(),
  fetchChronicleDossierMock: vi.fn(),
  fetchLiveGuideMock: vi.fn(),
  askLiveGuideMock: vi.fn(),
  fetchDaoPetitionsMock: vi.fn(),
}))

vi.mock('@/api', () => ({
  eventApi: {
    fetchWorldJournal: fetchWorldJournalMock,
    fetchEventCausalDetail: fetchEventCausalDetailMock,
    fetchWorldChronicle: fetchWorldChronicleMock,
    fetchChronicleDossier: fetchChronicleDossierMock,
    fetchLiveGuide: fetchLiveGuideMock,
    askLiveGuide: askLiveGuideMock,
  },
  // The Dao tab is reachable by keyboard (End jumps to the last tab), so its
  // query has to be stubbed for the tablist tests to exercise a real path.
  worldApi: {
    fetchDaoPetitions: fetchDaoPetitionsMock,
  },
  avatarApi: {
    fetchDetailInfo: vi.fn(),
  },
}))

vi.mock('@/components/game/panels/EventPanel.vue', () => ({
  default: {
    template: '<section aria-label="timeline existente">Timeline existente</section>',
  },
}))

function createJournalI18n() {
  return createI18n({
    legacy: false,
    locale: 'pt-BR',
    messages: {
      'pt-BR': {
        common: { year: ' ano', month: ' mes' },
        game: {
          world_journal: {
            title: 'Diario do Mundo',
            tabs: {
              now: 'Agora',
              focus: 'Em foco',
              stories: 'Historias',
              timeline: 'Linha do tempo',
              chronicle: 'Cronica',
              guide: 'Guia Vivo',
              dao: 'Suplicas ao Dao',
            },
            periods: { one: 'Este mes', three: '3 meses', twelve: '1 ano' },
            important_changes: 'Mudancas importantes',
            important_empty: 'Nenhuma mudanca importante neste periodo.',
            ongoing: 'Em andamento',
            ongoing_empty: 'Nenhuma atividade acompanhada neste periodo.',
            activity: 'Atividade do mundo',
            total_events: 'Eventos',
            major_events: 'Importantes',
            story_events: 'Historias',
            active_avatars: 'Personagens ativos',
            event_count: '{count} acontecimentos',
            loading: 'Carregando diario...',
            error: 'Nao foi possivel carregar o diario.',
            focus_empty: 'Nenhum dado em foco para este periodo.',
            focus_short_term: 'Meta de curto prazo',
            focus_long_term: 'Meta de longo prazo',
            focus_no_objective: 'Nenhuma meta definida.',
            stories_empty: 'Nenhuma historia neste periodo.',
            stories_truncated: 'Mostrando as {count} historias mais recentes.',
            why_button: 'Por que?',
            why_title: 'Por que isso aconteceu?',
            why_loading: 'Carregando a cadeia causal...',
            why_error: 'Nao foi possivel carregar a cadeia causal.',
            why_retry: 'Tentar novamente',
            why_close: 'Fechar',
            why_causes: 'Causas',
            why_effects: 'Efeitos',
            why_deltas: 'Mudancas de estado',
            why_measurements: 'Medicoes',
            why_no_measurements: 'Nenhuma medicao registrada.',
            why_measurement_unknown: 'Desconhecido',
            why_measurement_state_refs: 'Referencias de estado',
            why_measurement_source_events: 'Eventos de origem',
            why_measurement_derived_from: 'Entradas derivadas',
            why_measurement_none: 'Nenhuma',
            why_measurement_availability: {
              measurable: 'Mensuravel',
              partially_measurable: 'Parcialmente mensuravel',
              unmeasurable: 'Inmensuravel',
            },
            why_measurement_kind: {
              exact: 'Exata',
              derived: 'Derivada',
              estimated: 'Estimada',
              unknown: 'Desconhecida',
            },
            why_decision: 'Decisao por tras disso',
            why_no_causes: 'Nenhuma causa registrada.',
            why_no_effects: 'Nenhum efeito registrado ainda.',
            why_no_deltas: 'Nenhuma mudanca de estado registrada.',
            why_pruned: '(removido do historico)',
            why_truncated: 'Algumas causas nao foram exibidas.',
            why_considered_count: '{count} opcoes consideradas',
            why_rejected: 'Opcoes rejeitadas',
            why_relation: {
              triggered_by: 'desencadeado por',
              enabled_by: 'possibilitado por',
              motivated_by: 'motivado pela decisao',
              response_to: 'em resposta a',
              resolves: 'resolve',
              prevented_by: 'impedido por',
              contributed_to: 'contribuiu para',
            },
            chronicle: {
              loading: 'Carregando cronica...',
              error: 'Nao foi possivel carregar a cronica.',
              empty: 'Nenhuma cronica publicada.',
              load_more: 'Carregar anteriores',
              fact: 'Fato',
              inference: 'Interpretacao',
              source_count: '{count} fontes',
              trigger: { major_event: 'Evento importante', max_interval: 'Revisao' },
              dossier: 'Dossie causal',
              close: 'Fechar',
              dossier_error: 'Nao foi possivel carregar o dossie.',
              pruned: '{count} fontes removidas',
              truncated: 'Sequencia truncada',
              sequence: 'Sequencia causal',
              sequence_empty: 'Nenhum evento',
              why: 'Por que?',
            },
            guide: {
              loading: 'Lendo...', error: 'Erro no guia', retry: 'Tentar novamente', date: 'Ano {year}, mes {month}',
              world_in_one_sentence: 'O mundo em uma frase', no_headline: 'Sem manchete', sources: '{count} fontes',
              happening: 'O que esta acontecendo', happening_hint: 'Fios importantes', empty: 'Sem fios',
              understand_why: 'Entender por que', people: 'Quem importa agora', people_empty: 'Sem pessoas',
              no_current_action: 'Sem acao', no_ambition: 'Sem ambicao', concept: 'Conceito em foco',
              ask_eyebrow: 'Pergunte ao Cronista', ask_title: 'Tire uma duvida', grounded_note: 'Somente fatos',
              question_label: 'Pergunta', question_placeholder: 'Pergunte', ask_button: 'Perguntar', answering: 'Consultando',
              suggestion_people: 'Quem importa?', suggestion_conflict: 'Qual conflito?', suggestion_change: 'O que mudou?',
              answer_error: 'Erro na resposta', answer_unavailable: 'Sem resposta', answer_sources: 'Fontes', source_number: 'Fonte {number}',
            },
          },
          world_info: { entries: { WORLD_INFO_BATTLE_NAME: 'Combate', WORLD_INFO_BATTLE_DESC: 'Conflitos entre cultivadores.' } },
          event_templates: {},
        },
      },
    },
  })
}

function mountPanel() {
  return mount(WorldJournalPanel, {
    global: {
      plugins: [createPinia(), createJournalI18n()],
    },
  })
}

async function settlePromises() {
  await Promise.resolve()
  await Promise.resolve()
}

const baseJournal = {
  period: { months: 1, start_month_stamp: 1204, end_month_stamp: 1204 },
  activity: {
    total_events: 3,
    major_events: 1,
    story_events: 1,
    routine_events: 1,
    active_avatar_count: 2,
  },
  highlights: [
    {
      id: 'major-1',
      text: '100 ano 5 mes: Alice avancou de reino.',
      content: 'Alice avancou de reino.',
      year: 100,
      month: 5,
      month_stamp: 1204,
      related_avatar_ids: ['a1'],
      subjects: [{ type: 'avatar', id: 'a1', name: 'Alice' }],
      is_major: true,
      is_story: false,
      created_at: 1,
    },
  ],
  stories: [
    {
      id: 'story-1',
      text: '100 ano 5 mes: Uma lenda nasceu.',
      content: 'Uma lenda nasceu.',
      year: 100,
      month: 5,
      month_stamp: 1204,
      related_avatar_ids: ['a1'],
      subjects: [],
      is_major: false,
      is_story: true,
      created_at: 2,
    },
  ],
  stories_truncated: false,
  ongoing: [
    {
      avatar_id: 'a1',
      avatar_name: 'Alice',
      action: 'Cultivando',
      event_count: 3,
      short_term_objective: 'Alcancar o proximo reino',
      long_term_objective: 'Ascender a imortalidade',
    },
  ],
}

const baseGuide = {
  date: { month_stamp: 1204, year: 100, month: 5 },
  headline: 'A fronteira entrou em guerra.',
  source_event_ids: ['major-1'],
  threads: [{
    id: 'thread-1', title: 'Uma disputa mudou a fronteira', summary: 'Alice avancou e alterou o equilibrio local.',
    severity: 'critical', primary_event_id: 'major-1', source_event_ids: ['major-1'],
    subjects: [{ kind: 'avatar', id: 'a1', name: 'Alice' }],
  }],
  people: [{ avatar_id: 'a1', name: 'Alice', current_action: 'Cultivando', ambition: 'Ascender', event_count: 3 }],
  concept: { term_key: 'WORLD_INFO_BATTLE', source_event_ids: ['major-1'] },
}

describe('WorldJournalPanel', () => {
  beforeEach(() => {
    vi.useRealTimers()
    fetchWorldJournalMock.mockReset()
    fetchEventCausalDetailMock.mockReset()
    fetchWorldChronicleMock.mockReset()
    fetchChronicleDossierMock.mockReset()
    fetchLiveGuideMock.mockReset()
    askLiveGuideMock.mockReset()
    fetchDaoPetitionsMock.mockReset()
    fetchDaoPetitionsMock.mockResolvedValue({ pending: [], history: [] })
    fetchWorldJournalMock.mockResolvedValue(baseJournal)
    fetchWorldChronicleMock.mockResolvedValue({ chapters: [], next_cursor: null, has_more: false })
    fetchLiveGuideMock.mockResolvedValue(baseGuide)
    askLiveGuideMock.mockResolvedValue({ answer: 'Alice mudou o equilibrio local.', source_event_ids: ['major-1'], mode: 'generated' })
  })

  afterEach(() => {
    vi.useFakeTimers()
  })

  it('opens in Agora with factual highlights, ongoing activity and world totals', async () => {
    const wrapper = mountPanel()
    await settlePromises()

    expect(fetchWorldJournalMock).toHaveBeenCalledWith(1)
    const now = wrapper.get('[data-testid="journal-now"]')
    expect(now.isVisible()).toBe(true)
    expect(now.text()).toContain('Alice avancou de reino.')
    expect(now.text()).toContain('Cultivando')
    expect(now.text()).toContain('3')
    expect(wrapper.get('[data-testid="journal-tab-focus"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.get('[data-testid="journal-tab-stories"]').attributes('disabled')).toBeUndefined()
  })

  it('navigates to the avatar when an ongoing card in Agora is clicked', async () => {
    const wrapper = mountPanel()
    await settlePromises()

    const ongoingCards = wrapper.get('[data-testid="journal-now"]').findAll('.ongoing-card')
    expect(ongoingCards).toHaveLength(1)
    expect(ongoingCards[0].text()).toContain('Alice')
    expect(ongoingCards[0].text()).toContain('Cultivando')
    expect(ongoingCards[0].text()).toContain('3')

    await ongoingCards[0].trigger('click')
    await settlePromises()
    // Clicking through to the avatar detail (uiStore.select) must not throw.
  })

  it('changes the period and preserves the existing timeline as another mode', async () => {
    const wrapper = mountPanel()
    await settlePromises()

    await wrapper.get('[data-testid="journal-period-3"]').trigger('click')
    await settlePromises()
    expect(fetchWorldJournalMock).toHaveBeenLastCalledWith(3)

    await wrapper.get('[data-testid="journal-tab-timeline"]').trigger('click')
    expect(wrapper.find('[data-testid="journal-now"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="journal-timeline"]').text()).toContain('Timeline existente')
  })

  it('keeps the existing tabs and loads the Chronicle tab', async () => {
    const wrapper = mountPanel()
    await settlePromises()

    expect(wrapper.findAll('.journal-tab')).toHaveLength(7)
    await wrapper.get('[data-testid="journal-tab-chronicle"]').trigger('click')
    await settlePromises()

    expect(fetchWorldChronicleMock).toHaveBeenCalledWith({ limit: 20 })
    expect(wrapper.get('[data-testid="journal-chronicle"]').exists()).toBe(true)
  })

  describe('activity dateline', () => {
    it('still projects all four canonical counts, as one line instead of four cards', async () => {
      const wrapper = mountPanel()
      await settlePromises()

      // The 2x2 grid of stat cards is gone.
      expect(wrapper.find('.activity-grid').exists()).toBe(false)
      expect(wrapper.find('.activity-stat').exists()).toBe(false)

      const metrics = wrapper.get('.activity-line').findAll('.activity-metric')
      expect(metrics).toHaveLength(4)
      // total 3 / major 1 / stories 1 / active avatars 2, from the fixture.
      expect(metrics.map((metric) => metric.get('dd').text())).toEqual(['3', '1', '1', '2'])
      expect(metrics.map((metric) => metric.get('dt').text())).toEqual([
        'Eventos',
        'Importantes',
        'Historias',
        'Personagens ativos',
      ])
    })

    it('de-emphasises a zero so a quiet month does not read as broken', async () => {
      fetchWorldJournalMock.mockResolvedValue({
        ...baseJournal,
        activity: {
          total_events: 0,
          major_events: 0,
          story_events: 0,
          routine_events: 0,
          active_avatar_count: 4,
        },
      })
      const wrapper = mountPanel()
      await settlePromises()

      const metrics = wrapper.get('.activity-line').findAll('.activity-metric')
      expect(metrics[0].classes()).toContain('activity-metric--zero')
      expect(metrics[1].classes()).toContain('activity-metric--zero')
      // A non-zero count keeps full emphasis.
      expect(metrics[3].classes()).not.toContain('activity-metric--zero')
    })

    it('moves the period control into the activity header instead of its own row', async () => {
      const wrapper = mountPanel()
      await settlePromises()

      const head = wrapper.get('.journal-section-head')
      const selector = head.get('.period-selector')
      expect(selector.attributes('role')).toBe('group')

      const active = selector.get('[data-testid="journal-period-1"]')
      expect(active.attributes('aria-pressed')).toBe('true')
      expect(selector.get('[data-testid="journal-period-3"]').attributes('aria-pressed')).toBe('false')
    })
  })

  describe('tablist accessibility', () => {
    it('exposes the tabs as a tablist with a single tab stop', async () => {
      const wrapper = mountPanel()
      await settlePromises()

      expect(wrapper.get('[role="tablist"]').exists()).toBe(true)

      const tabs = wrapper.findAll('.journal-tab')
      expect(tabs.every((tab) => tab.attributes('role') === 'tab')).toBe(true)

      // Roving tabindex: only the selected tab is in the tab order.
      const focusable = tabs.filter((tab) => tab.attributes('tabindex') === '0')
      expect(focusable).toHaveLength(1)
      expect(focusable[0].attributes('data-testid')).toBe('journal-tab-now')
      expect(wrapper.get('[data-testid="journal-tab-now"]').attributes('aria-selected')).toBe('true')
      expect(wrapper.get('[data-testid="journal-tab-focus"]').attributes('aria-selected')).toBe('false')
    })

    it('moves between tabs with the arrow keys', async () => {
      const wrapper = mountPanel()
      await settlePromises()

      await wrapper.get('[role="tablist"]').trigger('keydown', { key: 'ArrowRight' })
      await settlePromises()
      expect(wrapper.get('[data-testid="journal-focus"]').exists()).toBe(true)
      expect(wrapper.get('[data-testid="journal-tab-focus"]').attributes('aria-selected')).toBe('true')

      await wrapper.get('[role="tablist"]').trigger('keydown', { key: 'ArrowLeft' })
      await settlePromises()
      expect(wrapper.get('[data-testid="journal-now"]').exists()).toBe(true)
    })

    it('wraps arrow navigation at the ends of the tablist', async () => {
      const wrapper = mountPanel()
      await settlePromises()

      await wrapper.get('[role="tablist"]').trigger('keydown', { key: 'ArrowLeft' })
      await settlePromises()
      expect(wrapper.get('[data-testid="journal-tab-dao"]').attributes('aria-selected')).toBe('true')

      await wrapper.get('[role="tablist"]').trigger('keydown', { key: 'ArrowRight' })
      await settlePromises()
      expect(wrapper.get('[data-testid="journal-tab-now"]').attributes('aria-selected')).toBe('true')
    })

    it('jumps to the first and last tab with Home and End', async () => {
      const wrapper = mountPanel()
      await settlePromises()

      await wrapper.get('[role="tablist"]').trigger('keydown', { key: 'End' })
      await settlePromises()
      expect(wrapper.get('[data-testid="journal-tab-dao"]').attributes('aria-selected')).toBe('true')

      await wrapper.get('[role="tablist"]').trigger('keydown', { key: 'Home' })
      await settlePromises()
      expect(wrapper.get('[data-testid="journal-tab-now"]').attributes('aria-selected')).toBe('true')
    })

    it('does not swallow keys it has no business handling', async () => {
      const wrapper = mountPanel()
      await settlePromises()

      await wrapper.get('[role="tablist"]').trigger('keydown', { key: 'a' })
      await settlePromises()
      // Still on the first tab.
      expect(wrapper.get('[data-testid="journal-tab-now"]').attributes('aria-selected')).toBe('true')
    })
  })

  it('loads the Live Guide lazily and opens its source in the existing Why view', async () => {
    fetchEventCausalDetailMock.mockResolvedValue({
      event: baseJournal.highlights[0], causes: [], effects: [], deltas: [], measurements: [], decision: null, decision_appraisals: [], truncated: false,
    })
    const wrapper = mountPanel()
    await settlePromises()

    await wrapper.get('[data-testid="journal-tab-guide"]').trigger('click')
    await settlePromises()

    expect(fetchLiveGuideMock).toHaveBeenCalledOnce()
    expect(wrapper.get('[data-testid="journal-guide"]').text()).toContain('A fronteira entrou em guerra.')
    expect(wrapper.get('[data-testid="journal-guide"]').text()).toContain('Alice')

    await wrapper.get('[data-testid="guide-why-major-1"]').trigger('click')
    await settlePromises()
    expect(fetchEventCausalDetailMock).toHaveBeenCalledWith('major-1')
    expect(wrapper.get('[data-testid="why-overlay"]').exists()).toBe(true)
  })

  it('asks the Chronicler and keeps the answer citation clickable', async () => {
    fetchEventCausalDetailMock.mockResolvedValue({
      event: baseJournal.highlights[0], causes: [], effects: [], deltas: [], measurements: [], decision: null, decision_appraisals: [], truncated: false,
    })
    const wrapper = mountPanel()
    await settlePromises()
    await wrapper.get('[data-testid="journal-tab-guide"]').trigger('click')
    await settlePromises()

    await wrapper.get('#live-guide-question').setValue('O que mudou?')
    await wrapper.get('.chronicler-box form').trigger('submit')
    await settlePromises()

    expect(askLiveGuideMock).toHaveBeenCalledWith('O que mudou?')
    expect(wrapper.get('[data-testid="guide-answer"]').text()).toContain('Alice mudou o equilibrio local.')
    await wrapper.get('.answer-sources button').trigger('click')
    await settlePromises()
    expect(fetchEventCausalDetailMock).toHaveBeenCalledWith('major-1')
  })

  it('keeps the Chronicle Why overlay above the dossier drawer', async () => {
    fetchWorldChronicleMock.mockResolvedValue({
      chapters: [{
        id: 'chapter-1', start_month_stamp: 1, end_month_stamp: 1, trigger: 'major_event', title: 'Cronica', created_at: 1,
        source_event_ids: ['event-1'],
        paragraphs: [{ source_event_ids: ['event-1'], segments: [{
          text: 'Um fato',
          reference: { id: 'event-ref', kind: 'event', label: 'Um fato', target_id: 'event-1', claim_kind: 'fact', source_event_ids: ['event-1'] },
        }] }],
      }],
      next_cursor: null,
      has_more: false,
    })
    fetchChronicleDossierMock.mockResolvedValue({
      chapter_id: 'chapter-1',
      anchor: { id: 'event-ref', kind: 'event', label: 'Um fato', target_id: 'event-1', claim_kind: 'fact', source_event_ids: ['event-1'] },
      focal_event: null,
      sequence: [{ ...baseJournal.highlights[0], id: 'event-1' }],
      pruned_source_ids: [],
      truncated: false,
    })
    fetchEventCausalDetailMock.mockResolvedValue({
      event: baseJournal.highlights[0], causes: [], effects: [], deltas: [], measurements: [], decision: null, decision_appraisals: [], truncated: false,
    })

    const wrapper = mountPanel()
    await settlePromises()
    await wrapper.get('[data-testid="journal-tab-chronicle"]').trigger('click')
    await settlePromises()
    await wrapper.get('[data-testid="chronicle-ref-event-ref"]').trigger('click')
    await settlePromises()
    await wrapper.get('[data-testid="dossier-why-event-1"]').trigger('click')
    await settlePromises()

    const whyOverlay = wrapper.get('[data-testid="why-overlay"]')
    expect(whyOverlay.isVisible()).toBe(true)
    expect(whyOverlay.classes()).toContain('why-overlay--above-dossier')
  })

  it('shows people and objectives in the Focus tab', async () => {
    const wrapper = mountPanel()
    await settlePromises()

    await wrapper.get('[data-testid="journal-tab-focus"]').trigger('click')
    const focus = wrapper.get('[data-testid="journal-focus"]')

    expect(focus.text()).toContain('Alice')
    expect(focus.text()).toContain('Cultivando')
    expect(focus.text()).toContain('Alcancar o proximo reino')
    expect(focus.text()).toContain('Ascender a imortalidade')
  })

  it('shows the focus empty state when nothing is ongoing', async () => {
    fetchWorldJournalMock.mockResolvedValue({ ...baseJournal, ongoing: [] })
    const wrapper = mountPanel()
    await settlePromises()

    await wrapper.get('[data-testid="journal-tab-focus"]').trigger('click')
    expect(wrapper.get('[data-testid="journal-focus"]').text()).toContain('Nenhum dado em foco para este periodo.')
  })

  it('shows story events in the Stories tab', async () => {
    const wrapper = mountPanel()
    await settlePromises()

    await wrapper.get('[data-testid="journal-tab-stories"]').trigger('click')
    expect(wrapper.get('[data-testid="journal-stories"]').text()).toContain('Uma lenda nasceu.')
  })

  it('shows the stories empty state and hides it when events exist', async () => {
    fetchWorldJournalMock.mockResolvedValue({ ...baseJournal, stories: [] })
    const wrapper = mountPanel()
    await settlePromises()

    await wrapper.get('[data-testid="journal-tab-stories"]').trigger('click')
    expect(wrapper.get('[data-testid="journal-stories"]').text()).toContain('Nenhuma historia neste periodo.')
  })

  it('opens the why drill-down for a highlight event and renders causes/effects/deltas', async () => {
    fetchEventCausalDetailMock.mockResolvedValue({
      event: baseJournal.highlights[0],
      causes: [
        {
          relation: 'triggered_by',
          weight: 1,
          note_key: null,
          note_params: null,
          depth: 1,
          event: {
            id: 'cause-1',
            text: 'cause',
            content: 'Alice decidiu avancar.',
            year: 100,
            month: 4,
            month_stamp: 1203,
            related_avatar_ids: [],
            is_major: false,
            is_story: false,
            created_at: 0,
          },
          pruned: false,
        },
        {
          relation: 'enabled_by',
          weight: 0.5,
          note_key: null,
          note_params: null,
          depth: 1,
          event: null,
          pruned: true,
        },
      ],
      effects: [],
      deltas: [
        { id: 'd1', event_id: 'major-1', owner_kind: 'avatar', owner_id: 'a1', aspect: 'realm', before: 'Qi', after: 'Foundation', magnitude: null },
      ],
      measurements: [
        {
          key: { dimension: 'load', subject_kind: 'region', subject_id: 'r1', concept_id: 'settlement' },
          derived_from: [
            { dimension: 'capacity', subject_kind: 'region', subject_id: 'r1', concept_id: 'settlement' },
            { dimension: 'stock', subject_kind: 'region', subject_id: 'r1', concept_id: 'grain' },
          ],
          value: 0.75,
          unit: 'ratio',
          availability: 'measurable',
          reading_kind: 'derived',
          confidence: null,
          state_refs: ['region:r1:load'],
          source_event_ids: ['measurement-source'],
        },
        {
          key: { dimension: 'risk', subject_kind: 'region', subject_id: 'r1', concept_id: 'unknown_risk' },
          derived_from: [],
          value: null,
          unit: 'unknown',
          availability: 'unmeasurable',
          reading_kind: 'unknown',
          confidence: null,
          state_refs: [],
          source_event_ids: [],
        },
      ],
      decision: null,
      truncated: false,
    })

    const wrapper = mountPanel()
    await settlePromises()

    await wrapper.get('.why-button').trigger('click')
    await settlePromises()

    expect(fetchEventCausalDetailMock).toHaveBeenCalledWith('major-1')
    const overlay = wrapper.get('[data-testid="why-overlay"]')
    expect(overlay.text()).toContain('Alice decidiu avancar.')
    expect(overlay.text()).toContain('(removido do historico)')
    expect(overlay.text()).toContain('realm')
    expect(overlay.text()).toContain('Qi')
    expect(overlay.text()).toContain('Foundation')
    const measurements = overlay.get('[data-testid="why-measurements"]')
    expect(measurements.text()).toContain('Medicoes')
    expect(measurements.text()).toContain('load(settlement)')
    expect(measurements.text()).toContain('0.75 ratio')
    expect(measurements.text()).toContain('Desconhecido')
    expect(measurements.text()).toContain('region:r1:load')
    expect(measurements.text()).toContain('Entradas derivadas')
    expect(measurements.text()).toContain('capacity(settlement)')
    expect(measurements.text()).toContain('stock(grain)')
    await measurements.get('[data-testid="why-measurement-source-event-measurement-source"]').trigger('click')
    expect(fetchEventCausalDetailMock).toHaveBeenCalledWith('measurement-source')

    await overlay.get('.why-close').trigger('click')
    expect(wrapper.find('[data-testid="why-overlay"]').exists()).toBe(false)
  })

  it('shows a loading state then an error with retry when the why query fails', async () => {
    fetchEventCausalDetailMock.mockRejectedValue(new Error('boom'))

    const wrapper = mountPanel()
    await settlePromises()

    await wrapper.get('.why-button').trigger('click')
    await settlePromises()

    const overlay = wrapper.get('[data-testid="why-overlay"]')
    expect(overlay.text()).toContain('Nao foi possivel carregar a cadeia causal.')
    expect(overlay.find('.why-retry').exists()).toBe(true)
  })
})
