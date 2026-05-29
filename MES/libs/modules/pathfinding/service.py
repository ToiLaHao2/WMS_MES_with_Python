from typing import List, Tuple, Dict, Optional
from libs.core.cache.manager import CacheManager
from libs.core.logger import logger
from .algorithm import AStarAlgorithm, TimeSpaceAStarAlgorithm


class PathfindingService:
    def __init__(self):
        # Sử dụng CacheManager để lấy bản đồ từ Redis/Local RAM
        self.cache = CacheManager()

    async def get_warehouse_grid(self, warehouse_id: str) -> List[List[int]]:
        """
        Lấy bản đồ kho từ Cache (Ưu tiên RAM -> Redis)
        """
        cache_key = f"warehouse:{warehouse_id}:layout"
        grid = await self.cache.get(cache_key)
        
        if not grid:
            logger.warning(f"Không tìm thấy bản đồ cho kho {warehouse_id} trong Cache!")
            return []
            
        return grid

    async def get_path_for_warehouse(self, warehouse_id: str, start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
        """
        Hàm thực hiện tìm đường (A* cơ bản, không phối hợp)
        """
        # 1. Lấy bản đồ
        grid = await self.get_warehouse_grid(warehouse_id)
        if not grid:
            return []

        # 2. Chạy thuật toán A*
        try:
            algo = AStarAlgorithm(grid)
            path = algo.find_path(start, end)
            return path
        except Exception as e:
            logger.error(f"Lỗi khi chạy thuật toán A*: {str(e)}")
            return []

    # ═══════════════════════════════════════════════════════════════
    # TIME-SPACE A* — Phối hợp nhiều AGV cùng lúc
    # ═══════════════════════════════════════════════════════════════

    async def get_reservation_table(self, warehouse_id: str) -> Dict[Tuple[int, int, int], str]:
        """
        Đọc Reservation Table từ Redis.
        
        Cấu trúc Redis:
            Key: "reservation:{warehouse_id}"
            Value: JSON dict { "x,y,t": "agv_id", ... }
        
        Returns:
            Dict { (x, y, t): "agv_id" }
        """
        cache_key = f"reservation:{warehouse_id}"
        raw = await self.cache.get_direct(cache_key)
        
        if not raw or not isinstance(raw, dict):
            return {}
        
        # Convert key từ string "x,y,t" về tuple (x, y, t)
        table: Dict[Tuple[int, int, int], str] = {}
        for key_str, agv_id in raw.items():
            try:
                parts = key_str.split(",")
                x, y, t = int(parts[0]), int(parts[1]), int(parts[2])
                table[(x, y, t)] = agv_id
            except (ValueError, IndexError):
                continue
        
        return table

    async def reserve_path(
        self, warehouse_id: str, agv_id: str, 
        path: List[Tuple[int, int]], start_time: int = 0
    ) -> None:
        """
        Ghi lịch trình của AGV vào Reservation Table trên Redis.
        Mỗi ô trong path sẽ được đánh dấu (x, y, t) → agv_id.
        
        TTL = 300 giây (5 phút) để tự động dọn rác nếu AGV bị lỗi giữa chừng.
        """
        cache_key = f"reservation:{warehouse_id}"
        
        # Đọc bảng hiện tại
        raw = await self.cache.get_direct(cache_key)
        if not raw or not isinstance(raw, dict):
            raw = {}
        
        # Ghi thêm lịch trình mới
        for i, (x, y) in enumerate(path):
            t = start_time + i
            key_str = f"{x},{y},{t}"
            raw[key_str] = agv_id
        
        # Lưu lại lên Redis với TTL 5 phút
        await self.cache.set_direct(cache_key, raw, ttl=300)
        logger.info(f"[Reservation] Đã đặt {len(path)} ô cho AGV {agv_id} tại kho {warehouse_id}")

    async def clear_reservation(self, warehouse_id: str, agv_id: str) -> None:
        """
        Xóa toàn bộ lịch trình đã đặt của 1 AGV khỏi Reservation Table.
        Gọi khi AGV hoàn thành nhiệm vụ hoặc bị lỗi.
        """
        cache_key = f"reservation:{warehouse_id}"
        raw = await self.cache.get_direct(cache_key)
        
        if not raw or not isinstance(raw, dict):
            return
        
        # Lọc bỏ tất cả entry thuộc về agv_id
        cleaned = {k: v for k, v in raw.items() if v != agv_id}
        
        if cleaned:
            await self.cache.set_direct(cache_key, cleaned, ttl=300)
        else:
            await self.cache.delete(cache_key)
        
        logger.info(f"[Reservation] Đã xóa lịch trình của AGV {agv_id} tại kho {warehouse_id}")

    async def get_cooperative_path(
        self,
        warehouse_id: str,
        agv_id: str,
        start: Tuple[int, int],
        end: Tuple[int, int],
        start_time: int = 0,
    ) -> List[Tuple[int, int]]:
        """
        Tìm đường có phối hợp (Time-Space A*).
        
        1. Đọc Reservation Table hiện tại từ Redis.
        2. Chạy thuật toán Time-Space A* với bảng đó.
        3. Nếu tìm được đường → ghi lịch trình mới vào Redis.
        4. Trả về danh sách tọa độ (bao gồm cả ô WAIT lặp lại).
        """
        grid = await self.get_warehouse_grid(warehouse_id)
        if not grid:
            return []

        try:
            # 1. Đọc Reservation Table
            reservation_table = await self.get_reservation_table(warehouse_id)

            # 2. Chạy Time-Space A*
            algo = TimeSpaceAStarAlgorithm(grid)
            path = algo.find_path(start, end, reservation_table, agv_id, start_time)

            if not path:
                logger.warning(f"[TimeSpace A*] Không tìm được đường cho AGV {agv_id} từ {start} tới {end}")
                return []

            # 3. Ghi lịch trình vào Reservation Table
            await self.reserve_path(warehouse_id, agv_id, path, start_time)

            logger.info(f"[TimeSpace A*] AGV {agv_id}: {len(path)} bước từ {start} tới {end} (t={start_time})")
            return path

        except Exception as e:
            logger.error(f"[TimeSpace A*] Lỗi: {str(e)}")
            return []
