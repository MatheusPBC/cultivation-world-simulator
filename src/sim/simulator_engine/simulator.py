from __future__ import annotations

from src.classes.event import Event
from src.classes.core.world import World
from src.config.providers import StaticConfigProvider
from src.utils.llm.runtime_mode import is_world_test_mode, llm_test_mode_scope

from .phase_runner import SimulationPhaseRunner


class Simulator:
    def __init__(self, world: World):
        self.world = world
        run_config = getattr(world, "run_config_snapshot", {}) or {}
        self.awakening_rate = float(run_config.get("npc_awakening_rate_per_month", 0.01))
        self.config_provider = StaticConfigProvider.current()
        self.can_interrupt_major = self.config_provider.can_interrupt_major_events()

        from src.sim.managers.sect_manager import SectManager

        self.sect_manager = SectManager(world)

    async def step(self) -> list[Event]:
        """
        模拟器单步主流程（一个月的推进）。

        相位顺序（`src/sim/simulator_engine/phase_registry.py:SIMULATION_PHASES`
        是唯一真源；此处只是可读摘要，改了顺序务必同步这里）：
        1.  更新角色感知与已知区域（纯 known_regions 并集，幂等）
        2.  AI 决策（为无计划角色生成行动链）——必选决策失败
            （`RequiredDecisionFailed`）会在这里向外抛出并中止本次 step，
            见 docs/specs/causal-world-kernel.md §6
        3.  长期目标思考
        4.  Gathering 系统（聚会/大会）处理
        5.  提交并启动下一步计划
        6.  执行当前行动（包括角色主动选择的 Occupy）
        7.  检查机缘（opportunity）与世界秘密发现
        8.  交互、关系、死亡、藏宝、POI、出生与个人后果
        9.  被动效果、自定义内容、宗门战争、外号与天象
        10. 城市人口、区域经济与集体领域 affordance 反应
        11. 王朝、官职、关系计算与年度维护
        12. 区域气候与洪水更新
        13. 已注册 hazard 法则作用于真实空间目标
        14. 明确 maintainer 解释并执行基础设施修复 affordance
        15. 路线依赖重算与机械语言评估
        16. 政府、组织、城市与人口解释器处理当前 affordances
        17. 保存晚于重算发生的机械 invalidations 供下月使用
        18. 事件解读、编年史、因果校验、入库并推进月份
        """
        if is_world_test_mode(self.world):
            with llm_test_mode_scope(True):
                return await SimulationPhaseRunner(self).run()
        return await SimulationPhaseRunner(self).run()
