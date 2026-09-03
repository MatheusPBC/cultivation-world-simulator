import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import RouteDetail from '@/components/game/panels/info/RouteDetail.vue'
import { useWorldJournalStore } from '@/stores/worldJournal'
import { useUiStore } from '@/stores/ui'
import { createTestI18n } from '@/__tests__/utils/i18n'

describe('RouteDetail', () => {
  it('renders causal route fields and opens source event why view', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const journalStore = useWorldJournalStore()
    journalStore.openCausalDetail = vi.fn()
    const uiStore = useUiStore()
    uiStore.select = vi.fn().mockResolvedValue(undefined)

    const wrapper = mount(RouteDetail, {
      props: {
        data: {
          id: 'route-1', endpointRegionIds: [1, 2], mode: 'land', capacity: 100,
          operationalCapacity: 64, quality: 0.8, enabled: true,
          allowedResourceIds: ['grain'], dependencySiteIds: ['bridge-1'],
          sourceEventIds: ['event-1'],
        },
      },
      global: {
        plugins: [pinia, createTestI18n({
          common: { yes: 'Sim', no: 'Não', none: 'Nenhum' },
          game: {
            info_panel: { route: {
              title: 'Rota causal', id: 'Identificador', mode: 'Modo', endpoints: 'Regiões conectadas',
              capacity_section: 'Capacidade operacional', capacity: 'Capacidade nominal',
              operational_capacity: 'Capacidade atual', quality: 'Qualidade', enabled: 'Ativa',
              references: 'Referências causais', allowed_resources: 'Recursos permitidos',
              dependency_sites: 'Sites de infraestrutura', source_events: 'Eventos de origem',
            } },
            world_journal: { why_button: 'Por quê?' },
          },
        })],
      },
    })

    expect(wrapper.text()).toContain('route-1')
    expect(wrapper.text()).toContain('100')
    expect(wrapper.text()).toContain('64')
    expect(wrapper.text()).toContain('bridge-1')

    await wrapper.get('[data-testid="route-open-why-event-1"]').trigger('click')
    expect(journalStore.openCausalDetail).toHaveBeenCalledWith('event-1')
    await wrapper.get('[data-testid="route-site-bridge-1"]').trigger('click')
    expect(uiStore.select).toHaveBeenCalledWith('site', 'bridge-1')
  })
})
