import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import InfrastructureSiteDetail from '@/components/game/panels/info/InfrastructureSiteDetail.vue'
import { useWorldJournalStore } from '@/stores/worldJournal'
import { useUiStore } from '@/stores/ui'
import { createTestI18n } from '@/__tests__/utils/i18n'

describe('InfrastructureSiteDetail', () => {
  it('opens the causal why view from the last material change', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const journalStore = useWorldJournalStore()
    journalStore.openCausalDetail = vi.fn()
    const wrapper = mount(InfrastructureSiteDetail, {
      props: {
        data: {
          id: 'bridge-1', name: 'Ponte', kind: 'bridge', cellRefs: [[0, 0]], regionIds: [1, 2],
          routeIds: ['route-1'], waterBodyIds: ['river-1'], capabilityIds: ['transport'],
          ownerRef: null, maintainerRef: null, integrity: 0.5, enabled: true,
          status: 'impaired', x: 0, y: 0, clickable: true, lastEventId: 'event-1',
          sourceEventIds: ['event-1'],
        },
      },
      global: {
        plugins: [pinia, createTestI18n({
          common: { yes: 'Sim', no: 'Não', none: 'Nenhum' },
          game: {
            info_panel: { infrastructure_site: {
              title: 'Infraestrutura', kind: 'Tipo', status: 'Estado', integrity: 'Integridade',
              location: 'Local', enabled: 'Ativo', references: 'Referências', regions: 'Regiões',
              routes: 'Rotas', capabilities: 'Capacidades', owner: 'Dono', maintainer: 'Mantenedor',
              last_event: 'Último evento', status_values: { active: 'Ativo', impaired: 'Danificado', destroyed: 'Destruído' },
            } },
            world_journal: { why_button: 'Por quê?' },
          },
        })],
      },
    })

    await wrapper.get('[data-testid="infrastructure-site-open-why"]').trigger('click')

    expect(journalStore.openCausalDetail).toHaveBeenCalledWith('event-1')
  })

  it('navigates explicitly linked routes through the shared selection store', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const uiStore = useUiStore()
    uiStore.select = vi.fn().mockResolvedValue(undefined)

    const wrapper = mount(InfrastructureSiteDetail, {
      props: {
        data: {
          id: 'bridge-1', name: 'Ponte', kind: 'bridge', cellRefs: [[0, 0]], regionIds: [1, 2],
          routeIds: ['route-1'], waterBodyIds: [], capabilityIds: ['transport'],
          ownerRef: null, maintainerRef: null, integrity: 1, enabled: true,
          status: 'active', x: 0, y: 0, clickable: true, lastEventId: null,
        },
      },
      global: {
        plugins: [pinia, createTestI18n({
          common: { yes: 'Sim', no: 'Não', none: 'Nenhum' },
          game: { info_panel: { infrastructure_site: {
            title: 'Infraestrutura', kind: 'Tipo', status: 'Estado', integrity: 'Integridade',
            location: 'Local', enabled: 'Ativa', references: 'Referências', regions: 'Regiões',
            routes: 'Rotas', capabilities: 'Capacidades', owner: 'Dono', maintainer: 'Mantenedor',
            last_event: 'Último evento', status_values: { active: 'Ativa', impaired: 'Danificada', destroyed: 'Destruída' },
          } } },
        })],
      },
    })

    await wrapper.get('[data-testid="infrastructure-site-route-route-1"]').trigger('click')

    expect(uiStore.select).toHaveBeenCalledWith('route', 'route-1')
  })
})
