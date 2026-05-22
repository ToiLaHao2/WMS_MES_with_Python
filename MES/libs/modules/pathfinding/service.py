from typing import List, Tuple, Optional
from libs.core.cache.manager import CacheManager
from libs.core.logger import logger
from .algorithm import AStarAlgorithm

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
        Hàm thực hiện tìm đường
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
