import { computed } from 'vue'
import { useObserverStore } from '../stores/world'
import { entityName } from '../mappers'

export function useDiplomacy() {
  const store = useObserverStore()
  const proposals = computed(() => {
    const data = store.snapshot!
    const obligations = new Map(data.diplomacy.obligations.map(o => [`${o.proposal_id}:${o.clause_index}`, o]))
    const informed = (eventId: string) => data.diplomacy.notices.filter(n => n.event_id === eventId)
      .map(n => ({ ...n, name: entityName(data, n.recipient_ref) }))
    return [...data.diplomacy.proposals].sort((a, b) => b.offered_day - a.offered_day || a.id.localeCompare(b.id))
      .map(p => ({ ...p, proposer: entityName(data, p.proposer_ref), counterparty: entityName(data, p.counterparty_ref),
        parentEventId: data.diplomacy.proposals.find(parent => parent.id === p.parent_id)?.last_event_id,
        informed: informed(p.last_event_id),
        terms: p.clauses.map((clause, index) => {
          const obligation = obligations.get(`${p.id}:${index}`)
          return { clause, number: index + 1, obligation,
            debtor: entityName(data, clause.debtor_ref), creditor: entityName(data, clause.creditor_ref),
            technology: clause.kind === 'teaching'
              ? data.research.technologies.find(t => t.id === clause.technology_id)?.name ?? clause.technology_id : null,
            informed: obligation ? informed(obligation.last_event_id) : [],
          }
        }),
      }))
  })
  const source = (id: string) => { store.focusEventId = id }
  return { proposals, source }
}
