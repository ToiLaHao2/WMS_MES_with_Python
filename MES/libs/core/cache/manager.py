from typing import Any, Optional
from .local_cache import LocalCache
from .redis_cache import RedisCache
from libs.core.config import settings

class CacheManager:
    """
    Bộ não điều phối Cache.

    Có 2 chiến lược đọc/ghi:

    1. get() / set() — Cache 2 lớp (L1 Local + L2 Redis)
       Dùng cho dữ liệu ÍT THAY ĐỔI: layout kho, config hệ thống, catalog...

    2. get_direct() / set_direct() — Chỉ Redis, KHÔNG qua Local Cache
       Dùng cho dữ liệu THAY ĐỔI LIÊN TỤC: trạng thái slot, AGV status...
       Tránh stale data do local cache chưa hết TTL.
    """
    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.local_cache = LocalCache()
        self.redis_cache = RedisCache(redis_url)

    # ─── CHIẾN LƯỢC 1: Cache 2 lớp (cho dữ liệu ít thay đổi) ───

    async def get(self, key: str) -> Optional[Any]:
        # 1. Thử lấy từ Local Cache (RAM)
        local_data = self.local_cache.get(key)
        if local_data is not None:
            print(f"[CACHE] HIT Local Cache: {key}")
            return local_data

        # 2. Nếu Local không có, gọi qua Redis
        print(f"[CACHE] MISS Local Cache. Thử lấy từ Redis: {key}")
        redis_data = await self.redis_cache.get(key)
        
        if redis_data is not None:
            # 3. Lưu ngược lại vào Local Cache để dùng cho lần sau
            print(f"[CACHE] HIT Redis. Lưu ngược vào Local Cache: {key}")
            self.local_cache.set(key, redis_data, ttl=300) # Lưu trong RAM 5 phút
            return redis_data
            
        print(f"[CACHE] MISS Redis luôn: {key}")
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Lưu đồng thời vào cả Local và Redis"""
        # Lưu vào Local
        self.local_cache.set(key, value, ttl)
        # Bắn lên Redis
        await self.redis_cache.set(key, value, ttl)

    # ─── CHIẾN LƯỢC 2: Chỉ Redis (cho dữ liệu mutable/state-sensitive) ───

    async def get_direct(self, key: str) -> Optional[Any]:
        """Đọc THẲNG từ Redis, bỏ qua Local Cache hoàn toàn."""
        print(f"[CACHE] DIRECT Redis GET: {key}")
        return await self.redis_cache.get(key)

    async def set_direct(self, key: str, value: Any, ttl: int = 86400) -> None:
        """Ghi THẲNG lên Redis, KHÔNG lưu vào Local Cache."""
        print(f"[CACHE] DIRECT Redis SET: {key}")
        await self.redis_cache.set(key, value, ttl)

    # ─── TIỆN ÍCH CHUNG ───

    async def acquire_lock(self, key: str, ttl: int = 5) -> bool:
        """
        Giao tiếp với Redis để lấy khóa phân tán (Distributed Lock).
        """
        return await self.redis_cache.acquire_lock(key, ttl)

    async def delete(self, key: str) -> None:
        """Xóa đồng thời ở cả 2 nơi"""
        self.local_cache.delete(key)
        await self.redis_cache.delete(key)

    async def close(self):
        """Dọn dẹp kết nối khi tắt server"""
        await self.redis_cache.close()

