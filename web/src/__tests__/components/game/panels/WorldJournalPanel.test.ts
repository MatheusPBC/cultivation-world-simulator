import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import WorldJournalPanel from '@/components/game/panels/WorldJournalPanel.vue'

const { fetchWorldJournalMock } = vi.hoisted(() => ({
  fetchWorldJournalMock: vi.fn(),
}))

vi.mock('@/api', () => ({
  eventApi: {
    fetchWorldJournal: fetchWorldJournalMock,
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
            },
            coming_soon: 'Em breve',
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
          },
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

describe('WorldJournalPanel', () => {
  beforeEach(() => {
    vi.useRealTimers()
    fetchWorldJournalMock.mockReset()
    fetchWorldJournalMock.mockResolvedValue({
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
      ongoing: [
        {
          avatar_id: 'a1',
          avatar_name: 'Alice',
          action: 'Cultivando',
          event_count: 3,
        },
      ],
    })
  })

  afterEach(() => {
    vi.useFakeTimers()
  })

  it('opens in Agora with factual highlights, ongoing activity and world totals', async () => {
    const wrapper = mountPanel()
    await settlePromises()

    expect(fetchWorldJournalMock).toHaveBeenCalledWith(1)
    expect(wrapper.get('[data-testid="journal-now"]').isVisible()).toBe(true)
    expect(wrapper.text()).toContain('Alice avancou de reino.')
    expect(wrapper.text()).toContain('Cultivando')
    expect(wrapper.text()).toContain('3')
    expect(wrapper.get('[data-testid="journal-tab-focus"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="journal-tab-stories"]').attributes('disabled')).toBeDefined()
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
})
