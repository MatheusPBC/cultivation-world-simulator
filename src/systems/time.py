from dataclasses import dataclass
from enum import Enum
from src.i18n import t


@dataclass(frozen=True, slots=True)
class WorldClock:
    """Medieval simulation time as an absolute day in a 12 × 30-day calendar."""

    absolute_day: int = 0

    DAYS_PER_MONTH = 30
    MONTHS_PER_YEAR = 12

    def __post_init__(self) -> None:
        if isinstance(self.absolute_day, bool) or not isinstance(self.absolute_day, int):
            raise TypeError("absolute_day must be an integer")
        if self.absolute_day < 0:
            raise ValueError("absolute_day must not be negative")

    @property
    def calendar_date(self) -> tuple[int, int, int]:
        """Return ``(year, month, day)`` with one-based month and day values."""
        year, day_of_year = divmod(self.absolute_day, self.DAYS_PER_MONTH * self.MONTHS_PER_YEAR)
        month_index, day_index = divmod(day_of_year, self.DAYS_PER_MONTH)
        return year, month_index + 1, day_index + 1

    def advance(self, days: int = 1) -> "WorldClock":
        if isinstance(days, bool) or not isinstance(days, int):
            raise TypeError("days must be an integer")
        if days < 0:
            raise ValueError("days must not be negative")
        return WorldClock(self.absolute_day + days)

class Month(Enum):
    JANUARY = 1
    FEBRUARY = 2
    MARCH = 3
    APRIL = 4
    MAY = 5
    JUNE = 6
    JULY = 7
    AUGUST = 8
    SEPTEMBER = 9
    OCTOBER = 10
    NOVEMBER = 11
    DECEMBER = 12

    def __str__(self) -> str:
        return str(self.value) 

    def __repr__(self) -> str:
        return str(self.value) 

class Year(int):
    def __add__(self, other: int) -> 'Year':
        return Year(int(self) + other)

class MonthStamp(int):
    """
    0年1月 = 0
    之后依次递增
    """
    def get_month(self) -> Month:
        month_value = (self % 12) + 1
        return Month(month_value if month_value <= 12 else 12)

    def get_year(self) -> Year:
        return Year(self // 12)

    def __add__(self, other: int) -> 'MonthStamp':
        return MonthStamp(int(self) + other)

def create_month_stamp(year: Year, month: Month) -> MonthStamp:
    """从年和月创建MonthStamp"""
    return MonthStamp(int(year) * 12 + month.value - 1)

def get_date_str(stamp: int) -> str:
    """将 MonthStamp (int) 转换为 'X年Y月' 格式"""
    ms = MonthStamp(stamp)
    return t("date_format_year_month", year=ms.get_year(), month=ms.get_month().value)
