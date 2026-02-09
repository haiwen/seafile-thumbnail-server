import sys
import uvicorn
import logging
import logging.handlers
import os
import argparse
from app import app
from seafile_thumbnail.thumbnail_task_manager import thumbnail_task_manager
from threading import Thread
from seafile_thumbnail.settings import LOG_DIR, TASK_WORKERS

# Custom uvicorn log config with timestamps
UVICORN_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "[%(asctime)s] %(levelprefix)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "use_colors": False,
        },
        "access": {
            "()": "uvicorn.logging.AccessFormatter",
            "fmt": "[%(asctime)s] %(levelprefix)s %(client_addr)s - \"%(request_line)s\" %(status_code)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "use_colors": False,
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.error": {"level": "INFO"},
        "uvicorn.access": {
            "handlers": ["access"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

class ThumbnailServer(Thread):

    def __init__(self, task_workers):
        Thread.__init__(self)
        thumbnail_task_manager.run(task_workers)

        config = uvicorn.Config(app, port=8088, log_config=UVICORN_LOG_CONFIG)
        self._server = uvicorn.Server(config)

    def run(self):
        logging.info('Starting seafile thumbnail server...')
        self._server.run()


def run_server(loglevel='info'):
    level = logging.INFO
    if loglevel == 'debug':
        level = logging.DEBUG

    seafile_log_to_stdout = os.getenv('SEAFILE_LOG_TO_STDOUT', 'false') == 'true'
    formatter = '[%(asctime)s] [%(levelname)s] %(name)s:%(lineno)s %(message)s'
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
    thumbnail_server.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Seafile Thumbnail Server')
    parser.add_argument('--loglevel', type=str, default='info', help='log level')
    args = parser.parse_args()
    run_server(args.loglevel)
