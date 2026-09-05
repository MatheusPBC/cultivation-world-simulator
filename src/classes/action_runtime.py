from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from enum import Enum, StrEnum


class ActionOrigin(StrEnum):
    """Who actually put an action into an Avatar's hands.

    This is engine-owned provenance, not an LLM parameter and not a name:
    only the decision boundary may declare ``ACTOR_CHOICE``.  Everything else
    -- a pre-empted fallback, a mutual-action response, a restored save --
    stays ``REACTIVE_RESPONSE``, which is also the fail-closed default, so a
    defensive or installed action can never be read as an initiating choice.

    It is deliberately transient.  It is never persisted, so a restored save
    proves nothing and therefore fails closed, and no save schema changes.
    """

    ACTOR_CHOICE = "actor_choice"
    REACTIVE_RESPONSE = "reactive_response"


class ActionStatus(Enum):
    """
    动作推进过程中的标准状态枚举。
    - RUNNING: 仍在进行中，需要在未来的 tick 中继续推进
    - COMPLETED: 已正常完成
    - FAILED: 执行失败（参数/前置条件等导致）
    - CANCELLED: 被外部取消（如被其他动作抢占）
    - INTERRUPTED: 运行中被打断（如战斗/事件中断）
    """

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


@dataclass
class ActionResult:
    """
    标准动作返回体。所有 Action.step() 必须返回该类型。

    Attributes:
        status: 当前推进后的状态（见 ActionStatus）
        events: 在本次推进过程中生成的事件（通常由 Avatar 收集并展示）
        payload: 可选的结构化数据，便于上层消费（如数值、战斗结果等）
        next_action: 可选的“建议下一个动作”（名称, 参数）供上层调度策略参考
    """

    status: ActionStatus
    events: List[Any]
    payload: Optional[Dict[str, Any]] = None
    next_action: Optional[tuple[str, Dict[str, Any]]] = None


@dataclass
class ActionPlan:
    """
    计划中的动作项：尚未提交执行。
    仅包含 class 名与参数，外加可选的调度策略字段。
    """
    action_name: str
    params: Dict[str, Any]
    priority: int = 0
    expiry_month: Optional[int] = None  # 到期月戳；None 为不过期
    max_retries: int = 0
    attempted: int = 0
    # 谁把这个计划装进来的。默认是 REACTIVE_RESPONSE 而不是自主选择：
    # 任何没有显式声明「这是本人自己选的」的路径（包括读档重建、
    # 抢占注入、互动响应）都必须被当成被动反应，见 ActionOrigin。
    # 这是运行时证据，不进存档：读档后没有证据，就 fail closed。
    origin: ActionOrigin = ActionOrigin.REACTIVE_RESPONSE
    
    def to_dict(self) -> dict:
        """转换为可序列化的字典"""
        return {
            "action_name": self.action_name,
            "params": self.params,
            "priority": self.priority,
            "expiry_month": self.expiry_month,
            "max_retries": self.max_retries,
            "attempted": self.attempted
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "ActionPlan":
        """从字典重建ActionPlan"""
        return cls(
            action_name=data["action_name"],
            params=data["params"],
            priority=data.get("priority", 0),
            expiry_month=data.get("expiry_month"),
            max_retries=data.get("max_retries", 0),
            attempted=data.get("attempted", 0)
        )


@dataclass
class ActionInstance:
    """
    已提交并开始执行的动作实例。
    """
    action: Any  # src.classes.action.Action
    params: Dict[str, Any]
    status: str = "running"  # 遗留字段：Avatar 以字符串记录运行态
