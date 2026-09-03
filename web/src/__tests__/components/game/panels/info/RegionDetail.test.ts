import { mount } from '@vue/test-utils'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import RegionDetail from '@/components/game/panels/info/RegionDetail.vue'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { useWorldJournalStore } from '@/stores/worldJournal'

const sharedI18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      game: {
        info_panel: {
          region: {
            type_explanations: { normal: '普通区域说明', city: '城市说明' },
            regional_context_title: '区域态势',
            semantic_context: {
              conditions_title: '活动中的语义条件',
              readings_title: '关键读数',
              empty: '暂无可用语义上下文。',
              intensity: '强度 {value}',
              started_month: '始于第 {month} 月',
              definition: '定义 {id}',
              source_event: '来源事件 {id}',
              derived_from: '推导输入',
              group_id: '群组：{id}',
              unknown_value: '未知',
              confidence: '置信度 {value}%',
              availability: {
                measurable: '可测量',
                partially_measurable: '部分可测量',
                unmeasurable: '不可测量',
              },
              reading_kind: {
                exact: '精确',
                derived: '推导',
                estimated: '估计',
                unknown: '未知',
              },
            },
            economy: {
              title: '区域经济',
              stocks: '库存',
              capacities: '容量',
              production_rates: '生产速率',
              demand_rates: '需求速率',
              access: '可获得性',
              dependencies: '依赖度',
            },
            infrastructure: {
              title: '基础设施',
              capacities: '容量',
              quality: '质量',
            },
            city_state: {
              title: '城市状态',
              districts: '城区',
              assets: '城市资产',
              governance: '治理',
              population_weight: '人口占比：{value}',
              tiles: '地图格：{value}',
              capacity: '容量：{value}',
              quality: '质量：{value}',
              integrity: '完整度：{value}',
              urban_services: '城市服务',
              service_demands: '服务需求',
              demand_per_population: '人口需求：{value}',
              population_groups: '人口群组',
              group_population_weight: '群组人口权重：{value}',
              priorities: '服务优先级',
              priority_weight: '权重：{value}',
              controller: '管理者',
              administrative_capacity: '行政能力：{value}',
            },
            spiritual_ecology: {
              title: '灵性生态',
              grounding_label: '依据',
              essence: '灵气',
              densities: '五行密度',
              formations: '生效中的阵法',
              graves: '墓葬',
              treasures: '宝物',
              celestial_context: '天象背景',
              state_refs: '依据引用',
              grounding: {
                grounded: '有依据的事实',
                unknown: '依据未知',
              },
            },
            collective_health: {
              title: '群体健康',
              grounding_label: '依据',
              living_avatar_count: '存活修士',
              active_wounded_count: '当前受伤',
              hp_deficit: '生命值缺口',
              healing_capacity: '疗愈能力',
              healing_access: '疗愈可及性',
              injuries: '当前伤势',
              healing_assets: '疗愈资产',
              hp_lost: '损失生命值：{value}',
              capacity: '容量：{value}',
              state_refs: '状态引用',
            },
          },
        },
        world_journal: { why_button: '为什么？' },
      },
    },
  },
})

let pinia: ReturnType<typeof createPinia>

describe('RegionDetail', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
  })

  it('should render successfully', () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: {
        'zh-CN': {
          game: {
            population: '人口',
            mortal_system: {
              population_ratio_value: '{current} / {capacity} 万',
            },
            info_panel: {
              region: {
                type_explanations: {
                  city: '城市说明',
                  ruin: '遗迹说明',
                  cave: '洞府说明',
                  sect: '宗门说明',
                  normal: '普通区域说明',
                },
                dao_tradition: '天道诠释',
                dao_traditions: {
                  mandate_and_order: '天命与秩序',
                },
                regional_context_title: '区域态势',
                semantic_context: {
                  conditions_title: '活动中的语义条件',
                  readings_title: '关键读数',
                  empty: '暂无可用语义上下文。',
                  intensity: '强度 {value}',
                  started_month: '始于第 {month} 月',
                  definition: '定义 {id}',
                  source_event: '来源事件 {id}',
                  derived_from: '推导输入',
                  unknown_value: '未知',
                  confidence: '置信度 {value}%',
                  availability: {
                    measurable: '可测量',
                    partially_measurable: '部分可测量',
                    unmeasurable: '不可测量',
                  },
                  reading_kind: {
                    exact: '精确',
                    derived: '推导',
                    estimated: '估计',
                    unknown: '未知',
                  },
                },
              },
            },
            world_journal: {
              why_button: '为什么？',
            },
          },
        },
      },
    })

    const wrapper = mount(RegionDetail, {
      props: {
        data: {
          id: '1',
          name: 'Test City',
          type: 'city',
          type_name: 'Test',
          desc: 'Test Desc',
          animals: [],
          plants: [],
          lodes: [],
          population: 120,
          population_capacity: 200,
          dao_tradition: 'mandate_and_order',
        }
      },
      global: {
        plugins: [pinia, i18n],
        stubs: {
          EntityRow: true,
          RelationRow: true,
          SecondaryPopup: true,
        }
      }
    })

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.text()).toContain('人口')
    expect(wrapper.text()).toContain('120.0 / 200.0 万')
    expect(wrapper.text()).toContain('天道诠释')
    expect(wrapper.text()).toContain('天命与秩序')
  })

  it('renders active semantic conditions and key readings with unknown values', () => {
    const wrapper = mount(RegionDetail, {
      props: {
        data: {
          id: 'region-1',
          name: 'Test Region',
          type: 'normal',
          type_name: 'Test',
          desc: 'Test Desc',
          animals: [],
          plants: [],
          lodes: [],
          semantic_context: {
            readings: [
              {
                key: { dimension: 'load', subject_kind: 'region', subject_id: 'region-1', concept_id: 'settlement' },
                derived_from: [{ dimension: 'capacity', subject_kind: 'region', subject_id: 'region-1', concept_id: 'settlement' }],
                value: null,
                unit: 'ratio',
                availability: 'unmeasurable',
                reading_kind: 'unknown',
                confidence: null,
                state_refs: [],
                source_event_ids: ['event-reading'],
              },
            ],
            conditions: [
              {
                id: 'condition-active',
                definition_id: 'crowding',
                label: '拥挤',
                intensity: 0.75,
                started_month: 12,
                cause_event_id: 'event-condition',
                source_readings: [],
              },
              {
                id: 'condition-resolved',
                definition_id: 'old-condition',
                label: '已解决',
                intensity: 1,
                started_month: 2,
                cause_event_id: 'event-resolved',
                source_readings: [],
                resolved_month: 8,
              },
            ],
            definitions: [],
          },
        },
      },
      global: {
        plugins: [pinia, sharedI18n],
        stubs: {
          EntityRow: true,
          RelationRow: true,
          SecondaryPopup: true,
        },
      },
    })

    expect(wrapper.text()).toContain('活动中的语义条件')
    expect(wrapper.text()).toContain('拥挤')
    expect(wrapper.text()).toContain('关键读数')
    expect(wrapper.text()).toContain('推导输入')
    expect(wrapper.text()).toContain('capacity(settlement)')
    expect(wrapper.text()).toContain('未知')
    expect(wrapper.text()).not.toContain('已解决')
    expect(wrapper.text()).not.toContain('当前压力')
    expect(wrapper.text()).not.toContain('可用能力')
  })

  it('opens the existing Why causal detail flow for condition and reading source events', async () => {
    const journalStore = useWorldJournalStore()
    const openCausalDetail = vi.spyOn(journalStore, 'openCausalDetail').mockResolvedValue()
    const wrapper = mount(RegionDetail, {
      props: {
        data: {
          id: 'region-1',
          name: 'Test Region',
          type: 'normal',
          type_name: 'Test',
          desc: 'Test Desc',
          animals: [],
          plants: [],
          lodes: [],
          semantic_context: {
            readings: [{
              key: { dimension: 'stock', subject_kind: 'region', subject_id: 'region-1', concept_id: 'spirit_stone' },
              derived_from: [],
              value: 42,
              unit: 'spirit_stone',
              availability: 'measurable',
              reading_kind: 'exact',
              confidence: null,
              state_refs: [],
              source_event_ids: ['event-reading'],
            }],
            conditions: [{
              id: 'condition-1',
              definition_id: 'definition-1',
              label: '条件',
              intensity: 0.5,
              started_month: 1,
              cause_event_id: 'event-1',
              source_readings: [],
            }],
            definitions: [],
          },
        },
      },
      global: {
        plugins: [pinia, sharedI18n],
        stubs: {
          EntityRow: true,
          RelationRow: true,
          SecondaryPopup: true,
        },
      },
    })

    await wrapper.get('[data-testid="region-condition-causal-event-condition-1-event-1"]').trigger('click')
    await wrapper.get('[data-testid="region-reading-causal-event-event-reading"]').trigger('click')

    expect(openCausalDetail).toHaveBeenNthCalledWith(1, 'event-1')
    expect(openCausalDetail).toHaveBeenNthCalledWith(2, 'event-reading')
  })

  it('renders factual city assets and grounded spiritual ecology with sources', async () => {
    const journalStore = useWorldJournalStore()
    const openCausalDetail = vi.spyOn(journalStore, 'openCausalDetail').mockResolvedValue()
    const wrapper = mount(RegionDetail, {
      props: {
        data: {
          id: '301',
          name: 'Grounded City',
          type: 'city',
          type_name: '城市',
          desc: 'Test Desc',
          animals: [],
          plants: [],
          lodes: [],
          city_state: {
            districts: [{ id: 'river-quarter', kind: 'mixed', tile_refs: [[1, 2]], population_weight: 0.6 }],
            assets: [{
              id: 'public-well',
              district_id: 'river-quarter',
              capability_ids: ['clean_water'],
              capacity: 120,
              quality: 0.75,
              integrity: 0.9,
            }],
            service_demands: [],
            population_groups: [],
            capacity_projects: [],
            governance: {
              controller_kind: 'dynasty',
              controller_id: 'house-1',
              administrative_capacity: 0.7,
            },
          },
          semantic_context: {
            readings: [],
            conditions: [],
            definitions: [],
            spiritual_ecology: {
              schema_version: 1,
              region_id: 301,
              grounding_status: 'grounded',
              grounded: true,
              risk_level: null,
              essence: {
                type: 'GOLD',
                density: 4,
                densities: { GOLD: 4 },
                state_refs: ['region:301:essence'],
                source_event_ids: [],
              },
              formations: [],
              graves: [],
              treasures: [],
              celestial_context: null,
              state_refs: ['region:301', 'region:301:essence'],
              source_event_ids: ['event-ecology'],
            },
            collective_health: {
              schema_version: 1,
              region_id: 301,
              grounding_status: 'grounded',
              grounded: true,
              living_avatar_count: {
                value: 4,
                unit: 'avatars',
                availability: 'measurable',
                reading_kind: 'exact',
                state_refs: ['region:301:living_avatars'],
                source_event_ids: [],
              },
              active_wounded_count: {
                value: 1,
                unit: 'avatars',
                availability: 'measurable',
                reading_kind: 'derived',
                state_refs: ['region:301:wounded'],
                source_event_ids: ['event-injury'],
              },
              hp_deficit: {
                value: 35,
                unit: 'hp',
                availability: 'measurable',
                reading_kind: 'derived',
                state_refs: ['region:301:hp'],
                source_event_ids: ['event-injury'],
              },
              healing_capacity: {
                value: 24,
                unit: 'capacity_units',
                availability: 'measurable',
                reading_kind: 'derived',
                state_refs: ['region:301:urban_asset:clinic:capacity'],
                source_event_ids: [],
              },
              healing_access: {
                value: 0.75,
                unit: 'ratio',
                availability: 'measurable',
                reading_kind: 'derived',
                state_refs: ['region:301:urban_service:healing:access'],
                source_event_ids: [],
              },
              injuries: [{
                avatar_id: 'avatar-1',
                severity: 'moderate',
                hp_lost: 35,
                state_refs: ['avatar:avatar-1:hp'],
                source_event_ids: ['event-injury'],
              }],
              healing_assets: [{
                asset_id: 'clinic',
                capability_ids: ['healing'],
                capacity: 24,
                state_refs: ['region:301:urban_asset:clinic:capacity'],
              }],
              state_refs: ['region:301:living_avatars', 'region:301:hp'],
              source_event_ids: ['event-injury'],
            },
          },
        },
      },
      global: {
        plugins: [pinia, sharedI18n],
        stubs: {
          EntityRow: true,
          RelationRow: true,
          SecondaryPopup: true,
        },
      },
    })

    expect(wrapper.text()).toContain('城市状态')
    expect(wrapper.text()).toContain('public-well')
    expect(wrapper.text()).toContain('clean_water')
    expect(wrapper.text()).toContain('有依据的事实')
    expect(wrapper.text()).toContain('来源事件 event-ecology')
    expect(wrapper.text()).toContain('群体健康')
    expect(wrapper.text()).toContain('存活修士')
    expect(wrapper.text()).toContain('疗愈可及性')
    expect(wrapper.text()).toContain('0.75 ratio')
    expect(wrapper.text()).toContain('avatar-1')
    expect(wrapper.text()).toContain('clinic')
    expect(wrapper.text()).toContain('来源事件 event-injury')
    await wrapper.get('[data-testid="region-spiritual-causal-event-event-ecology"]').trigger('click')
    await wrapper.get('[data-testid="region-health-causal-event-event-injury"]').trigger('click')
    expect(openCausalDetail).toHaveBeenCalledWith('event-ecology')
    expect(openCausalDetail).toHaveBeenCalledWith('event-injury')
  })

  it('renders urban service demands, group priorities, and group-specific reading ids', () => {
    const wrapper = mount(RegionDetail, {
      props: {
        data: {
          id: '305',
          name: 'Urban Services Region',
          type: 'city',
          type_name: '城市',
          desc: 'Test Desc',
          animals: [],
          plants: [],
          lodes: [],
          city_state: {
            districts: [],
            assets: [],
            service_demands: [{ capability_id: 'clean_water', demand_per_population: 1.5 }],
            population_groups: [{
              id: 'artisans',
              population_weight: 0.35,
              service_priority_weights: { clean_water: 2, medicine: 0.5 },
            }],
            governance: { controller_kind: '', controller_id: '', administrative_capacity: 0 },
            capacity_projects: [],
          },
          semantic_context: {
            readings: [
              {
                key: { dimension: 'capacity', subject_kind: 'region', subject_id: '305', concept_id: 'clean_water' },
                derived_from: [],
                value: 10,
                unit: 'units',
                availability: 'measurable',
                reading_kind: 'exact',
                confidence: null,
                state_refs: [],
                source_event_ids: [],
              },
              {
                key: {
                  dimension: 'capacity',
                  subject_kind: 'region',
                  subject_id: '305',
                  concept_id: 'clean_water',
                  group_id: 'artisans',
                  qualifiers: { kind: 'urban_service' },
                },
                derived_from: [],
                value: 8,
                unit: 'units',
                availability: 'measurable',
                reading_kind: 'derived',
                confidence: null,
                state_refs: [],
                source_event_ids: [],
              },
            ],
            conditions: [],
            definitions: [],
          },
        },
      },
      global: {
        plugins: [pinia, sharedI18n],
        stubs: { EntityRow: true, RelationRow: true, SecondaryPopup: true },
      },
    })

    expect(wrapper.get('[data-testid="region-urban-services"]').text()).toContain('城市服务')
    expect(wrapper.text()).toContain('clean_water')
    expect(wrapper.text()).toContain('人口需求：1.5')
    expect(wrapper.text()).toContain('artisans')
    expect(wrapper.text()).toContain('群组人口权重：35%')
    expect(wrapper.text()).toContain('medicine')
    expect(wrapper.text()).toContain('群组：artisans')
    expect(wrapper.findAll('.semantic-reading')).toHaveLength(2)
  })

  it('renders unknown spiritual grounding without inventing a risk or an empty fact block', () => {
    const wrapper = mount(RegionDetail, {
      props: {
        data: {
          id: '302',
          name: 'Unobserved Region',
          type: 'normal',
          type_name: '普通区域',
          desc: 'Test Desc',
          animals: [],
          plants: [],
          lodes: [],
          semantic_context: {
            readings: [],
            conditions: [],
            definitions: [],
            spiritual_ecology: {
              schema_version: 1,
              region_id: 302,
              grounding_status: 'unknown',
              grounded: false,
              risk_level: null,
              essence: null,
              formations: [],
              graves: [],
              treasures: [],
              celestial_context: null,
              state_refs: [],
              source_event_ids: [],
            },
            collective_health: {
              schema_version: 1,
              region_id: 302,
              grounding_status: 'unknown',
              grounded: false,
              living_avatar_count: {
                value: null,
                unit: 'avatars',
                availability: 'unmeasurable',
                reading_kind: 'unknown',
                state_refs: [],
                source_event_ids: [],
              },
              active_wounded_count: {
                value: null,
                unit: 'avatars',
                availability: 'unmeasurable',
                reading_kind: 'unknown',
                state_refs: [],
                source_event_ids: [],
              },
              hp_deficit: {
                value: null,
                unit: 'hp',
                availability: 'unmeasurable',
                reading_kind: 'unknown',
                state_refs: [],
                source_event_ids: [],
              },
              healing_capacity: {
                value: null,
                unit: 'capacity_units',
                availability: 'unmeasurable',
                reading_kind: 'unknown',
                state_refs: [],
                source_event_ids: [],
              },
              healing_access: {
                value: null,
                unit: 'ratio',
                availability: 'unmeasurable',
                reading_kind: 'unknown',
                state_refs: [],
                source_event_ids: [],
              },
              injuries: [],
              healing_assets: [],
              state_refs: [],
              source_event_ids: [],
            },
          },
        },
      },
      global: {
        plugins: [pinia, sharedI18n],
        stubs: {
          EntityRow: true,
          RelationRow: true,
          SecondaryPopup: true,
        },
      },
    })

    expect(wrapper.find('.spiritual-ecology').exists()).toBe(true)
    expect(wrapper.find('.collective-health').exists()).toBe(true)
    expect(wrapper.text()).toContain('依据未知')
    expect(wrapper.text()).toContain('群体健康')
    expect(wrapper.text()).toContain('存活修士')
    expect(wrapper.text()).not.toContain('风险')
    expect(wrapper.text()).not.toContain('暂无可用语义上下文。')
  })

  it('renders only canonical economy and infrastructure values', () => {
    const wrapper = mount(RegionDetail, {
      props: {
        data: {
          id: '303',
          name: 'Canonical Economy Region',
          type: 'city',
          type_name: '城市',
          desc: 'Test Desc',
          animals: [],
          plants: [],
          lodes: [],
          economy: {
            stocks: { grain: 42 },
            capacities: { grain: 100 },
            production_rates: { grain: 8 },
            demand_rates: { grain: 6 },
            access: { grain: 0.5 },
            dependencies: { grain_import: 0.25 },
          },
          infrastructure: {
            capacities: { road_transport: 30 },
            quality: { road_transport: 0.8 },
          },
        },
      },
      global: {
        plugins: [pinia, sharedI18n],
        stubs: {
          EntityRow: true,
          RelationRow: true,
          SecondaryPopup: true,
        },
      },
    })

    expect(wrapper.get('[data-testid="region-economy"]').text()).toContain('区域经济')
    expect(wrapper.get('[data-testid="region-economy"]').text()).toContain('grain')
    expect(wrapper.get('[data-testid="region-economy"]').text()).toContain('42')
    expect(wrapper.get('[data-testid="region-economy"]').text()).toContain('0.25')
    expect(wrapper.get('[data-testid="region-infrastructure"]').text()).toContain('road_transport')
    expect(wrapper.get('[data-testid="region-infrastructure"]').text()).toContain('0.8')
    expect(wrapper.text()).not.toContain('价格')
    expect(wrapper.text()).not.toContain('稀缺')
    expect(wrapper.text()).not.toContain('风险')
  })

  it('omits empty economy and infrastructure blocks', () => {
    const wrapper = mount(RegionDetail, {
      props: {
        data: {
          id: '304',
          name: 'Empty Economy Region',
          type: 'city',
          type_name: '城市',
          desc: 'Test Desc',
          animals: [],
          plants: [],
          lodes: [],
          economy: {
            stocks: {},
            capacities: {},
            production_rates: {},
            demand_rates: {},
            access: {},
            dependencies: {},
          },
          infrastructure: {
            capacities: {},
            quality: {},
          },
        },
      },
      global: {
        plugins: [pinia, sharedI18n],
        stubs: {
          EntityRow: true,
          RelationRow: true,
          SecondaryPopup: true,
        },
      },
    })

    expect(wrapper.find('[data-testid="region-economy"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="region-infrastructure"]').exists()).toBe(false)
  })
})
