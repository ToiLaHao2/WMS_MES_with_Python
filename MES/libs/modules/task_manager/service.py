import time
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
        agv_id: str = "",
    ) -> dict:
        """
        Sinh ra kế hoạch di chuyển đầy đủ cho 1 AGV.
        
        Nếu có agv_id → sử dụng Time-Space A* (phối hợp tránh va chạm).
        Nếu không có agv_id → fallback về A* cơ bản.
        
        Trả về dict dạng:
        {
            "success": bool,
            "message": str,
            "waypoints": [{"x": int, "y": int, "action": str}, ...]
        }
        """
        logger.info(
            f"[Dispatch] AGV {agv_id or '???'} tại {agv_position} | Lấy hàng tại {pickup_point} | Cất tại {slot_position}"
        )

        use_cooperative = bool(agv_id)
        waypoints = []
        current_time = int(time.time())  # Bắt đầu tính bằng UNIX timestamp tuyệt đối

        # === Chặng 1: AGV đi tới điểm lấy hàng ===
        if use_cooperative:
            path_to_pickup = await self.path_service.get_cooperative_path(
                warehouse_id, agv_id, agv_position, pickup_point, start_time=current_time
            )
        else:
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
        # Bỏ điểm đầu tiên vì AGV đã ở đó sẵn
        # Trừ bước cuối cùng là PICK_UP
        for i, point in enumerate(path_to_pickup[1:]):
            if i == len(path_to_pickup[1:]) - 1:
                # Tại điểm lấy hàng, tốn 2s để gắp hàng -> cần reserve thêm 2 ô WAIT để khớp với Go manager
                waypoints.append({"x": point[0], "y": point[1], "action": "PICK_UP"})
                waypoints.append({"x": point[0], "y": point[1], "action": "WAIT"})
                waypoints.append({"x": point[0], "y": point[1], "action": "WAIT"})
            else:
                waypoints.append({"x": point[0], "y": point[1], "action": "MOVE"})

        # Cập nhật thời gian tích lũy (đã bỏ 1 điểm đầu, cộng thêm 2 giây gắp hàng)
        current_time += len(path_to_pickup) - 1 + 2

        if use_cooperative:
            # AGV sẽ đứng yên tại pickup_point thêm 2 giây (vì action = PICK_UP tốn 2s trong Go)
            # Cần reserve vị trí này để tránh AGV khác đâm vào
            await self.path_service.reserve_path(
                warehouse_id, agv_id, [pickup_point, pickup_point], start_time=current_time
            )
            current_time += 2

        # === Chặng 2: AGV đi từ điểm lấy hàng tới Slot đích ===
        if use_cooperative:
            # Xóa reservation chặng 1 trước khi đặt chặng 2
            # (để AGV khác có thể dùng các ô đã đi qua)
            path_to_slot = await self.path_service.get_cooperative_path(
                warehouse_id, agv_id, pickup_point, slot_position, start_time=current_time
            )
        else:
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
            if i == len(path_to_slot[1:]) - 1:
                # Tại điểm cất hàng, tốn 2s để cất hàng
                waypoints.append({"x": point[0], "y": point[1], "action": "DROP_OFF"})
                waypoints.append({"x": point[0], "y": point[1], "action": "WAIT"})
                waypoints.append({"x": point[0], "y": point[1], "action": "WAIT"})
            else:
                waypoints.append({"x": point[0], "y": point[1], "action": "MOVE"})

        # Cập nhật thời gian tích lũy
        current_time += len(path_to_slot) - 1

        if use_cooperative:
            # AGV đứng yên tại slot_position thêm 2 giây (vì action = DROP_OFF tốn 2s trong Go)
            await self.path_service.reserve_path(
                warehouse_id, agv_id, [slot_position, slot_position], start_time=current_time
            )
            current_time += 2

        # === Chặng 3: AGV quay về Charging Dock (vị trí ban đầu) ===
        if use_cooperative:
            path_to_dock = await self.path_service.get_cooperative_path(
                warehouse_id, agv_id, slot_position, agv_position, start_time=current_time
            )
        else:
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

    async def replan_execution_plan(
        self,
        warehouse_id: str,
        agv_id: str,
        current_position: Tuple[int, int],
        milestones: List[Tuple[int, int, str]],
        obstacles: List[Tuple[int, int]] = None
    ) -> dict:
        logger.info(f"[Replan] AGV {agv_id} at {current_position}. Milestones: {milestones}. Obstacles: {obstacles}")
        
        # 1. Clear old reservations
        await self.path_service.clear_reservation(warehouse_id, agv_id)
        
        # 2. Get current time
        import time
        current_time = int(time.time())
        waypoints = []
        
        # 3. Loop through milestones to build path
        prev_pos = current_position
        for (mx, my, action) in milestones:
            target_pos = (mx, my)
            path = await self.path_service.get_cooperative_path(
                warehouse_id, agv_id, prev_pos, target_pos, start_time=current_time, obstacles=obstacles
            )
            
            if not path:
                # Nếu không tìm được đường, reserve vị trí hiện tại thêm 5 giây để báo cho xe khác biết mình đang đứng đây chờ
                fallback_path = [current_position] * 5
                await self.path_service.reserve_path(
                    warehouse_id, agv_id, fallback_path, start_time=int(time.time())
                )
                return {
                    "success": False,
                    "message": f"Không tìm được đường Re-plan tới {target_pos}",
                    "waypoints": []
                }
            
            for i, point in enumerate(path[1:]):
                is_last = (i == len(path[1:]) - 1)
                
                if is_last:
                    waypoints.append({"x": point[0], "y": point[1], "action": action})
                    if action in ("PICK_UP", "DROP_OFF"):
                        waypoints.append({"x": point[0], "y": point[1], "action": "WAIT"})
                        waypoints.append({"x": point[0], "y": point[1], "action": "WAIT"})
                        await self.path_service.reserve_path(
                            warehouse_id, agv_id, [target_pos, target_pos], start_time=current_time + len(path) - 1
                        )
                        current_time += 2
                else:
                    waypoints.append({"x": point[0], "y": point[1], "action": "MOVE"})
            
            current_time += len(path) - 1
            prev_pos = target_pos
            
        return {
            "success": True,
            "message": "Replan thành công",
            "waypoints": waypoints
        }
