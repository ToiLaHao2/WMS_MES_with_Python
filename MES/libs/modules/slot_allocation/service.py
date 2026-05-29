from typing import List
from libs.core.logger import logger
from libs.core.cache.manager import CacheManager
from .models import ItemRequest, SlotConfig, AllocationResult
from .algorithm import BestFitAllocator
from .exceptions import ItemTooLargeError, NoAvailableSlotError

class SlotAllocationService:
    def __init__(self):
        self.cache = CacheManager()
        self.allocator = BestFitAllocator()

    async def get_warehouse_slots(self, warehouse_id: str) -> List[SlotConfig]:
        """
        Lấy danh sách các slot trong kho TRỰC TIẾP từ Redis.
        Slot là dữ liệu mutable (thay đổi liên tục) nên KHÔNG đi qua Local Cache.
        """
        cache_key = f"warehouse:{warehouse_id}:slots"
        slots_data = await self.cache.get_direct(cache_key)
        
        if not slots_data:
            logger.warning(f"Không tìm thấy cấu hình slot cho kho {warehouse_id} trong Cache")
            return []
            
        return [SlotConfig(**slot) for slot in slots_data]

    async def allocate_optimal_slot(self, warehouse_id: str, item_id: str, length: float, width: float) -> AllocationResult:
        """
        Hàm chính được gRPC gọi vào.
        Toàn bộ luồng đọc/ghi slot đều dùng get_direct/set_direct (chỉ Redis, không local cache).
        """
        try:
            item = ItemRequest(item_id=item_id, length=length, width=width)
            cache_key = f"warehouse:{warehouse_id}:slots"
            
            # 1. Đọc THẲNG từ Redis (không qua local cache)
            slots = await self.get_warehouse_slots(warehouse_id)
            
            if not slots:
                 return AllocationResult(
                     success=False, 
                     message="Kho chưa được cấu hình slot hoặc lỗi Redis", 
                     error_code="WAREHOUSE_NOT_CONFIGURED"
                 )

            # 2. Đưa vào thuật toán tính toán
            optimal_slot = self.allocator.allocate(item, slots)
            
            # 3. THỬ GIÀNH KHÓA (DISTRIBUTED LOCK) TRƯỚC KHI TRẢ VỀ
            #    TTL = 120s để lock sống đủ lâu cho toàn bộ luồng AGV chạy xong
            lock_key = f"lock:slot:{optimal_slot.slot_id}"
            is_locked = await self.cache.acquire_lock(lock_key, ttl=120)
            
            if not is_locked:
                logger.warning(f"Race Condition: Slot {optimal_slot.slot_id} vừa bị nẫng tay trên. Yêu cầu chạy lại.")
                return AllocationResult(
                    success=False, 
                    message="Slot vừa bị hệ thống khác lấy. Vui lòng gửi lại yêu cầu.", 
                    error_code="RACE_CONDITION_RETRY"
                )
            
            # 4. KHÓA THÀNH CÔNG → Đánh dấu slot là occupied NGAY trên Redis
            slots_data = await self.cache.get_direct(cache_key)
            if slots_data:
                for slot_entry in slots_data:
                    if slot_entry.get("slot_id") == optimal_slot.slot_id:
                        slot_entry["is_occupied"] = True
                        break
                await self.cache.set_direct(cache_key, slots_data, ttl=86400)
            
            logger.info(f"Đã khóa và cấp slot {optimal_slot.slot_id} cho item {item_id}")
            return AllocationResult(
                success=True, 
                slot_id=optimal_slot.slot_id, 
                message="Tìm được vị trí cất hàng tối ưu",
                error_code="SUCCESS"
            )

        except ItemTooLargeError as e:
            logger.error(f"Slot Allocation: {str(e)}")
            return AllocationResult(success=False, message=str(e), error_code="ITEM_TOO_LARGE")
            
        except NoAvailableSlotError as e:
            logger.error(f"Slot Allocation: {str(e)}")
            return AllocationResult(success=False, message=str(e), error_code="NO_AVAILABLE_SLOT")
            
        except Exception as e:
            logger.error(f"Lỗi không xác định khi cấp phát slot: {str(e)}")
            return AllocationResult(success=False, message="Lỗi hệ thống nội bộ", error_code="INTERNAL_ERROR")

    async def free_slot(self, warehouse_id: str, slot_id: str) -> bool:
        """
        Giải phóng một slot bằng cách đặt is_occupied = False.
        """
        try:
            cache_key = f"warehouse:{warehouse_id}:slots"
            slots_data = await self.cache.get_direct(cache_key)
            if not slots_data:
                logger.warning(f"FreeSlot: Không tìm thấy data kho {warehouse_id}")
                return False

            updated = False
            for slot_entry in slots_data:
                if slot_entry.get("slot_id") == slot_id:
                    slot_entry["is_occupied"] = False
                    updated = True
                    break
            
            if updated:
                await self.cache.set_direct(cache_key, slots_data, ttl=86400)
                logger.info(f"Đã giải phóng slot {slot_id} của kho {warehouse_id}")
                return True
            else:
                logger.warning(f"FreeSlot: Không tìm thấy slot {slot_id} trong kho {warehouse_id}")
                return False
        except Exception as e:
            logger.error(f"Lỗi FreeSlot: {str(e)}")
            return False

