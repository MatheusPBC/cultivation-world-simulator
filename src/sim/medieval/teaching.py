"""Explicit bilateral institutional disclosure, not global technology unlocks."""
from src.classes.event import FactKind
from src.classes.mechanical_language import EntityRef
from src.classes.governance.authority import require_authority
from .research import learn_technology


def teach_technology(world, offer_id, acceptance_id):
    events = {e.id: e for e in world.events}
    offer, acceptance = events.get(offer_id), events.get(acceptance_id)
    keys = {'technology_id', 'teacher_ref', 'student_ref'}
    if (offer is None or acceptance is None or offer_id == acceptance_id
            or any(e.fact_kind != FactKind.DECISION or e.day != world.clock.absolute_day or e.decision is None
                   or set(e.decision) != keys | {'action', 'actor_ref'} for e in (offer, acceptance))):
        raise ValueError('teaching requires two current decisions')
    a, b = offer.decision, acceptance.decision
    if (a['action'] != 'teach' or b['action'] != 'learn' or any(a[k] != b[k] for k in keys)
            or a['actor_ref'] != a['teacher_ref'] or b['actor_ref'] != b['student_ref']):
        raise ValueError('teaching decisions do not agree')
    teacher, student = EntityRef.from_dict(a['teacher_ref']), EntityRef.from_dict(a['student_ref'])
    tech = world.research.technologies.get(a['technology_id'])
    if (tech is None or teacher == student or not world.knowledge.knows(teacher, tech.id)
            or world.knowledge.knows(student, tech.id)
            or any(not world.knowledge.knows(student, k) for k in tech.prerequisites)):
        raise ValueError('teaching requires owned knowledge and a prepared learner')
    require_authority(world, teacher, 'research')
    require_authority(world, student, 'research')
    source = next(k for k in world.knowledge.technologies.values() if k.owner_ref == teacher and k.technology_id == tech.id)
    learn_technology(world, student, tech.id, 'teaching', (offer_id, acceptance_id, source.event_id))
