from typing import List, Tuple
from libs.core.logger import logger
from libs.modules.pathfinding.service import PathfindingService


class DispatchService:
    """
    Trình điều phối AGV — nối Pathfinding thành 1 Execution Plan hoàn chỉnh.
    Chặng 1: AGV vị trí hiện tại -> Điểm lấy hàng (pickup_point / Cửa kho)
    Chặng 2: Điểm lấy hàng -> Slot đích (slot_position)
    Chặng 3: Slot đích -> Quay về Charging Dock (agv_position ban đầu)
    """

    def __init__(self):
        self.path_service = PathfindingService()

    async def create_execution_plan(
        self,
        warehouse_id: str,
        agv_position: Tuple[int, int],
        pickup_point: Tuple[int, int],
        slot_position: Tuple[int, int],
    ) -> dict:
        """
        Sinh ra kế hoạch di chuyển đầy đủ cho 1 AGV.
        Trả về dict dạng:
        {
            "success": bool,
            "message": str,
            "waypoints": [{"x": int, "y": int, "action": str}, ...]
        }
        """
        logger.info(
            f"[Dispatch] AGV tại {agv_position} | Lấy hàng tại {pickup_point} | Cất tại {slot_position}"
        )

        waypoints = []

        # === Chặng 1: AGV đi tới điểm lấy hàng ===
        path_to_pickup = await self.path_service.get_path_for_warehouse(
            warehouse_id, agv_position, pickup_point
        )

        if not path_to_pickup:
            return {
                "success": False,
                "message": f"Không tìm được đường từ AGV tới điểm lấy hàng {pickup_point}",
                "waypoints": [],
            }

        # Tất cả các bước di chuyển đến điểm lấy hàng đều là MOVE
        # Trừ bước cuối cùng là PICK_UP
        for i, point in enumerate(path_to_pickup):
            action = "PICK_UP" if i == len(path_to_pickup) - 1 else "MOVE"
            waypoints.append({"x": point[0], "y": point[1], "action": action})

        # === Chặng 2: AGV đi từ điểm lấy hàng tới Slot đích ===
        path_to_slot = await self.path_service.get_path_for_warehouse(
            warehouse_id, pickup_point, slot_position
        )

        if not path_to_slot:
            return {
                "success": False,
                "message": f"Không tìm được đường từ điểm lấy hàng tới Slot {slot_position}",
                "waypoints": [],
            }

        # Bỏ điểm đầu tiên (đã có ở cuối chặng 1 rồi), trừ bước cuối là DROP_OFF
        for i, point in enumerate(path_to_slot[1:]):
            action = "DROP_OFF" if i == len(path_to_slot) - 2 else "MOVE"
            waypoints.append({"x": point[0], "y": point[1], "action": action})

        # === Chặng 3: AGV quay về Charging Dock (vị trí ban đầu) ===
        path_to_dock = await self.path_service.get_path_for_warehouse(
            warehouse_id, slot_position, agv_position
        )

        if path_to_dock and len(path_to_dock) > 1:
            # Bỏ điểm đầu (đã có ở cuối chặng 2), tất cả action = RETURN
            for point in path_to_dock[1:]:
                waypoints.append({"x": point[0], "y": point[1], "action": "RETURN"})

        logger.info(f"[Dispatch] Execution Plan: {len(waypoints)} bước (bao gồm quay về dock).")
        return {
            "success": True,
            "message": f"Tạo kế hoạch thành công ({len(waypoints)} bước)",
            "waypoints": waypoints,
        }

