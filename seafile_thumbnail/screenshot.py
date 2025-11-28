import jwt
import time
import logging
from seafile_thumbnail.settings import JWT_PRIVATE_KEY

import asyncio
import threading
import queue
from typing import Dict, Optional, Any, Tuple
from concurrent.futures import Future
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

def gen_thumbnail_access_token(file_uuid):
    access_token = jwt.encode({
        'file_uuid': file_uuid,
        'exp': int(time.time()) + 300,
    },
        JWT_PRIVATE_KEY,
        algorithm='HS256'
    )
    return access_token
    
class SimplifiedPlaywrightManager:
    """
    Runs the asyncio loop in a background thread
    and manages a single browser instance (sufficient for most use cases)
    
    Supports synchronous calls to the screenshot API with internal asynchronous processing
    Integrates requirements such as Cookie injection and selector cropping
    """
    def __init__(
        self,
        page_timeout: int = 60_000,
        browser_launch_kwargs: Optional[Dict[str, Any]] = None,
    ):
        self.page_timeout = page_timeout
        self.browser_launch_kwargs = browser_launch_kwargs or {
            "headless": True,
            "args": [
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--disable-background-networking",
            ]
        }

        # Thread and loop controle
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()

        
        self._task_queue: queue.Queue[Tuple[Dict, Future]] = queue.Queue()

        # Playwright
        self._playwright = None
        self._browser: Optional[Browser] = None

    def start(self):
        
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()
        self._ready_event.wait()

    def stop(self):
        """"""
        if not self._thread:
            return
        self._stop_event.set()
        #
        self._task_queue.put(({"__stop__": True}, Future()))
        self._thread.join(timeout=30)
        self._thread = None

    def screenshot_from_url(
        self,
        url: str,
        save_path: str,
        div_selector: str = "#sdoc-editor-print-wrapper",
        request=None,
        access_token: Optional[str] = None
    ) -> str:
        """sync call API"""
        if not self._thread or not self._thread.is_alive():
            raise RuntimeError("Manager not start, please call start() first")

        task = {
            "url": url,
            "save_path": save_path,
            "div_selector": div_selector,
            "request": request,
            "access_token": access_token
        }
        fut = Future()
        self._task_queue.put((task, fut))
        return fut.result()

    def _thread_main(self):
        try:
            asyncio.run(self._async_main())
        except Exception as e:
            raise e
        finally:
            self._ready_event.clear()

    async def _async_main(self):
        self._loop = asyncio.get_event_loop()
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(**self.browser_launch_kwargs)
        self._ready_event.set()

        while not self._stop_event.is_set():
            try:
                task, fut = await self._loop.run_in_executor(None, self._task_queue.get, True, 0.5)
            except queue.Empty:
                continue

            if task.get("__stop__"):
                fut.set_result(None)
                break

            # async handle screenshot
            asyncio.create_task(self._handle_screenshot_task(task, fut))

        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _handle_screenshot_task(self, task: Dict, fut: Future):
        
        url = task["url"]
        save_path = task["save_path"]
        div_selector = task["div_selector"]
        request = task["request"]
        access_token = task["access_token"]

        context: Optional[BrowserContext] = None
        page: Optional[Page] = None
        try:
            if not self._browser or not self._browser.is_connected():
                if self._browser:
                    try:
                        await self._browser.close()
                    except:
                        pass
                self._browser = await self._playwright.chromium.launch(**self.browser_launch_kwargs)
            
            
            context = await self._browser.new_context(
                viewport={
                    "width": 1920,
                    "height": 3000
                },
                device_scale_factor=1
            )
            page = await context.new_page()
            page.set_default_timeout(self.page_timeout)

            if request:
                parsed_url = urlparse(url)
                cookie_domain = parsed_url.netloc.split(":")[0]
                playwright_cookies = []
                for cookie_name, cookie_value in request.cookies.items():
                    playwright_cookies.append({
                        "name": cookie_name,
                        "value": cookie_value,
                        "domain": cookie_domain,
                        "path": "/",
                    })
                # 添加access_token Cookie
                if access_token:
                    playwright_cookies.append({
                        "name": "thumbnail_access_token",
                        "value": access_token,
                        "domain": cookie_domain,
                        "path": "/"
                    })
                if playwright_cookies:
                    await context.add_cookies(playwright_cookies)

            response = await page.goto(url, wait_until="domcontentloaded", timeout=self.page_timeout)
            if response and response.status > 400:
                raise Exception(f"URL request failed: {url} (status code: {response.status})")

            await page.wait_for_load_state("networkidle")

            div_locator = page.locator(div_selector)
            await div_locator.wait_for(state="visible", timeout=self.page_timeout)
            div_box = await div_locator.bounding_box()
            if not div_box:
                raise Exception(f"element {div_selector} size invalid")
            clip_region = {
                "x": div_box["x"],
                "y": div_box["y"],
                "width": div_box["width"],
                "height": min(div_box['height'], div_box["width"] * 1.414 * 3 )
            }

            await page.screenshot(path=save_path, clip=clip_region, full_page=False)
            fut.set_result(save_path)

        except Exception as e:
            fut.set_exception(e)
            logger.exception(f"handle_screenshot_task error: {e}")
        finally:
            if page:
                await page.close()
            if context:
                await context.close()


_playwright_manager: Optional[SimplifiedPlaywrightManager] = None


def get_playwright_manager():
    global _playwright_manager
    if not _playwright_manager:
        _playwright_manager = SimplifiedPlaywrightManager()
    return _playwright_manager
