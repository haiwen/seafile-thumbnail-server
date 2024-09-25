import uvicorn
import logging
import sys
import os
from app import app
from seafile_thumbnail.task_queue import thumbnail_task_manager
from threading import Thread
from seafile_thumbnail.settings import LOG_DIR



class ThumbnailServer(Thread):

    def __init__(self):
        Thread.__init__(self)
        thumbnail_task_manager.run()

        config = uvicorn.Config(app, port=8001)
        self._server = uvicorn.Server(config)

    def run(self):
        self._server.run()


def run_server():
    log_kw = {
        'format': '[%(asctime)s] [%(levelname)s] %(message)s',
        'datefmt': '%m/%d/%Y %H:%M:%S',
        'level': logging.INFO,
        'filename': f'{LOG_DIR}/thumbnail.log'
    }
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(**log_kw)
    thumbnail_server = ThumbnailServer()
    thumbnail_server.run()


if __name__ == '__main__':
    run_server()
