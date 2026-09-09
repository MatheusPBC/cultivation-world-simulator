from __future__ import annotations

from src.classes.action import InstantAction
from src.classes.action.param_options import ParamOptionSource
from src.classes.event import NULL_EVENT, Event
from src.i18n import t
from src.systems.civic_endorsement import (
    can_endorse_public_petition,
    get_endorse_petition_blocker,
    record_public_endorsement,
)


class EndorsePublicPetition(InstantAction):
    """Let one living resident publicly endorse their city's own petition.

    Individual support, not leadership: it gathers no followers, forms no
    organization and grants no authority. It costs no resource -- nothing is
    bought and no owner is moved by speaking -- so it takes the ordinary action
    slot and nothing else.
    """

    ACTION_NAME_ID = "endorse_public_petition_action_name"
    DESC_ID = "endorse_public_petition_description"
    REQUIREMENTS_ID = "endorse_public_petition_requirements"

    EMOJI = "📜"
    PARAMS = {"cause_event_id": "str"}
    PARAM_OPTION_SOURCES = {
        "cause_event_id": ParamOptionSource.ENDORSABLE_PUBLIC_PETITION_EVENT_ID,
    }
    IS_MAJOR = True

    def can_possibly_start(self) -> bool:
        # Keep the action out of the prompt unless a real, currently endorsable
        # petition exists for this very avatar.
        return can_endorse_public_petition(self.world, self.avatar)

    def can_start(self, cause_event_id: str) -> tuple[bool, str]:
        blocker = get_endorse_petition_blocker(
            self.world, self.avatar, cause_event_id
        )
        return (False, t(blocker)) if blocker is not None else (True, "")

    def start(self, cause_event_id: str) -> Event:
        # Nothing is endorsed yet: the engine installs ``action_origin`` only
        # after ``start`` returns, so authorship can only be proved at the
        # execution boundary below.
        return NULL_EVENT

    def _execute(self, cause_event_id: str) -> None:
        return

    async def finish(self, cause_event_id: str) -> list[Event]:
        event = record_public_endorsement(
            self.world,
            self.avatar,
            cause_event_id,
            action_origin=self.action_origin,
        )
        return [event] if event is not None else []
