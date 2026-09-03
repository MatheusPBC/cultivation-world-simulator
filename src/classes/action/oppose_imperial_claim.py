from __future__ import annotations

from src.classes.action import InstantAction
from src.i18n import t
from src.systems.imperial_crisis_service import (
    get_imperial_opposition_blocker,
    oppose_imperial_claim,
)


class OpposeImperialClaim(InstantAction):
    ACTION_NAME_ID = "oppose_imperial_claim_action_name"
    DESC_ID = "oppose_imperial_claim_description"
    REQUIREMENTS_ID = "oppose_imperial_claim_requirements"
    EMOJI = "⚔"
    PARAMS = {}
    IS_MAJOR = True

    def can_possibly_start(self) -> bool:
        return get_imperial_opposition_blocker(self.world, str(self.avatar.id)) is None

    def can_start(self) -> tuple[bool, str]:
        blocker = get_imperial_opposition_blocker(self.world, str(self.avatar.id))
        return (False, t(blocker)) if blocker else (True, "")

    def start(self):
        return oppose_imperial_claim(self.world, str(self.avatar.id))

    def _execute(self) -> None:
        return

    async def finish(self) -> list:
        return []
