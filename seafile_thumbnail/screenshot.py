import asyncio
import threading
import queue
import logging
from contextlib import asynccontextmanager
from typing import Dict, Optional, Tuple, Any
from concurrent.futures import Future
from urllib.parse import urlparse

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Error as PlaywrightError
)

logger = logging.getLogger(__name__)


class PlaywrightManager:
    
    def __init__(
        self,
        page_timeout: int = 60_000,
        max_contexts: int = 8,  # Context pool size (adjust based on CPU cores)
        task_queue_maxsize: int = 100,  # Task queue capacity limit
        browser_launch_kwargs: Optional[Dict[str, Any]] = None,
    ):
        if hasattr(self, "_initialized"):
            return
        
        # Basic configuration
        self.page_timeout = page_timeout
        self.max_contexts = max_contexts
        self.browser_launch_kwargs = browser_launch_kwargs or {
            "headless": True,
            "args": [
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--disable-background-networking",
                "--start-maximized",
            ]
        }
        
        # Thread and loop control
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        
        # Task queue (rate limiting)
        self._task_queue: queue.Queue[Tuple[Dict, Future]] = queue.Queue(maxsize=task_queue_maxsize)
        
        # Playwright resources + context pool
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context_pool: Optional[asyncio.Queue[BrowserContext]] = None  # Context pool
        
        self._initialized = True
    
    def start(self):
        """Start background thread + initialize context pool"""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()
        self._ready_event.wait(timeout=10)  # Initialization timeout protection
        if not self._ready_event.is_set():
            raise RuntimeError("Playwright manager init timeout")
    
    def stop(self):
        """Graceful stop + resource cleanup"""
        if not self._thread or not self._thread.is_alive():
            return
        self._stop_event.set()
        self._task_queue.put(({"__stop__": True}, Future()))  # Wake up queue
        self._thread.join(timeout=30)
        
        # Cleanup context pool + browser
        if self._loop and not self._loop.is_closed():
            self._loop.run_until_complete(self._cleanup_all())
    
    def screenshot_from_url(
        self,
        url: str,
        save_path: str,
        div_selector: str = "#sdoc-editor-print-wrapper",
        request=None,
        access_token: Optional[str] = None,
    ) -> str:
        """Synchronous call: with timeout protection"""
        if not self._ready_event.is_set():
            raise RuntimeError("Manager not ready, call start() first")
        
        task = {
            "url": url,
            "save_path": save_path,
            "div_selector": div_selector,
            "request": request,
            "access_token": access_token,
        }
        fut = Future()
        try:
            self._task_queue.put((task, fut), block=True, timeout=5)  # Block 5s when queue is full
        except queue.Full:
            raise RuntimeError("Task queue full, try again later")
        
        try:
            return fut.result(timeout=self.page_timeout / 1000)  # Overall task timeout
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            raise
    
    # ------------------------------ Internal core logic ------------------------------
    def _thread_main(self):
        """Background thread: Run asyncio event loop"""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._async_main())
        except Exception as e:
            logger.error(f"Background thread error: {e}", exc_info=True)
            self._ready_event.clear()
        finally:
            if self._loop and not self._loop.is_closed():
                self._loop.close()
    
    async def _async_main(self):
        """Initialize Playwright + context pool + task consumption"""
        await self._init_browser_and_pool()
        self._ready_event.set()
        logger.info("Playwright manager ready")
        
        # Task consumption loop
        while not self._stop_event.is_set():
            try:
                task, fut = await self._loop.run_in_executor(None, self._task_queue.get, True, 0.5)
            except queue.Empty:
                continue
            
            if task.get("__stop__"):
                fut.set_result(None)
                break
            asyncio.create_task(self._handle_screenshot_task(task, fut))  # Process task asynchronously
    
    async def _init_browser_and_pool(self):
        """Initialize browser + context pool"""
        if not self._playwright:
            self._playwright = await async_playwright().start()
        if not self._browser or not self._browser.is_connected():
            self._browser = await self._playwright.chromium.launch(**self.browser_launch_kwargs)
        
        # Initialize context pool
        self._context_pool = asyncio.Queue(maxsize=self.max_contexts)
        for _ in range(self.max_contexts):
            context = await self._create_context()
            await self._context_pool.put(context)
    
    async def _create_context(self) -> BrowserContext:
        """Create context adapted for A4 size"""
        return await self._browser.new_context(
            viewport={"width": 1920, "height": 3000},  # Height for 3 A4 pages
            device_scale_factor=1,
            ignore_https_errors=True
        )
    
    @asynccontextmanager
    async def get_context(self):
        """Get context from pool: create temporary context on timeout"""
        if not self._context_pool:
            raise RuntimeError("Context pool not initialized")
        
        try:
            context = await asyncio.wait_for(self._context_pool.get(), timeout=3)
            is_temp = False
        except asyncio.TimeoutError:
            logger.warning("Context pool empty, create temp context")
            context = await self._create_context()
            is_temp = True
        
        try:
            yield context
        finally:
            if is_temp:
                await context.close()
            else:
                # Clean context state (avoid task contamination)
                await context.clear_cookies()
                await context.clear_permissions()
                await self._context_pool.put(context)
    
    async def _handle_screenshot_task(self, task: Dict, fut: Future):
        """Optimized screenshot task processing: granular timeout + lazy loading handling"""
        page: Optional[Page] = None
        try:
            # Browser health check + pool reconstruction
            if not self._browser or not self._browser.is_connected():
                await self._init_browser_and_pool()
            
            async with self.get_context() as context:
                page = await context.new_page()
                page.set_default_timeout(self.page_timeout)
                
                # 1. Inject cookies (optimization: cleaned after context reuse)
                await self._inject_cookies(page, task)
                
                # 2. Page loading: wait only for necessary state + handle lazy loading
                await self._load_page(page, task["url"])
                
                # 3. Locate element + smart wait
                div_locator = page.locator(task["div_selector"])
                await div_locator.wait_for(state="visible", timeout=20_000)  # Element wait timeout 20s
                div_box = await div_locator.bounding_box()
                if not div_box:
                    raise PlaywrightError(f"Element {task['div_selector']} has no valid size")
                
                # 4. Screenshot area optimization: adapt to A4 height
                clip_region = {
                    "x": div_box["x"],
                    "y": div_box["y"],
                    "width": div_box["width"],
                    "height": min(div_box["height"], div_box["width"] * 3 * 1.414)
                }
                await page.screenshot(path=task["save_path"], clip=clip_region, full_page=False)
                
                fut.set_result(task["save_path"])
                logger.debug(f"Screenshot success: {task['save_path']}")
        
        except Exception as e:
            fut.set_exception(e)
            logger.error(f"Task failed: {e}", exc_info=True)
        finally:
            if page:
                await page.close()
    
    async def _inject_cookies(self, page: Page, task: Dict):
        """Optimized cookie injection: execute only when needed"""
        request, access_token = task.get("request"), task.get("access_token")
        if not (request or access_token):
            return
        
        parsed_url = urlparse(task["url"])
        domain = parsed_url.netloc.split(":")[0]
        cookies = []
        
        if request and hasattr(request, "cookies"):
            cookies.extend([{
                "name": k, "value": v, "domain": domain, "path": "/"
            } for k, v in request.cookies.items()])
        
        if access_token:
            cookies.append({
                "name": "thumbnail_access_token",
                "value": access_token,
                "domain": domain,
                "path": "/"
            })
        
        if cookies:
            await page.context.add_cookies(cookies)
    
    async def _load_page(self, page: Page, url: str):
        """Optimized page loading: reduce unnecessary waiting"""
        page.on("console", lambda msg: logger.debug("Console [%s]: %s", msg.type, msg.text))
        page.on("request", lambda req: logger.debug("Request: %s %s", req.method, req.url))
        page.on("response", lambda res: logger.debug("Response: %d %s", res.status, res.url))
        
        
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)  # Navigation timeout 30s
        if response and response.status >= 400:
            raise PlaywrightError(f"URL failed: {url} (status: {response.status})")
        
        # Stop immediately after key resource loading, no wait for networkidle
        await page.wait_for_load_state("domcontentloaded")
        # Scroll to trigger lazy loading (necessary for document screenshot)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(500)  # Lazy loading content rendering wait
    
    async def _cleanup_all(self):
        """Cleanup all resources on stop"""
        if self._context_pool:
            while not self._context_pool.empty():
                try:
                    context = self._context_pool.get_nowait()
                    await context.close()
                except Exception:
                    pass
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()


# Global instance
_playwright_manager: Optional[PlaywrightManager] = None


def get_playwright_manager() -> PlaywrightManager:
    global _playwright_manager
    if not _playwright_manager:
        _playwright_manager = PlaywrightManager()
    return _playwright_manager
