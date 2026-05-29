import grpc
from libs.core.contracts import mes_pb2, mes_pb2_grpc
from libs.core.logger import logger
from libs.modules.pathfinding.service import PathfindingService
from libs.modules.slot_allocation.service import SlotAllocationService
from libs.modules.task_manager.service import DispatchService


class PathfindingHandler(mes_pb2_grpc.PathfindingServiceServicer):
    """
    Handler tiếp nhận các cuộc gọi gRPC từ WMS (Node.js).
    """
    def __init__(self):
        # Khởi tạo Service từ tầng libs
        self.path_service = PathfindingService()

    async def CalculatePath(self, request, context):
        """
        Hàm xử lý logic tìm đường khi Node.js gọi qua gRPC
        """
        warehouse_id = request.warehouse_id
        start_pos = (request.start.x, request.start.y)
        end_pos = (request.end.x, request.end.y)

        logger.info(f"gRPC Request: Tìm đường cho kho {warehouse_id} từ {start_pos} tới {end_pos}")

        try:
            # Gọi vào tầng libs để xử lý logic A*
            path = await self.path_service.get_path_for_warehouse(warehouse_id, start_pos, end_pos)

            if not path:
                return mes_pb2.PathResponse(success=False, message="Không tìm thấy đường đi")

            # Convert kết quả mảng tọa độ sang định dạng gRPC Point
            waypoints = [mes_pb2.Point(x=p[0], y=p[1]) for p in path]

            return mes_pb2.PathResponse(
                waypoints=waypoints,
                success=True,
                message="Tìm đường thành công"
            )
        except Exception as e:
            logger.error(f"Lỗi gRPC CalculatePath: {str(e)}")
            return mes_pb2.PathResponse(success=False, message=str(e))

class SlotAllocationHandler(mes_pb2_grpc.SlotAllocationServiceServicer):
    def __init__(self):
        self.slot_service = SlotAllocationService()

    async def AllocateSlot(self, request, context):
        """
        Hàm xử lý logic cấp phát vị trí khi được gọi qua gRPC
        """
        warehouse_id = request.warehouse_id
        item_id = request.item_id
        length = request.length
        width = request.width

        logger.info(f"gRPC Request: Cấp phát vị trí cho kho {warehouse_id} với kiện {item_id}")

        try:
            # Gọi vào tầng libs để xử lý logic Best Fit
            result = await self.slot_service.allocate_optimal_slot(warehouse_id, item_id, length, width)

            # result là AllocationResult object, trả thẳng các trường về gRPC
            return mes_pb2.SlotAllocationResponse(
                success=result.success,
                slot_id=result.slot_id or "",
                message=result.message,
                error_code=result.error_code or ""
            )
        except Exception as e:
            logger.error(f"Lỗi gRPC AllocateSlot: {str(e)}")
            return mes_pb2.SlotAllocationResponse(
                success=False,
                message=str(e),
                error_code="INTERNAL_ERROR"
            )

    async def FreeSlot(self, request, context):
        """
        Hàm giải phóng slot khi có lỗi AGV.
        """
        warehouse_id = request.warehouse_id
        slot_id = request.slot_id
        
        logger.info(f"gRPC Request: FreeSlot {slot_id} tại kho {warehouse_id}")
        try:
            success = await self.slot_service.free_slot(warehouse_id, slot_id)
            return mes_pb2.FreeSlotResponse(
                success=success,
                message="Giải phóng slot thành công" if success else "Giải phóng slot thất bại"
            )
        except Exception as e:
            logger.error(f"Lỗi gRPC FreeSlot: {str(e)}")
            return mes_pb2.FreeSlotResponse(success=False, message=str(e))

class DispatchHandler(mes_pb2_grpc.DispatchServiceServicer):
    def __init__(self):
        self.dispatch_service = DispatchService()

    async def DispatchAGV(self, request, context):
        """
        Nhận thông tin từ WMS, tạo Execution Plan đầy đủ cho AGV.
        """
        warehouse_id = request.warehouse_id
        agv_pos = (request.agv_position.x, request.agv_position.y)
        pickup = (request.pickup_point.x, request.pickup_point.y)
        slot_pos = (request.slot_position.x, request.slot_position.y)
        agv_id = request.agv_id

        logger.info(f"gRPC Request: DispatchAGV cho kho {warehouse_id} (AGV: {agv_id})")

        try:
            plan = await self.dispatch_service.create_execution_plan(
                warehouse_id, agv_pos, pickup, slot_pos, agv_id=agv_id
            )

            if not plan["success"]:
                return mes_pb2.DispatchResponse(success=False, message=plan["message"])

            # Map hành động từ string sang enum proto
            action_map = {
                "MOVE": mes_pb2.ActionType.MOVE,
                "PICK_UP": mes_pb2.ActionType.PICK_UP,
                "DROP_OFF": mes_pb2.ActionType.DROP_OFF,
                "RETURN": mes_pb2.ActionType.RETURN,
            }

            waypoints = [
                mes_pb2.WaypointAction(
                    position=mes_pb2.Point(x=wp["x"], y=wp["y"]),
                    action=action_map.get(wp["action"], mes_pb2.ActionType.MOVE)
                )
                for wp in plan["waypoints"]
            ]

            return mes_pb2.DispatchResponse(
                success=True,
                message=plan["message"],
                waypoints=waypoints
            )
        except Exception as e:
            logger.error(f"Loi gRPC DispatchAGV: {str(e)}")
            return mes_pb2.DispatchResponse(success=False, message=str(e))