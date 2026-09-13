import { computed } from 'vue'
import { useObserverStore } from '../stores/world'
import { entityName } from '../mappers'

export function useSupplyPlans() {
  const store = useObserverStore()
  const plans = computed(() => {
    const data = store.snapshot!
    return data.governance.objectives.map(objective => {
      const settlement = data.society.settlements.find(s => s.id === objective.settlement_id)!
      const stockId = objective.stock_id
      const stock = data.economy.stocks.find(s => s.id === stockId)!
      const resource = data.economy.resources.find(r => r.id === objective.resource_id)!
      const plan = data.governance.plans.find(p => p.objective_id === objective.id)
      const pending = data.economy.pending_orders.filter(o => o.destination_id === stockId && o.resource_id === resource.id)
      const reports = data.governance.reports.filter(r => r.recipient_ref.kind === objective.actor_ref.kind
        && r.recipient_ref.id === objective.actor_ref.id && r.kind === 'offer' && r.resource_id === resource.id)
        .map(r => ({ ...r, publisherName: entityName(data, r.publisher_ref) }))
      return { objective, plan, settlement, resource, stockId, owner: entityName(data, objective.actor_ref),
        target: objective.target_quantity, stored: stock.goods[resource.id] ?? 0,
        transit: pending.reduce((sum, o) => sum + o.quantity - o.delivered_quantity, 0), reports }
    })
  })
  return { plans, source: (id: string) => { store.focusEventId = id } }
}
