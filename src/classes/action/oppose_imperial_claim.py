from __future__ import annotations

from src.classes.action import InstantAction
from src.classes.action.param_options import ParamOptionSource
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
    PARAMS = {"candidate_id": "str"}
    PARAM_OPTION_SOURCES = {
        "candidate_id": ParamOptionSource.ACTIVE_IMPERIAL_CLAIM_CANDIDATE_ID,
    }
    IS_MAJOR = True

    def can_possibly_start(self) -> bool:
        from src.classes.action.param_options import build_param_options

        return bool(build_param_options(self.__class__, self.avatar).get("candidate_id"))

    def can_start(self, candidate_id: str) -> tuple[bool, str]:
        blocker = get_imperial_opposition_blocker(
            self.world, str(self.avatar.id), candidate_id
        )
        return (False, t(blocker)) if blocker else (True, "")

    def start(self, candidate_id: str):
        return oppose_imperial_claim(
            self.world, str(self.avatar.id), candidate_id
        )

    def _execute(self) -> None:
        return

    async def finish(self, candidate_id: str) -> list:
        return []
