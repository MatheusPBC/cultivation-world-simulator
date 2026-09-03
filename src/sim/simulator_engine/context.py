from __future__ import annotations

from dataclasses import dataclass, field

from src.classes.core.avatar import Avatar
from src.classes.core.world import World
from src.classes.event import Event
from src.classes.chronicle import ChronicleChapter
from src.sim.simulator_engine.causal_recorder import CausalRecorder
from src.sim.simulator_engine.causal_budget import CausalBudget
from src.sim.simulator_engine.domain_invalidation import DomainInvalidationQueue
from src.systems.time import Month, MonthStamp


@dataclass(slots=True)
class SimulationStepContext:
    # 单次 step 共享的运行时容器：
    # 把“在世角色缓存、事件汇总、交互去重状态”集中到一起，
    # 避免这些临时状态散落在 Simulator.step() 的局部变量里。
    world: World
    living_avatars: list[Avatar]
    events: list[Event] = field(default_factory=list)
    processed_event_ids: set[str] = field(default_factory=set)
    month_stamp: MonthStamp | None = None
    # 被动因果记录器：由已经完成变更的领域 owner 写入，finalize_step 统一drain。
    causal: CausalRecorder = field(default_factory=CausalRecorder)
    invalidations: DomainInvalidationQueue = field(default_factory=DomainInvalidationQueue)
    causal_budget: CausalBudget | None = None
    pending_chronicle_chapter: ChronicleChapter | None = None

    @classmethod
    def create(cls, world: World) -> "SimulationStepContext":
        # 每轮开始时抓取一次在世角色快照，后续只允许通过 phase
        # 明确地修改这份列表，例如死亡结算阶段会原地移除死者。
        ctx = cls(
            world=world,
            living_avatars=world.avatar_manager.get_living_avatars(),
            month_stamp=world.month_stamp,
            causal_budget=CausalBudget.from_world(world),
        )
        # 桥接：部分 owner（如 Action）只能拿到 world，拿不到 ctx 本身，
        # 与 get_decision_boundary_gateway(world) 是同一种挂载方式。
        world.step_causal_recorder = ctx.causal
        return ctx

    @property
    def is_january(self) -> bool:
        return self.month_stamp is not None and self.month_stamp.get_month() == Month.JANUARY

    def add_events(self, new_events: list[Event] | None) -> None:
        # phase 可以返回空列表或 None，这里统一做一次兼容，
        # 让 step() 的编排代码保持扁平。
        if new_events:
            self.events.extend(new_events)
