import queue
import threading
import logging
import time
import uuid

logger = logging.getLogger(__name__)


class ThumbnailManager(object):

    def __init__(self):
        self.tasks_map = {}
        self.task_results_map = {}
        self.image_queue = queue.Queue()
        self.video_queue = queue.Queue()
        self.current_task_info = {}
        self.threads = []

    def is_valid_task_id(self, task_id):
        return task_id in (self.tasks_map.keys() | self.task_results_map.keys())

    def add_image_creat_task(self, func, repo, file_id, path, size, thumbnail_file):
        task_id = str(uuid.uuid4())
        task = (func, (repo, file_id, path, size, thumbnail_file))
        self.image_queue.put(task_id)
        self.tasks_map[task_id] = task
        return task_id

    def add_pdf_or_psd_create_task(self, func, repo_id, file_id, path, size, thumbnail_file, file_size):
        task_id = str(uuid.uuid4())
        task = (func, (repo_id, file_id, path, size, thumbnail_file, file_size))
        self.image_queue.put(task_id)
        self.tasks_map[task_id] = task
        return task_id

    def add_xmind_create_task(self, func, repo_id, path, size):
        task_id = str(uuid.uuid4())
        task = (func, (repo_id, path, size))
        self.image_queue.put(task_id)
        self.tasks_map[task_id] = task
        return task_id

    def add_video_task(self, func, repo, file_id, path, size, thumbnail_file):
        task_id = str(uuid.uuid4())
        task = (func, (repo, file_id, path, size, thumbnail_file))
        self.video_queue.put(task_id)
        self.tasks_map[task_id] = task
        return task_id

    def query_status(self, task_id):
        task_result = self.task_results_map.pop(task_id, None)
        if task_result == 'success':
            return True, None
        if isinstance(task_result, str) and task_result.startswith('error_'):
            return True, task_result[6:]
        return False, None

    def handle_image_task(self):
        while True:
            try:
                image_id = self.image_queue.get(timeout=2)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(e)
                continue
            task = self.tasks_map.get(image_id)
            if type(task) != tuple or len(task) < 1:
                continue
            task_info = image_id + ' ' + str(task[0])
            try:
                self.current_task_info[image_id] = task_info
                logging.info('Run task: %s' % task_info)
                start_time = time.time()
                # run
                task[0](*task[1])
                self.task_results_map[image_id] = 'success'

                finish_time = time.time()
                logging.info('Run task success: %s cost %ds \n' % (task_info, int(finish_time - start_time)))
                self.current_task_info.pop(image_id, None)
            except Exception as e:
                self.task_results_map[image_id] = 'error_' + str(e.args[0])
                logger.exception(e)
                logger.error('Failed to handle task %s, error: %s \n' % (task_info, e))
                self.current_task_info.pop(image_id, None)
            finally:
                self.tasks_map.pop(image_id, None)

    def handle_video_task(self):
        while True:
            try:
                video_id = self.video_queue.get(timeout=2)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(e)
                continue
            task = self.tasks_map.get(video_id)
            if type(task) != tuple or len(task) < 1:
                continue
            task_info = video_id + ' ' + str(task[0])
            try:
                self.current_task_info[video_id] = task_info
                logging.info('Run task: %s' % task_info)
                start_time = time.time()
                # run
                task[0](*task[1])
                self.task_results_map[video_id] = 'success'

                finish_time = time.time()
                logging.info('Run task success: %s cost %ds \n' % (task_info, int(finish_time - start_time)))
                self.current_task_info.pop(video_id, None)
            except Exception as e:
                self.task_results_map[video_id] = 'error_' + str(e.args[0])
                logger.exception(e)
                logger.error('Failed to handle task %s, error: %s \n' % (task_info, e))
                self.current_task_info.pop(video_id, None)
            finally:
                self.tasks_map.pop(video_id, None)

    def run(self):
        image_name = 'ImageManager Thread-' + str(1)
        video_name = 'VideoManager Thread-' + str(2)

        image_t = threading.Thread(target=self.handle_image_task, name=image_name)
        video_t = threading.Thread(target=self.handle_video_task, name=video_name)
        self.threads.append(image_t)
        self.threads.append(video_t)
        image_t.setDaemon(True)
        video_t.setDaemon(True)
        image_t.start()
        video_t.start()


thumbnail_task_manager = ThumbnailManager()
