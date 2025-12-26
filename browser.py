# browser.py
"""
Browser management for YokTez MCP.

Provides browser context pooling for efficient resource reuse,
reducing overhead from creating new browser contexts for each request.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class BrowserContextPool:
    """
    Manages a pool of reusable browser contexts for efficient resource usage.

    Instead of creating a new browser context for each request, contexts are
    reused from a pool, significantly reducing overhead for concurrent operations.
    """

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        max_contexts: int = 3,
        context_ttl_seconds: int = 300,
        headless: bool = True,
        user_agent: Optional[str] = None
    ):
        """
        Initialize browser context pool.

        Args:
            max_contexts: Maximum number of contexts in the pool.
            context_ttl_seconds: Time-to-live for idle contexts (not implemented yet).
            headless: Whether to run browser in headless mode.
            user_agent: Custom user agent string.
        """
        self._max_contexts = max_contexts
        self._ttl = context_ttl_seconds
        self._headless = headless
        self._user_agent = user_agent or self.DEFAULT_USER_AGENT

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._available_contexts: asyncio.Queue[BrowserContext] = asyncio.Queue()
        self._active_count = 0
        self._lock = asyncio.Lock()
        self._initialized = False

    async def _ensure_browser(self) -> Browser:
        """Ensure browser is started (lazy initialization)."""
        if not self._initialized:
            async with self._lock:
                if not self._initialized:
                    logger.info("Initializing browser pool...")
                    self._playwright = await async_playwright().start()
                    self._browser = await self._playwright.chromium.launch(
                        headless=self._headless
                    )
                    self._initialized = True
                    logger.info(f"Browser pool initialized (headless: {self._headless})")

        if self._browser is None or not self._browser.is_connected():
            raise RuntimeError("Browser not available or disconnected")

        return self._browser

    async def _create_context(self) -> BrowserContext:
        """Create a new browser context with configured options."""
        browser = await self._ensure_browser()
        context = await browser.new_context(
            user_agent=self._user_agent,
            java_script_enabled=True,
            accept_downloads=False,
            bypass_csp=False
        )
        return context

    @asynccontextmanager
    async def acquire_page(self):
        """
        Acquire a page from the pool, creating context if needed.

        Usage:
            async with pool.acquire_page() as page:
                await page.goto("https://example.com")
                content = await page.content()

        Yields:
            Page: A Playwright page ready for use.
        """
        context: Optional[BrowserContext] = None
        page: Optional[Page] = None

        # Ensure browser is initialized BEFORE acquiring lock to prevent deadlock
        # (_ensure_browser also uses self._lock internally)
        await self._ensure_browser()

        try:
            # Try to get existing context from pool
            try:
                context = self._available_contexts.get_nowait()
                logger.debug("Reusing context from pool")
            except asyncio.QueueEmpty:
                async with self._lock:
                    if self._active_count < self._max_contexts:
                        context = await self._create_context()
                        self._active_count += 1
                        logger.debug(f"Created new context (active: {self._active_count}/{self._max_contexts})")
                    else:
                        # Wait for available context
                        logger.debug("Pool full, waiting for available context...")
                        context = await self._available_contexts.get()
                        logger.debug("Got context from pool after waiting")

            # Create page from context
            page = await context.new_page()
            yield page

        finally:
            # Close page but return context to pool
            if page:
                try:
                    await page.close()
                except Exception as e:
                    logger.warning(f"Error closing page: {e}")

            if context:
                try:
                    # Return context to pool for reuse
                    await self._available_contexts.put(context)
                    logger.debug("Returned context to pool")
                except Exception as e:
                    logger.warning(f"Error returning context to pool: {e}")
                    # If we can't return it, close it and decrement counter
                    try:
                        await context.close()
                    except Exception:
                        pass
                    async with self._lock:
                        self._active_count = max(0, self._active_count - 1)

    async def warmup(self, count: int = 1) -> None:
        """
        Pre-create contexts to warm up the pool.

        Args:
            count: Number of contexts to pre-create.
        """
        count = min(count, self._max_contexts)
        logger.info(f"Warming up browser pool with {count} context(s)...")

        for _ in range(count):
            async with self._lock:
                if self._active_count < self._max_contexts:
                    try:
                        context = await self._create_context()
                        self._active_count += 1
                        await self._available_contexts.put(context)
                    except Exception as e:
                        logger.error(f"Error during warmup: {e}")
                        break

        logger.info(f"Browser pool warmed up: {self._active_count} context(s) ready")

    async def close(self) -> None:
        """Close all resources and cleanup."""
        logger.info("Closing browser pool...")

        # Drain pool and close all contexts
        while not self._available_contexts.empty():
            try:
                ctx = self._available_contexts.get_nowait()
                await ctx.close()
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.warning(f"Error closing context: {e}")

        # Close browser
        if self._browser and self._browser.is_connected():
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
            self._browser = None

        # Stop playwright
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning(f"Error stopping playwright: {e}")
            self._playwright = None

        self._initialized = False
        self._active_count = 0
        logger.info("Browser pool closed")

    @property
    def stats(self) -> dict:
        """Get pool statistics."""
        return {
            "initialized": self._initialized,
            "max_contexts": self._max_contexts,
            "active_contexts": self._active_count,
            "available_contexts": self._available_contexts.qsize(),
            "headless": self._headless
        }


class BrowserManager:
    """
    Simple browser manager for backward compatibility.

    Wraps BrowserContextPool for easy integration with existing code.
    """

    def __init__(
        self,
        headless: bool = True,
        pool_size: int = 3,
        user_agent: Optional[str] = None
    ):
        """
        Initialize browser manager.

        Args:
            headless: Whether to run browser in headless mode.
            pool_size: Size of the context pool.
            user_agent: Custom user agent string.
        """
        self._pool = BrowserContextPool(
            max_contexts=pool_size,
            headless=headless,
            user_agent=user_agent
        )

    @asynccontextmanager
    async def get_page(self):
        """Get a page from the pool."""
        async with self._pool.acquire_page() as page:
            yield page

    async def warmup(self, count: int = 1) -> None:
        """Warm up the browser pool."""
        await self._pool.warmup(count)

    async def close(self) -> None:
        """Close the browser manager."""
        await self._pool.close()

    @property
    def stats(self) -> dict:
        """Get browser manager statistics."""
        return self._pool.stats
