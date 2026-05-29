from dataclasses import dataclass
from typing import Optional

@dataclass
class Node:
    x: int
    y: int
    t: int = 0       # Thời điểm AGV ở tọa độ này (đơn vị: bước di chuyển)
    g: float = 0     # Chi phí từ điểm bắt đầu đến node hiện tại
    h: float = 0     # Chi phí ước tính từ node hiện tại đến đích (Heuristic)
    f: float = 0     # f = g + h
    parent: Optional['Node'] = None

    def __lt__(self, other):
        # Hổ trợ Priority Queue so sánh dựa trên giá trị f
        return self.f < other.f

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        return self.x == other.x and self.y == other.y and self.t == other.t

    def __hash__(self):
        # Dùng tọa độ + thời gian làm hash để phân biệt trạng thái trong không gian 3D
        return hash((self.x, self.y, self.t))