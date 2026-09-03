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
        4.  占据无主修炼地（曾是相位 1 的一部分，现移到 AI 决策之后，
            避免必选决策失败重跑同一月时被再次触发）
        5.  Gathering 系统（聚会/大会）处理（同样移到 AI 决策之后，理由相同）
        6.  提交并启动下一步计划
        7.  执行当前行动（多轮 Tick，直到稳定或达到上限）
        8.  检查机缘（opportunity）
        9.  世界秘密发现
        10. 按事件处理交互（第一轮）
        11. 关系演化相位
        12. 死亡结算
        13. 藏宝生命周期
        14. POI 发现
        15. 年龄更新与出生
        16. 身世背景生成
        17. 被动效果与世界性随机事件
        18. 个人后果与伤势恢复
        19. 自定义内容自主创建
        20. 小型随机事件
        21. 后台 NPC 事件
        22. 宗门随机事件
        23. 宗门战争
        24. 外号生成
        25. 天象（大环境气候）更新
        26. 城市人口更新
        27. 区域经济的确定性生产与需求
        28. 经济解释器处理真实短缺与显式路线
        29. 城市容量项目按真实治理和基础设施推进
        30. 王朝与官职系统更新
        31. 按事件处理交互（第二轮，包含后续新事件）
        32. 计算型关系（如二阶关系）更新
        33. 地方请愿与民间仪式
        34. 每年一月：世界年度维护
        35. 机械语言重算与条件转变
        36. 当前王朝政府处理其明确控制城市的 grounded urban risk
        37. 宗门组织处理成员所在区域的 grounded adversity
        38. 无制度控制城市的解释器处理 grounded urban risk
        39. 人口解释器处理新的、真实的人口压力转变
        40. 保存晚于重算发生的机械 invalidations 供下月使用
        41. 事件解读
        42. 编年史
        43. 最终入库并推进月份
        """
        if is_world_test_mode(self.world):
            with llm_test_mode_scope(True):
                return await SimulationPhaseRunner(self).run()
        return await SimulationPhaseRunner(self).run()
