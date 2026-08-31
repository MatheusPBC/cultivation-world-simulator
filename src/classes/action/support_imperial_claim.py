from __future__ import annotations

from src.classes.action import InstantAction
from src.i18n import t
from src.systems.imperial_crisis_service import get_imperial_support_blocker, support_imperial_claim


class SupportImperialClaim(InstantAction):
    """Let an eligible court official take a public side in one active crisis."""

    ACTION_NAME_ID = "support_imperial_claim_action_name"
    DESC_ID = "support_imperial_claim_description"
    REQUIREMENTS_ID = "support_imperial_claim_requirements"

    EMOJI = "⚖"
    PARAMS = {}
    IS_MAJOR = True

    def can_possibly_start(self) -> bool:
        return get_imperial_support_blocker(self.world, str(self.avatar.id)) is None

    def can_start(self) -> tuple[bool, str]:
        blocker = get_imperial_support_blocker(self.world, str(self.avatar.id))
        return (False, t(blocker)) if blocker is not None else (True, "")

    def start(self):
        support_imperial_claim(self.world, str(self.avatar.id))
        return None

    def _execute(self) -> None:
        return

    async def finish(self) -> list:
        return []
