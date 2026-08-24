from __future__ import annotations

from typing import TYPE_CHECKING

from src.systems.event_appraisal_service import generate_appraisals_for_events

if TYPE_CHECKING:
    from src.classes.event import Event


async def phase_generate_event_appraisals(world, events: list["Event"]) -> None:
    """为本月已产生的事件挂载个人解读。

    只读取本轮 `SimulationStepContext` 中已有的事件，并且只往
    `event.appraisals` 上挂载对象；不写库、不新增事件、不改世界状态。
    真正的落库仍由随后的 `finalize_step` 统一完成。
    """
    await generate_appraisals_for_events(world, events)
