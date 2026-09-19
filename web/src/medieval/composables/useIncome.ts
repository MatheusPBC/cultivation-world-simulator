import { computed } from 'vue'
import { useObserverStore } from '../stores/world'
import { entityName } from '../mappers'

export function useIncome() {
  const store = useObserverStore()
  const data = computed(() => store.snapshot!)
  const savings = computed(() => {
    const groups = new Map(data.value.society.population_groups.map(g => [g.id, g.settlement_id]))
    const balances = new Map<string, number>()
    for (const account of data.value.economy.accounts) {
      if (account.owner_ref.kind !== 'population_group') continue
      const place = groups.get(account.owner_ref.id)
      if (place) balances.set(place, (balances.get(place) ?? 0) + account.balance)
    }
    return data.value.society.settlements.map(s => ({ id: s.id, name: s.name, balance: balances.get(s.id) ?? 0 }))
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
