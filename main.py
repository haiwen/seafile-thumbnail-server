import uvicorn

from app import app
from seafile_thumbnail.task_queue import thumbnail_task_manager
from threading import Thread

class ThumbnaiServer(Thread):
    
    def __init__(self):
        Thread.__init__(self)
        thumbnail_task_manager.run()
        
        config = uvicorn.Config(app, port=8001)
        self._server = uvicorn.Server(config)
        
    def run(self):
        self._server.run()
        
        




def run_server():
    thumbnail_server = ThumbnaiServer()
    thumbnail_server.run()
    

if __name__ == '__main__':
    run_server()