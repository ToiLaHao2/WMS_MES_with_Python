import heapq
from typing import List, Tuple, Set, Dict, Optional
from .model import Node


class AStarAlgorithm:
    """
    Thuật toán A* cơ bản trên không gian 2D.
    Dùng cho trường hợp chỉ có 1 AGV hoặc không cần phối hợp.
    """
    def __init__(self, grid: List[List[int]]):
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0]) if self.rows > 0 else 0

    def heuristic(self, a: Node, b: Node) -> float:
        # Khoảng cách Manhattan: |x1 - x2| + |y1 - y2|
        return abs(a.x - b.x) + abs(a.y - b.y)

    def get_neighbors(self, node: Node, end_node: Node) -> List[Node]:
        neighbors = []
        # 4 hướng di chuyển: Lên, Xuống, Trái, Phải
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = node.x + dx, node.y + dy
            
            # Kiểm tra xem có nằm trong bản đồ không
            if 0 <= nx < self.cols and 0 <= ny < self.rows:
                # Kiểm tra vật cản (Giá trị 1 là GRID_STORAGE, 2 là GRID_BLOCKED)
                tile_value = self.grid[ny][nx]
                
                # Kiểm tra ràng buộc di chuyển (Chống đi tắt qua ngã 4)
                # Tuy nhiên, nếu ô tiếp theo chính là đích đến (end_node) thì được phép rẽ vào để đỗ
                if not (nx == end_node.x and ny == end_node.y):
                    current_tile = self.grid[node.y][node.x]
                    if current_tile == 8 and dx != 0:
                        continue  # Đang ở đường Dọc, cấm rẽ Ngang
                    if current_tile == 7 and dy != 0:
                        continue  # Đang ở đường Ngang, cấm rẽ Dọc

                # Cho phép đi vào nếu nó là ô đích (end_node) dù nó là Storage/Charging, 
                # hoặc nếu nó là đường đi chính thức (0, 7, 8)
                if (nx == end_node.x and ny == end_node.y) or tile_value in (0, 7, 8):
                    neighbors.append(Node(nx, ny))
        return neighbors

    def find_path(self, start_pos: Tuple[int, int], end_pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        start_node = Node(start_pos[0], start_pos[1])
        end_node = Node(end_pos[0], end_pos[1])

        # Danh sách các node đang chờ xem xét (Priority Queue)
        open_list = []
        heapq.heappush(open_list, start_node)
        
        # Danh sách các node đã xử lý xong (dùng set để tìm kiếm cực nhanh)
        closed_list: Set[Node] = set()
        
        # Lưu trữ chi phí g tốt nhất đến từng node
        g_score = {start_node: 0}

        while open_list:
            # Lấy node có f thấp nhất ra
            current_node = heapq.heappop(open_list)

            # Nếu đã đến đích
            if current_node == end_node:
                path = []
                while current_node:
                    path.append((current_node.x, current_node.y))
                    current_node = current_node.parent
                return path[::-1] # Đảo ngược lại để có đường đi từ đầu đến cuối

            closed_list.add(current_node)

            for neighbor in self.get_neighbors(current_node, end_node):
                if neighbor in closed_list:
                    continue

                # Giả sử mỗi bước đi tốn chi phí là 1
                tentative_g_score = g_score[current_node] + 1

                if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                    neighbor.parent = current_node
                    neighbor.g = tentative_g_score
                    neighbor.h = self.heuristic(neighbor, end_node)
                    neighbor.f = neighbor.g + neighbor.h
                    g_score[neighbor] = tentative_g_score
                    
                    if neighbor not in open_list:
                        heapq.heappush(open_list, neighbor)

        return [] # Không tìm thấy đường đi


class TimeSpaceAStarAlgorithm:
    """
    Thuật toán Time-Space A* (Cooperative A*) trên không gian 3D (x, y, t).
    
    Sử dụng Reservation Table để phối hợp nhiều AGV cùng lúc:
    - AGV đến trước đặt lịch trình vào bảng.
    - AGV đến sau kiểm tra bảng để tránh va chạm.
    - AGV có thể WAIT (đứng yên) nếu ô phía trước bị chiếm tạm thời.
    """

    # Giới hạn thời gian tìm kiếm tối đa (tránh vòng lặp vô hạn)
    MAX_TIME_STEPS = 200
    # Số lần tối đa AGV được phép đứng chờ liên tiếp
    MAX_WAIT_STEPS = 15

    def __init__(self, grid: List[List[int]]):
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0]) if self.rows > 0 else 0

    def heuristic(self, node: Node, goal: Node) -> float:
        """Khoảng cách Manhattan (không tính thời gian)."""
        return abs(node.x - goal.x) + abs(node.y - goal.y)

    def _is_walkable(self, x: int, y: int, end_node: Node) -> bool:
        """Kiểm tra ô (x, y) có đi vào được không (dựa trên bản đồ tĩnh)."""
        if not (0 <= x < self.cols and 0 <= y < self.rows):
            return False
        tile_value = self.grid[y][x]
        # Cho phép đi vào nếu là ô đích, hoặc là đường đi (0, 7, 8)
        if x == end_node.x and y == end_node.y:
            return True
        return tile_value in (0, 7, 8)

    def _check_turn_constraint(self, cur_x: int, cur_y: int, dx: int, dy: int, end_node: Node) -> bool:
        """
        Kiểm tra ràng buộc rẽ hướng (đường 1 chiều ngang/dọc).
        Trả về True nếu được phép rẽ, False nếu bị cấm.
        """
        # Nếu ô tiếp theo là đích thì luôn được phép rẽ vào
        nx, ny = cur_x + dx, cur_y + dy
        if nx == end_node.x and ny == end_node.y:
            return True
        current_tile = self.grid[cur_y][cur_x]
        if current_tile == 8 and dx != 0:
            return False  # Đang ở đường Dọc, cấm rẽ Ngang
        if current_tile == 7 and dy != 0:
            return False  # Đang ở đường Ngang, cấm rẽ Dọc
        return True

    def _is_reserved(self, x: int, y: int, t: int,
                     reservation_table: Dict[Tuple[int, int, int], str],
                     agv_id: str) -> bool:
        """Kiểm tra ô (x, y) tại thời điểm t đã bị AGV khác đặt chỗ chưa."""
        occupant = reservation_table.get((x, y, t))
        if occupant is not None and occupant != agv_id and occupant != "PHYSICAL_OBSTACLE":
            return True
        return False

    def _has_swap_conflict(self, cur_x: int, cur_y: int, next_x: int, next_y: int, t: int,
                           reservation_table: Dict[Tuple[int, int, int], str],
                           agv_id: str) -> bool:
        """
        Kiểm tra va chạm ngược chiều (swap conflict):
        AGV A đi từ (cx, cy) sang (nx, ny) ở thời điểm t,
        trong khi AGV B đi từ (nx, ny) sang (cx, cy) ở cùng thời điểm t.
        """
        # Nếu ô (cx, cy) ở thời điểm t+1 bị AGV khác chiếm, 
        # VÀ ô (nx, ny) ở thời điểm t bị chính AGV đó chiếm → swap conflict
        occupant_at_current_next = reservation_table.get((cur_x, cur_y, t + 1))
        occupant_at_next_current = reservation_table.get((next_x, next_y, t))
        
        if (occupant_at_current_next is not None and occupant_at_current_next != agv_id and
            occupant_at_next_current is not None and occupant_at_next_current != agv_id and
            occupant_at_current_next == occupant_at_next_current):
            return True
        return False

    def _count_consecutive_waits(self, node: Node) -> int:
        """Đếm số lần WAIT liên tiếp bằng cách truy ngược parent chain."""
        count = 0
        current = node
        while current and current.parent:
            if current.x == current.parent.x and current.y == current.parent.y:
                count += 1
                current = current.parent
            else:
                break
        return count

    def find_path(
        self,
        start_pos: Tuple[int, int],
        end_pos: Tuple[int, int],
        reservation_table: Optional[Dict[Tuple[int, int, int], str]] = None,
        agv_id: str = "",
        start_time: int = 0,
    ) -> List[Tuple[int, int]]:
        """
        Tìm đường trong không gian Time-Space (x, y, t).

        Args:
            start_pos: Tọa độ bắt đầu (x, y)
            end_pos: Tọa độ đích (x, y)
            reservation_table: Bảng đặt chỗ {(x, y, t): agv_id}
            agv_id: ID của AGV đang tìm đường
            start_time: Thời điểm bắt đầu di chuyển

        Returns:
            Danh sách tọa độ [(x1, y1), (x2, y2), ...] (bao gồm cả ô WAIT lặp lại)
        """
        if reservation_table is None:
            reservation_table = {}

        start_node = Node(start_pos[0], start_pos[1], t=start_time)
        end_node = Node(end_pos[0], end_pos[1])  # Đích chỉ cần khớp (x, y)

        open_list: list = []
        heapq.heappush(open_list, start_node)

        # closed_set dùng (x, y, t) để tránh xét lại cùng trạng thái
        closed_set: Set[Tuple[int, int, int]] = set()

        # g_score lưu chi phí tốt nhất đến từng trạng thái (x, y, t)
        g_score: Dict[Tuple[int, int, int], float] = {
            (start_node.x, start_node.y, start_node.t): 0
        }

        while open_list:
            current = heapq.heappop(open_list)

            # Kiểm tra đã tới đích chưa (chỉ so sánh x, y, bỏ qua t)
            if current.x == end_node.x and current.y == end_node.y:
                # Truy ngược parent chain để lấy đường đi
                path = []
                node = current
                while node:
                    path.append((node.x, node.y))
                    node = node.parent
                return path[::-1]

            state_key = (current.x, current.y, current.t)
            if state_key in closed_set:
                continue
            closed_set.add(state_key)

            # Giới hạn thời gian tìm kiếm
            if current.t >= start_time + self.MAX_TIME_STEPS:
                continue

            next_t = current.t + 1

            # ═══ Sinh các neighbor: 4 hướng di chuyển + 1 hành động WAIT ═══
            candidates: List[Tuple[Node, float]] = []

            # --- 4 hướng di chuyển ---
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = current.x + dx, current.y + dy

                if not self._is_walkable(nx, ny, end_node):
                    continue
                if not self._check_turn_constraint(current.x, current.y, dx, dy, end_node):
                    continue
                # Kiểm tra reservation table (Hard block)
                if self._is_reserved(nx, ny, next_t, reservation_table, agv_id):
                    continue
                # Kiểm tra swap conflict
                if self._has_swap_conflict(current.x, current.y, nx, ny, current.t, reservation_table, agv_id):
                    continue

                # Soft block penalty cho PHYSICAL_OBSTACLE
                occupant = reservation_table.get((nx, ny, next_t))
                penalty = 1000.0 if occupant == "PHYSICAL_OBSTACLE" else 0.0

                candidates.append((Node(nx, ny, t=next_t), penalty))

            # --- Hành động WAIT (đứng yên tại chỗ) ---
            consecutive_waits = self._count_consecutive_waits(current)
            if consecutive_waits < self.MAX_WAIT_STEPS:
                # Chỉ cho phép WAIT nếu ô hiện tại không bị AGV khác chiếm (ngoại trừ PHYSICAL_OBSTACLE)
                if not self._is_reserved(current.x, current.y, next_t, reservation_table, agv_id):
                    occupant = reservation_table.get((current.x, current.y, next_t))
                    penalty = 1000.0 if occupant == "PHYSICAL_OBSTACLE" else 0.0
                    wait_node = Node(current.x, current.y, t=next_t)
                    candidates.append((wait_node, penalty))

            # ═══ Đánh giá từng candidate ═══
            for neighbor, extra_penalty in candidates:
                n_state = (neighbor.x, neighbor.y, neighbor.t)
                if n_state in closed_set:
                    continue

                # Chi phí di chuyển = 1, chi phí chờ = 1.5 (khuyến khích di chuyển hơn đứng chờ)
                is_wait = (neighbor.x == current.x and neighbor.y == current.y)
                move_cost = 1.5 if is_wait else 1.0
                tentative_g = g_score.get(state_key, float('inf')) + move_cost + extra_penalty

                if tentative_g < g_score.get(n_state, float('inf')):
                    neighbor.parent = current
                    neighbor.g = tentative_g
                    neighbor.h = self.heuristic(neighbor, end_node)
                    neighbor.f = neighbor.g + neighbor.h
                    g_score[n_state] = tentative_g
                    heapq.heappush(open_list, neighbor)

        # Không tìm được đường (có thể do bị chặn hoàn toàn)
        return []
