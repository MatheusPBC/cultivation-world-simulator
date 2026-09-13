import { computed } from 'vue'
import { useObserverStore } from '../stores/world'

export function useMigration() {
  const store = useObserverStore()
  const migrations = computed(() => {
    const data = store.snapshot!
    return data.society.migrations.map(journey => {
      const group = data.society.population_groups.find(item => item.id === journey.source_group_id)!
      const source = data.society.settlements.find(item => item.id === group.settlement_id)!
      const destination = data.society.settlements.find(item => item.id === journey.destination_id)!
      const provision = data.economy.migration_provisions.find(item => item.id === journey.provision_id)!
      const account = data.economy.accounts.find(item => item.id === provision.account_id)!
      const routeId = journey.route_ids[journey.route_index]
      const route = data.map.routes.find(item => item.route.id === routeId)
      const people = journey.character_ids.map(id => data.society.characters.find(item => item.id === id)!.name)
      return { journey, group, source, destination, provision, account, routeId, route, people,
        returnLabel: journey.returning ? `Retorno a ${destination.name}` : `${source.name} → ${destination.name}`,
        balance: account.balance }
    })
  })
  const source = (id: string) => { store.focusEventId = id }
  return { migrations, source }
}
