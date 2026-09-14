"""Load authored technologies only when creating a new world."""
import json
from pathlib import Path
from src.classes.research import ResearchState
from src.classes.research.models import RiteBlueprint, Technology

CATALOG = Path(__file__).resolve().parents[2] / 'static/game_configs/medieval/research.json'


def create_research():
    data = json.loads(CATALOG.read_text(encoding='utf-8'))
    if type(data.get('catalog_version')) is not int or data['catalog_version'] != 1:
        raise ValueError('unsupported research catalog')
    state = ResearchState()
    for raw in data['technologies']:
        tech = Technology.model_validate(raw)
        if tech.id in state.technologies:
            raise ValueError('duplicate technology')
        state.technologies[tech.id] = tech
    for raw in data.get('rite_blueprints', ()):
        rite = RiteBlueprint.model_validate(raw)
        if rite.id in state.rite_blueprints:
            raise ValueError('duplicate rite blueprint')
        state.rite_blueprints[rite.id] = rite
    state.validate()
    return state
