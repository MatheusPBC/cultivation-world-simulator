from __future__ import annotations

from src.classes.action import InstantAction
from src.classes.action.param_options import ParamOptionSource
from src.classes.event import Event
from src.i18n import t
from src.systems.celestial_dao_service import (
    can_sponsor_dao_rite,
    get_sponsor_dao_rite_blocker,
    sponsor_dao_rite,
)


class SponsorDaoRite(InstantAction):
    """Let the emperor or a living sect patriarch sponsor one public rite."""

    ACTION_NAME_ID = "sponsor_dao_rite_action_name"
    DESC_ID = "sponsor_dao_rite_description"
    REQUIREMENTS_ID = "sponsor_dao_rite_requirements"

    EMOJI = "🕯"
    PARAMS = {"cause_event_id": "str"}
    PARAM_OPTION_SOURCES = {
        "cause_event_id": ParamOptionSource.SPONSORABLE_DAO_RITE_EVENT_ID,
    }
    IS_MAJOR = True

    def can_possibly_start(self) -> bool:
        # Keep the action out of the LLM prompt unless the avatar has the
        # institutional identity and at least one public rite in reach.
        from src.classes.action.param_options import build_param_options

        return can_sponsor_dao_rite(self.world, self.avatar) and bool(
            build_param_options(self.__class__, self.avatar).get("cause_event_id")
        )

    def can_start(self, cause_event_id: str) -> tuple[bool, str]:
        blocker = get_sponsor_dao_rite_blocker(
            self.world,
            self.avatar,
            cause_event_id,
        )
        return (False, t(blocker)) if blocker is not None else (True, "")

    def start(self, cause_event_id: str) -> Event:
        return sponsor_dao_rite(self.world, self.avatar, cause_event_id)

    def _execute(self, cause_event_id: str) -> None:
        return

    async def finish(self, cause_event_id: str) -> list[Event]:
        return []
