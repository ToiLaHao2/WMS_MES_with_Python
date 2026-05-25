import heapq
from typing import List, Tuple, Set
from .model import Node

class AStarAlgorithm:
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
