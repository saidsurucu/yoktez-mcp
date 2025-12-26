# cache.py
"""
Multi-tier caching system for YokTez MCP.

Provides persistent disk cache with async I/O for PDF files,
surviving server restarts and reducing network load.
"""
import asyncio
import hashlib
import json
import logging
import os
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any

try:
    import aiofiles
    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False

logger = logging.getLogger(__name__)


class LRUMemoryCache:
    """
    Size-limited LRU (Least Recently Used) in-memory cache for PDF bytes.
    Prevents memory bloat in long-running sessions.
    """

    def __init__(self, max_items: int = 50, max_size_mb: int = 100):
        """
        Initialize LRU cache with size limits.

        Args:
            max_items: Maximum number of items in cache.
            max_size_mb: Maximum total size in megabytes.
        """
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._max_items = max_items
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._current_size_bytes = 0

    def get(self, key: str) -> Optional[bytes]:
        """Get item from cache, updating LRU order."""
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: bytes) -> None:
        """Set item in cache with LRU eviction if needed."""
        value_size = len(value)

        # If key exists, remove old size
        if key in self._cache:
            self._current_size_bytes -= len(self._cache[key])
            del self._cache[key]

        # Evict until space is available
        while (self._current_size_bytes + value_size > self._max_size_bytes or
               len(self._cache) >= self._max_items):
            if not self._cache:
                break
            evicted_key, evicted_value = self._cache.popitem(last=False)
            self._current_size_bytes -= len(evicted_value)

        self._cache[key] = value
        self._current_size_bytes += value_size

    def has(self, key: str) -> bool:
        """Check if key exists in cache."""
        return key in self._cache

    def clear(self) -> None:
        """Clear all items from cache."""
        self._cache.clear()
        self._current_size_bytes = 0

    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "items": len(self._cache),
            "max_items": self._max_items,
            "size_mb": round(self._current_size_bytes / (1024 * 1024), 2),
            "max_size_mb": round(self._max_size_bytes / (1024 * 1024), 2)
        }


class DiskCache:
    """
    Persistent disk-based cache for PDF files.
    Survives server restarts and provides long-term caching.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_size_mb: int = 500,
        ttl_days: int = 30
    ):
        """
        Initialize disk cache.

        Args:
            cache_dir: Directory for cache files. Defaults to ~/.cache/yoktez-mcp
            max_size_mb: Maximum cache size in megabytes.
            ttl_days: Time-to-live in days for cached items.
        """
        if not AIOFILES_AVAILABLE:
            logger.warning("aiofiles not available. Disk cache will be disabled.")
            self._enabled = False
            return

        self._enabled = True
        self._cache_dir = cache_dir or (Path.home() / ".cache" / "yoktez-mcp")
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._ttl = timedelta(days=ttl_days)
        self._metadata_file = self._cache_dir / "cache_metadata.json"
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

        # Create cache directory
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._load_metadata_sync()

    def _get_cache_key(self, url: str) -> str:
        """Generate cache key from URL using SHA256 hash."""
        return hashlib.sha256(url.encode()).hexdigest()[:32]

    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for a key (uses subdirectories for efficiency)."""
        subdir = self._cache_dir / key[:2]
        subdir.mkdir(parents=True, exist_ok=True)
        return subdir / f"{key}.pdf"

    def _load_metadata_sync(self) -> None:
        """Load metadata synchronously (for initialization)."""
        if not self._enabled:
            return

        try:
            if self._metadata_file.exists():
                with open(self._metadata_file, 'r', encoding='utf-8') as f:
                    self._metadata = json.load(f)
                logger.info(f"Loaded cache metadata: {len(self._metadata)} entries")
        except Exception as e:
            logger.warning(f"Failed to load cache metadata: {e}")
            self._metadata = {}

    async def _save_metadata(self) -> None:
        """Save metadata to disk asynchronously."""
        if not self._enabled:
            return

        try:
            async with aiofiles.open(self._metadata_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self._metadata, indent=2))
        except Exception as e:
            logger.error(f"Failed to save cache metadata: {e}")

    async def get(self, url: str) -> Optional[bytes]:
        """
        Get cached PDF bytes for URL.

        Args:
            url: The URL to look up.

        Returns:
            Cached bytes if found and valid, None otherwise.
        """
        if not self._enabled:
            return None

        key = self._get_cache_key(url)
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        # Check TTL
        meta = self._metadata.get(key, {})
        if meta:
            cached_time = datetime.fromisoformat(meta.get("cached_at", "1970-01-01"))
            if datetime.now() - cached_time > self._ttl:
                logger.info(f"Disk cache TTL expired: {url[:60]}...")
                await self.delete(url)
                return None

        try:
            async with aiofiles.open(cache_path, 'rb') as f:
                data = await f.read()
            logger.info(f"Disk cache HIT: {url[:60]}... ({len(data)} bytes)")
            return data
        except Exception as e:
            logger.error(f"Failed to read from disk cache: {e}")
            return None

    async def set(self, url: str, data: bytes) -> None:
        """
        Cache PDF bytes for URL.

        Args:
            url: The URL to cache.
            data: The PDF bytes to cache.
        """
        if not self._enabled:
            return

        async with self._lock:
            key = self._get_cache_key(url)
            cache_path = self._get_cache_path(key)

            try:
                async with aiofiles.open(cache_path, 'wb') as f:
                    await f.write(data)

                self._metadata[key] = {
                    "url": url,
                    "size": len(data),
                    "cached_at": datetime.now().isoformat(),
                    "path": str(cache_path)
                }
                await self._save_metadata()
                logger.info(f"Disk cache SET: {url[:60]}... ({len(data)} bytes)")

                # Enforce size limit
                await self._enforce_size_limit()
            except Exception as e:
                logger.error(f"Failed to write to disk cache: {e}")

    async def delete(self, url: str) -> None:
        """Delete cached item for URL."""
        if not self._enabled:
            return

        key = self._get_cache_key(url)
        cache_path = self._get_cache_path(key)

        try:
            if cache_path.exists():
                os.remove(cache_path)
            if key in self._metadata:
                del self._metadata[key]
                await self._save_metadata()
        except Exception as e:
            logger.error(f"Failed to delete from disk cache: {e}")

    async def _enforce_size_limit(self) -> None:
        """Evict oldest items if cache exceeds size limit."""
        if not self._enabled:
            return

        total_size = sum(m.get("size", 0) for m in self._metadata.values())

        if total_size <= self._max_size_bytes:
            return

        # Sort by cached_at (oldest first)
        sorted_keys = sorted(
            self._metadata.keys(),
            key=lambda k: self._metadata[k].get("cached_at", "1970-01-01")
        )

        # Evict oldest until under limit
        for key in sorted_keys:
            if total_size <= self._max_size_bytes:
                break

            meta = self._metadata.get(key, {})
            cache_path = Path(meta.get("path", ""))

            try:
                if cache_path.exists():
                    os.remove(cache_path)
                total_size -= meta.get("size", 0)
                del self._metadata[key]
                logger.info(f"Disk cache EVICTED: {meta.get('url', key)[:60]}...")
            except Exception as e:
                logger.error(f"Failed to evict from disk cache: {e}")

        await self._save_metadata()

    async def clear(self) -> None:
        """Clear all cached items."""
        if not self._enabled:
            return

        async with self._lock:
            for key, meta in list(self._metadata.items()):
                try:
                    cache_path = Path(meta.get("path", ""))
                    if cache_path.exists():
                        os.remove(cache_path)
                except Exception:
                    pass

            self._metadata.clear()
            await self._save_metadata()
            logger.info("Disk cache cleared")

    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self._enabled:
            return {"enabled": False}

        total_size = sum(m.get("size", 0) for m in self._metadata.values())
        return {
            "enabled": True,
            "items": len(self._metadata),
            "size_mb": round(total_size / (1024 * 1024), 2),
            "max_size_mb": round(self._max_size_bytes / (1024 * 1024), 2),
            "cache_dir": str(self._cache_dir)
        }


class MultiTierCache:
    """
    Multi-tier cache combining memory and disk caching.
    Memory (L1) -> Disk (L2) -> Network (miss)
    """

    def __init__(
        self,
        memory_max_items: int = 50,
        memory_max_size_mb: int = 100,
        disk_cache_dir: Optional[Path] = None,
        disk_max_size_mb: int = 500,
        disk_ttl_days: int = 30,
        enable_disk_cache: bool = True
    ):
        """
        Initialize multi-tier cache.

        Args:
            memory_max_items: Max items in memory cache.
            memory_max_size_mb: Max size for memory cache.
            disk_cache_dir: Directory for disk cache.
            disk_max_size_mb: Max size for disk cache.
            disk_ttl_days: TTL for disk cache items.
            enable_disk_cache: Whether to enable disk caching.
        """
        self._memory_cache = LRUMemoryCache(
            max_items=memory_max_items,
            max_size_mb=memory_max_size_mb
        )

        self._disk_cache: Optional[DiskCache] = None
        if enable_disk_cache and AIOFILES_AVAILABLE:
            self._disk_cache = DiskCache(
                cache_dir=disk_cache_dir,
                max_size_mb=disk_max_size_mb,
                ttl_days=disk_ttl_days
            )

    async def get(self, key: str) -> Optional[bytes]:
        """
        Get item from cache (memory first, then disk).

        Args:
            key: Cache key (typically a URL).

        Returns:
            Cached bytes if found, None otherwise.
        """
        # L1: Memory cache
        cached = self._memory_cache.get(key)
        if cached is not None:
            logger.debug(f"L1 Memory cache HIT: {key[:60]}...")
            return cached

        # L2: Disk cache
        if self._disk_cache:
            cached = await self._disk_cache.get(key)
            if cached is not None:
                # Promote to memory cache
                self._memory_cache.set(key, cached)
                logger.debug(f"L2 Disk cache HIT (promoted to L1): {key[:60]}...")
                return cached

        return None

    async def set(self, key: str, value: bytes) -> None:
        """
        Set item in all cache tiers (write-through).

        Args:
            key: Cache key (typically a URL).
            value: Bytes to cache.
        """
        # Write to memory cache
        self._memory_cache.set(key, value)

        # Write to disk cache
        if self._disk_cache:
            await self._disk_cache.set(key, value)

    def has(self, key: str) -> bool:
        """Check if key exists in memory cache (fast check)."""
        return self._memory_cache.has(key)

    async def clear(self) -> None:
        """Clear all cache tiers."""
        self._memory_cache.clear()
        if self._disk_cache:
            await self._disk_cache.clear()

    @property
    def stats(self) -> Dict[str, Any]:
        """Get statistics for all cache tiers."""
        result = {
            "memory": self._memory_cache.stats,
            "disk": self._disk_cache.stats if self._disk_cache else {"enabled": False}
        }
        return result
