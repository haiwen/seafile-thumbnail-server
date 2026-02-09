import sys
import uvicorn
import logging
import logging.handlers
import os
import argparse
from app import app
from seafile_thumbnail.screenshot import get_playwright_manager
from seafile_thumbnail.thumbnail_task_manager import thumbnail_task_manager
from seafile_thumbnail.repo_storage_task import RepoStorageTask
from threading import Thread
from seafile_thumbnail.settings import ENABLE_MULTI_STORAGE, LOG_DIR, TASK_WORKERS


class ThumbnailServer:

    def __init__(self, task_workers):
        self.task_workers = task_workers

        
        config = uvicorn.Config(app, port=8088)
        self._uvicorn_server = uvicorn.Server(config)
        self._server_thread = None
        if ENABLE_MULTI_STORAGE:
            self.repo_storage_task_event = RepoStorageTask()
        

    def _server_runner(self):
        """Run uvicorn server"""
        logging.info('Starting seafile thumbnail server...')
        self._uvicorn_server.run()
    def start(self):
        logging.info('Initializing seafile thumbnail components')
        # start thumbnail task workers (non-blocking)
        thumbnail_task_manager.run(self.task_workers)
        # start Playwright manager
        get_playwright_manager().start()
        # start repo storage task thread
        if ENABLE_MULTI_STORAGE:
            self.repo_storage_task_event.start()

        # run uvicorn server in a dedicated thread so we can manage other threads
        self._server_thread = Thread(target=self._server_runner, name='uvicorn-server')
        self._server_thread.daemon = True
        self._server_thread.start()
    def wait(self):
        if self._server_thread is not None:
            try:
                self._server_thread.join()
            except KeyboardInterrupt:
                pass

def run_server(loglevel='info'):
    level = logging.INFO
    if loglevel == 'debug':
        level = logging.DEBUG

    seafile_log_to_stdout = os.getenv('SEAFILE_LOG_TO_STDOUT', 'false') == 'true'
    if seafile_log_to_stdout:
        formatter = '[thumbnail-server] [%(asctime)s] [%(levelname)s] %(name)s:%(lineno)s %(message)s'
        log_kw = {
            'format': formatter,
            'datefmt': '%Y-%m-%d %H:%M:%S',
            'level': level,
            'stream': sys.stdout
        }
        logging.basicConfig(**log_kw)
        
    else:
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR, exist_ok=True)
        handler = logging.handlers.TimedRotatingFileHandler(f'{LOG_DIR}/thumbnail.log', when='W0', interval=1)
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(name)s:%(lineno)s %(message)s',
                                      datefmt='%Y-%m-%d %H:%M:%S')
        handler.setLevel(level)
        handler.setFormatter(formatter)
        logging.root.setLevel(level)
        logging.root.addHandler(handler)

        thumbnail_server = ThumbnailServer(TASK_WORKERS)
        thumbnail_server.start()
        thumbnail_server.wait()
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Seafile Thumbnail Server')
    parser.add_argument('--loglevel', type=str, default='info', help='log level')
    args = parser.parse_args()
    run_server(args.loglevel)
