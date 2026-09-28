import { computed } from 'vue'
import { useObserverStore } from '../stores/world'
import { entityName } from '../mappers'

export function useIncome() {
  const store = useObserverStore()
  const data = computed(() => store.snapshot!)
  const savings = computed(() => {
    const groups = new Map(data.value.society.population_groups.map(g => [g.id, g]))
    const balances = new Map<string, number>()
    const accounts = new Map<string, { balance: number; last_event_id: string | null }>()
    for (const account of data.value.economy.accounts) {
      if (account.owner_ref.kind !== 'population_group') continue
      const group = groups.get(account.owner_ref.id)
      if (group) {
        balances.set(group.settlement_id, (balances.get(group.settlement_id) ?? 0) + account.balance)
        accounts.set(group.id, account)
      }
    }
    return data.value.society.settlements.map(s => {
      const need = data.value.economy.needs.find(item => item.id === s.id)
      const stock = data.value.economy.stocks.find(item => item.id === need?.stock_id)
      const artisans = data.value.society.population_groups.filter(
        group => group.settlement_id === s.id && group.occupation === 'artisan')
      const artisanGroups = artisans.map(group => ({ ...group,
        balance: accounts.get(group.id)?.balance ?? 0,
        sourceId: accounts.get(group.id)?.last_event_id ?? null }))
      return { id: s.id, name: s.name, balance: balances.get(s.id) ?? 0,
        artisanPeople: artisans.reduce((total, group) => total + group.count, 0),
        artisanCash: artisanGroups.reduce((total, group) => total + group.balance, 0),
        artisanGroups, food: stock?.goods.food ?? 0, foodSourceId: stock?.last_event_ids.food ?? null,
        missingFood: need?.missing_food ?? 0, health: need?.health ?? 0,
        foodPrice: s.food_price ?? 0,
        householdCashByOccupation: s.household_cash_by_occupation ?? {},
        estimatedUnaffordable: s.estimated_unaffordable_public_rations ?? 0,
        estimatedUnaffordableByOccupation: s.estimated_unaffordable_public_rations_by_occupation ?? {},
        foodAccessEvidenceIds: s.food_access_evidence_event_ids ?? [],
        needSourceId: need?.last_event_id ?? null }
    })
  })
  const totalSavings = computed(() => savings.value.reduce((sum, s) => sum + s.balance, 0))
  const payrolls = computed(() => data.value.economy.payrolls.map(p => {
    const project = data.value.economy.expansions.find(e => e.id === p.id)
    const research = data.value.research.projects.find(r => r.id === p.id)
    const facility = data.value.economy.facilities.find(f => f.id === (project?.facility_id ?? p.id))
    const recipe = !project && !research && data.value.economy.recipes.find(r => r.id === facility?.recipe_id)
    const products = recipe ? Object.keys(recipe.outputs).map(id =>
      data.value.economy.resources.find(r => r.id === id)?.name ?? id).join(', ') : null
    return { ...p, construction: !!project, research: !!research,
      products,
      name: data.value.map.sites.find(s => s.id === (research?.site_id ?? facility?.site_id))?.name ?? p.id,
      workers: Object.values(p.workers_by_group).reduce((sum, count) => sum + count, 0), net: p.gross - p.tax }
  }))
  const employmentContracts = computed(() => data.value.economy.employment_contracts.map(contract => ({
    ...contract,
    employer: entityName(data.value, contract.employer_ref),
    cohort: data.value.society.population_groups.find(group => group.id === contract.cohort_id),
    workSite: data.value.map.sites.find(site => site.id === contract.work_site_id)?.name ?? contract.work_site_id,
  })))
  const policies = computed(() => data.value.governance.tax_policies.map(p => ({ ...p,
    name: entityName(data.value, { kind: 'polity', id: p.id }) })))
  const source = (id: string | null) => { if (id) store.focusEventId = id }
  return { savings, totalSavings, payrolls, employmentContracts, policies, source }
}
