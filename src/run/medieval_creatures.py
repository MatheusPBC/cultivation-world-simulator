"""The single authored creature premise of this world: the River Lume drake.

It is a bootstrap physical fact, not a spawn rule and not an event generator.
The drake begins neutral, well fed and silent; nothing happens until cargo
actually crosses its river.
"""

from src.classes.environment.creature import Creature, CreatureState

DRAKE_ID = "creature:drake-do-lume"
WATER_BODY_ID = "rio-lume"
ROUTE_ID = "river-pedraclara-portovelho"


def create_creatures(game_map) -> CreatureState:
    state = CreatureState()
    water_bodies = {body.id: body for body in game_map.geography.water_bodies}
    if WATER_BODY_ID not in water_bodies or ROUTE_ID not in game_map.routes:
        return state
    state.creatures[DRAKE_ID] = Creature(
        id=DRAKE_ID, name="Dragão do Lume", water_body_id=WATER_BODY_ID, route_ids=(ROUTE_ID,),
        condition=1000, hunger_threshold=700, tribute_food=40)
    state.validate()
    return state
