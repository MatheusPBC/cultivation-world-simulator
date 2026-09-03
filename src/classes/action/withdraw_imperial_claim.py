from __future__ import annotations

from src.classes.action import InstantAction
from src.i18n import t
from src.systems.imperial_crisis_service import withdraw_imperial_claim


class WithdrawImperialClaim(InstantAction):
    ACTION_NAME_ID = "withdraw_imperial_claim_action_name"
    DESC_ID = "withdraw_imperial_claim_description"
    REQUIREMENTS_ID = "withdraw_imperial_claim_requirements"
    EMOJI = "🏳"
    PARAMS = {}
    IS_MAJOR = True

    def can_possibly_start(self) -> bool:
        crisis = getattr(getattr(self.world, "dynasty", None), "imperial_crisis", None)
        return bool(crisis and crisis.status == "active" and str(crisis.claimant_avatar_id) == str(self.avatar.id))

    def can_start(self) -> tuple[bool, str]:
        return (True, "") if self.can_possibly_start() else (False, t("Only the active claimant can withdraw the imperial claim"))

    def start(self):
        return withdraw_imperial_claim(self.world, str(self.avatar.id))

    def _execute(self) -> None:
        return

    async def finish(self) -> list:
        return []
