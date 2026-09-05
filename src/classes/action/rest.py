from __future__ import annotations

from src.i18n import t
from src.classes.action import TimedAction
from src.classes.event import Event


class Rest(TimedAction):
    ACTION_NAME_ID = "rest_action_name"
    DESC_ID = "rest_description"
    REQUIREMENTS_ID = "rest_requirements"

    EMOJI = "💤"
    PARAMS = {}

    duration_months = 3
    BASE_HP_RECOVERY_RATIO = 0.2

    def _execute(self) -> None:
        return

    def can_start(self) -> tuple[bool, str]:
        if getattr(self.avatar, "is_dead", False):
            return False, t("Dead avatars cannot rest.")
        return True, ""

    def start(self) -> Event:
        content = t("{avatar} begins resting.", avatar=self.avatar.name)
        return Event(self.world.month_stamp, content, related_avatars=[self.avatar.id])

    async def finish(self) -> list[Event]:
        hp_max = int(getattr(getattr(self.avatar, "hp", None), "max", 0) or 0)
        before_hp = self.avatar.hp.cur
        extra_recovery = float(self.avatar.effects.get("extra_rest_hp_recovery_rate", 0.0) or 0.0)
        recovery = max(1, int(hp_max * (self.BASE_HP_RECOVERY_RATIO + extra_recovery))) if hp_max > 0 else 0
        if recovery > 0 and hasattr(self.avatar.hp, "recover"):
            self.avatar.hp.recover(recovery)

        exp = int(self.avatar.effects.get("extra_rest_exp", 0) or 0)
        if exp > 0 and self.avatar.cultivation_progress.can_cultivate():
            self.avatar.cultivation_progress.add_exp(exp)

        if exp > 0:
            content = t("{avatar} finished resting, recovered {hp} HP and gained {exp} cultivation experience.", avatar=self.avatar.name, hp=recovery, exp=exp)
        else:
            content = t("{avatar} finished resting and recovered {hp} HP.", avatar=self.avatar.name, hp=recovery)
        event = Event(self.world.month_stamp, content, related_avatars=[self.avatar.id])
        from src.classes.individual_consequence import record_hp_change_from_event
        record_hp_change_from_event(self.avatar, event, before_hp)
        # The recovery is a real change either way; who *chose* it is a
        # separate, proved question.  Only this Avatar's own audited decision
        # naming this exact Rest may author it, so a rest installed as a
        # reaction, or one whose actor carries no audit, stays unattributed
        # rather than borrowing an unrelated decision.
        from src.systems.avatar_decision import attach_validated_actor_decision
        attach_validated_actor_decision(
            event,
            self.avatar,
            action_name=self.name,
            params={},
            action_origin=self.action_origin,
        )
        return [event]
