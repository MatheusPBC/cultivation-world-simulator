import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useObserverStore } from '../stores/world'
import { entityName } from '../mappers'

export function useResearch() {
  const store = useObserverStore()
  const { t } = useI18n()
  const data = computed(() => store.snapshot!)
  const technologies = computed(() => new Map(data.value.research.technologies.map(x => [x.id, x])))
  const projects = computed(() => data.value.research.projects.map(p => ({ ...p,
    technology: technologies.value.get(p.technology_id)!,
    owner: entityName(data.value, p.owner_ref),
    researcher: entityName(data.value, { kind: 'character', id: p.researcher_id }),
    site: data.value.map.sites.find(s => s.id === p.site_id)?.name ?? p.site_id,
    blocker: p.blocker?.startsWith('input:')
      ? t('missingMaterial') + ': ' + (data.value.economy.resources.find(r => r.id === p.blocker!.slice(6))?.name ?? p.blocker.slice(6))
      : p.blocker ? t('researchBlockers.' + p.blocker) : null,
  })))
  const knowledge = computed(() => data.value.research.knowledge.map(k => ({ ...k,
    owner: entityName(data.value, k.owner_ref), technology: technologies.value.get(k.technology_id)!,
  })))
  const catalog = computed(() => data.value.research.technologies.map(tech => ({ ...tech,
    requirements: tech.prerequisites.map(id => technologies.value.get(id)?.name ?? id).join(', '),
  })))
  const rites = computed(() => data.value.research.rite_blueprints)
  const source = (id: string) => { store.focusEventId = id }
  return { projects, knowledge, catalog, rites, source }
}
