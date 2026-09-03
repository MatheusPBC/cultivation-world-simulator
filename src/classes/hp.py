from dataclasses import dataclass

from src.systems.cultivation import Realm

@dataclass
class HP:
    """
    血量。
    会因为战斗，天灾或者其他原因降低cur。
    会随时间或者服用丹药等补充cur。
    会因为突破境界，服用丹药等增加max。
    """
    max: int 
    cur: int 

    def __post_init__(self) -> None:
        self.max = max(0, int(self.max))
        self.cur = max(0, min(self.max, int(self.cur)))

    def reduce(self, value_2_reduce:int) -> bool:
        self.cur = max(0, self.cur - max(0, int(value_2_reduce)))
        return self.cur > 0

    def recover(self, value_2_recover:int) -> bool:
        self.cur = min(self.max, self.cur + max(0, int(value_2_recover)))
        return True

    def add_max(self, value_2_add:int) -> bool:
        self.max = max(0, self.max + int(value_2_add))
        self.cur = min(self.cur, self.max)
        return True

    def __str__(self) -> str:
        return f"{self.cur}/{self.max}"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    # 比较运算符，使用cur进行比较
    def __eq__(self, other) -> bool:
        if isinstance(other, HP):
            return self.cur == other.cur
        return self.cur == other
    
    def __ne__(self, other) -> bool:
        if isinstance(other, HP):
            return self.cur != other.cur
        return self.cur != other
    
    def __lt__(self, other) -> bool:
        if isinstance(other, HP):
            return self.cur < other.cur
        return self.cur < other
    
    def __le__(self, other) -> bool:
        if isinstance(other, HP):
            return self.cur <= other.cur
        return self.cur <= other
    
    def __gt__(self, other) -> bool:
        if isinstance(other, HP):
            return self.cur > other.cur
        return self.cur > other
    
    def __ge__(self, other) -> bool:
        if isinstance(other, HP):
            return self.cur >= other.cur
        return self.cur >= other
    
    def to_dict(self) -> dict:
        """转换为可序列化的字典"""
        return {"max": self.max, "cur": self.cur}
    
    @classmethod
    def from_dict(cls, data: dict) -> "HP":
        """从字典重建HP"""
        return cls(max=data["max"], cur=data["cur"])
        
HP_MAX_BY_REALM = {
    Realm.Qi_Refinement: 100,
    Realm.Foundation_Establishment: 200,
    Realm.Core_Formation: 300,
    Realm.Nascent_Soul: 400,
}
