from __future__ import annotations

from src.classes.action import InstantAction
from src.i18n import t
from src.systems.imperial_crisis_service import get_imperial_claim_blocker, open_imperial_claim


class ClaimImperialMandate(InstantAction):
    """Open a political legitimacy crisis; it never transfers the throne directly."""

    ACTION_NAME_ID = "claim_imperial_mandate_action_name"
    DESC_ID = "claim_imperial_mandate_description"
    REQUIREMENTS_ID = "claim_imperial_mandate_requirements"

    EMOJI = "👑"
    PARAMS = {}
    IS_MAJOR = True

    def can_possibly_start(self) -> bool:
        return get_imperial_claim_blocker(self.world, str(self.avatar.id)) is None

    def can_start(self) -> tuple[bool, str]:
        blocker = get_imperial_claim_blocker(self.world, str(self.avatar.id))
        if blocker is not None:
            return False, t(blocker)
        return True, ""

    def start(self):
        open_imperial_claim(self.world, str(self.avatar.id))
        # The domain service records the major decision fact immediately, so it
        # remains available to both an API mutation and the simulation phase.
        return None

    def _execute(self) -> None:
        return

    async def finish(self) -> list:
        return []
