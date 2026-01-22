import queue
import threading
import logging
import time
import uuid
import os
import hashlib

from seafile_thumbnail.settings import TASK_WORKERS

logger = logging.getLogger(__name__)

# Results older than this will be cleaned up (seconds)
RESULT_EXPIRE_TIME = 120

# Memory limit in MB, exit for restart if exceeded (default 4GB)
MEMORY_LIMIT_MB = int(os.environ.get('THUMBNAIL_MEMORY_LIMIT', 4096))
IMAGE_QUEUE_SIZE = TASK_WORKERS * 4
PDF_QUEUE_SIZE = TASK_WORKERS * 3
VIDEO_QUEUE_SIZE = TASK_WORKERS * 2
SEADOC_QUEUE_SIZE = TASK_WORKERS * 2

class ThumbnailManager(object):

    def __init__(self):
        self.tasks_map = {}
        # Store results with timestamp: {task_id: (result, timestamp)}
        self.task_results_map = {}


        self.seadoc_queue = queue.Queue(SEADOC_QUEUE_SIZE)
        self.image_queue = queue.Queue(IMAGE_QUEUE_SIZE)
        self.pdf_queue = queue.Queue(PDF_QUEUE_SIZE)  # Separate queue for slow tasks (PDF, PSD, XMIND)
        self.video_queue = queue.Queue(VIDEO_QUEUE_SIZE)

        self.current_task_info = {}
        self.threads = []
        self._results_lock = threading.Lock()

    def is_valid_task_id(self, task_id):
        return task_id in (self.tasks_map.keys() | self.task_results_map.keys())
    
    def threads_is_alive(self):
        info = {}
        for t in self.threads:
            info[t.name] = t.is_alive()
        return info

    def add_image_creat_task(self, func, repo_id, file_id, path, thumbnail_file, size):
        if self.image_queue.full():
            logger.warning('thumbnail server busy, queue size: %d, current tasks: %s, threads is_alive: %s'
                            % (self.image_queue.qsize(), self.current_task_info,
                            self.threads_is_alive()))
            return ('thumbnail server busy.', 503)
        task_id = hashlib.md5((repo_id + path).encode('utf-8')).hexdigest()
        if task_id in self.image_queue.queue:
            return (task_id, 200)
        task = (func, (repo_id, file_id, thumbnail_file, size))
        self.image_queue.put(task_id)
        self.tasks_map[task_id] = task
        return task_id, 200

    def add_svg_create_task(self, func, repo_id, file_id, path, size, thumbnail_file, file_size):
        # SVG conversion is fast, use image_queue
        if self.image_queue.full():
            logger.warning('thumbnail server busy, queue size: %d, current tasks: %s, threads is_alive: %s'
                            % (self.image_queue.qsize(), self.current_task_info,
                            self.threads_is_alive()))
            return ('thumbnail server busy.', 503)
        task_id = hashlib.md5((repo_id + path).encode('utf-8')).hexdigest()
        if task_id in self.image_queue.queue:
            return (task_id, 200)
        task = (func, (repo_id, file_id, path, size, thumbnail_file, file_size))
        self.image_queue.put(task_id)
        self.tasks_map[task_id] = task
        return task_id, 200

    def add_pdf_or_psd_create_task(self, func, repo_id, file_id, path, size, thumbnail_file, file_size):
        # Use pdf_queue for slow tasks (PDF, PSD) to avoid blocking image tasks
        if self.pdf_queue.full():
            logger.warning('pdf thumbnail server busy, queue size: %d, current tasks: %s, threads is_alive: %s'
                            % (self.pdf_queue.qsize(), self.current_task_info,
                            self.threads_is_alive()))
            return ('thumbnail server busy.', 503)
        task_id = hashlib.md5((repo_id + path).encode('utf-8')).hexdigest()
        if task_id in self.pdf_queue.queue:
            return (task_id, 200)
        task = (func, (repo_id, file_id, path, size, thumbnail_file, file_size))
        self.pdf_queue.put(task_id)
        self.tasks_map[task_id] = task
        return task_id, 200

    def add_xmind_create_task(self, func, repo_id, file_id, path, size, file_size=0):
        # XMIND just extracts embedded thumbnail from ZIP, very fast, use image_queue
        if self.image_queue.full():
            logger.warning('thumbnail server busy, queue size: %d, current tasks: %s, threads is_alive: %s'
                            % (self.image_queue.qsize(), self.current_task_info,
                            self.threads_is_alive()))
            return ('thumbnail server busy.', 503)
        task_id = hashlib.md5((repo_id + path).encode('utf-8')).hexdigest()
        if task_id in self.image_queue.queue:
            return (task_id, 200)
        task = (func, (repo_id, file_id, size, file_size))
        self.image_queue.put(task_id)
        self.tasks_map[task_id] = task
        return task_id, 200
    
    def add_seadoc_create_task(self, func, request, repo_id, file_id, path, size, thumbnail_file, file_size):
        if self.seadoc_queue.full():
            logger.warning('thumbnail server busy, queue size: %d, current tasks: %s, threads is_alive: %s'
                            % (self.seadoc_queue.qsize(), self.current_task_info,
                            self.threads_is_alive()))
            return ('thumbnail server busy.', 503)
        task_id = str(uuid.uuid4())
        task = (func, (request, repo_id, file_id, path, size, thumbnail_file, file_size))
        self.seadoc_queue.put(task_id)
        self.tasks_map[task_id] = task
        return task_id, 200

    def add_video_task(self, func, repo_id, file_id, path, size, thumbnail_file, file_size=0):
        if self.video_queue.full():
            logger.warning('thumbnail server busy, queue size: %d, current tasks: %s, threads is_alive: %s'
                            % (self.video_queue.qsize(), self.current_task_info,
                            self.threads_is_alive()))
            return ('thumbnail server busy.', 503)
        task_id = hashlib.md5((repo_id + path).encode('utf-8')).hexdigest()
        if task_id in self.video_queue.queue:
            return (task_id, 200)
        task = (func, (repo_id, file_id, size, thumbnail_file, file_size))
        self.video_queue.put(task_id)
        self.tasks_map[task_id] = task
        return task_id, 200

    def _set_result(self, task_id, result):
        """Store result with timestamp"""
        with self._results_lock:
            self.task_results_map[task_id] = (result, time.time())

    def _get_and_remove_result(self, task_id):
        """Get and remove result, returns None if not found"""
        with self._results_lock:
            item = self.task_results_map.pop(task_id, None)
            if item:
                return item[0]  # Return only the result, not timestamp
            return None

    def _cleanup_expired_results(self):
        """Remove results older than RESULT_EXPIRE_TIME"""
        now = time.time()
        expired_keys = []
        with self._results_lock:
            for task_id, (result, timestamp) in self.task_results_map.items():
                if now - timestamp > RESULT_EXPIRE_TIME:
                    expired_keys.append(task_id)
            for key in expired_keys:
                del self.task_results_map[key]
        if expired_keys:
            logger.info(f'Cleaned up {len(expired_keys)} expired task results')

    def _check_memory_and_exit(self):
        """Check memory usage, exit for restart if exceeded limit"""
        try:
            with open('/proc/self/statm', 'r') as f:
                # statm: size resident shared text lib data dt (in pages)
                # resident (RSS) is the second field
                rss_pages = int(f.read().split()[1])
                rss_mb = rss_pages * 4096 / 1024 / 1024
                if rss_mb > MEMORY_LIMIT_MB:
                    logger.warning(f'Memory usage {rss_mb:.0f}MB exceeds limit {MEMORY_LIMIT_MB}MB, exiting for restart')
                    os._exit(1)
        except Exception as e:
            logger.error(f'Failed to check memory: {e}')

    def query_status(self, task_id):
        if not self.is_valid_task_id(task_id):
            error = 'task id: %s invalid'% task_id
            logger.warning(error)
            return True, error
        task_result = self._get_and_remove_result(task_id)
        if task_result == 'success':
            return True, None
        if isinstance(task_result, str) and task_result.startswith('error_'):
            return True, task_result[6:]
        return False, None
    

    def check_and_restart_threads(self):
        """monitor the thread status and restart the dead threads"""
        logger.info("thread monitor started")
        while True:
            try:
                # Cleanup expired task results to prevent memory leak
                self._cleanup_expired_results()
                
                # Check memory usage and exit if exceeded limit
                self._check_memory_and_exit()
                
                # check the thread status
                dead_threads = []
                for i, thread in enumerate(self.threads):
                    if not thread.is_alive():
                        logger.warning(f"detected thread {thread.name} is dead, preparing to restart")
                        dead_threads.append((i, thread))
                
                # restart the dead threads
                for i, thread in dead_threads:
                    if thread.name.startswith('ImageManager'):
                        new_thread = threading.Thread(
                            target=self.handle_image_task, 
                            name=thread.name
                        )
                    elif thread.name.startswith('PdfManager'):
                        new_thread = threading.Thread(
                            target=self.handle_pdf_task,
                            name=thread.name
                        )
                    elif thread.name.startswith('SeaDocManager'):
                        new_thread = threading.Thread(
                            target=self.handle_seadoc_task,
                            name=thread.name
                        )
                    else:  # VideoManager
                        new_thread = threading.Thread(
                            target=self.handle_video_task, 
                            name=thread.name
                        )
                    
                    new_thread.setDaemon(True)
                    new_thread.start()
                    
                    self.threads[i] = new_thread
                    
                    logger.info(f"thread {thread.name} restarted")
                    
            except Exception as e:
                logger.error(f"thread monitor error: {str(e)}")
            
            time.sleep(60)


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
                logging.debug('Thread name: %s, threads is_alive: %s image_queue: %s image_queue size: %d, tasks_map: %s, task_results_map: %s'
                            % (threading.current_thread().name, self.threads_is_alive(), self.image_queue.queue, self.image_queue.qsize(),
                            self.tasks_map, self.task_results_map))
                start_time = time.time()
                # run
                task[0](*task[1])
                self._set_result(image_id, 'success')

                finish_time = time.time()
                logging.info('Run task success: %s cost %ds \n' % (task_info, int(finish_time - start_time)))
                self.current_task_info.pop(image_id, None)
            except Exception as e:
                # Some errors in seabobj are not properly thrown, resulting in index exceeding errors here
                if len(e.args) > 0:
                    self._set_result(image_id, 'error_' + str(e.args[0]))
                else:
                    self._set_result(image_id, 'error_' + str(e))
                logger.exception('Failed to handle task %s, error: %s \n' % (task_info, e))
                
                self.current_task_info.pop(image_id, None)
            finally:
                self.tasks_map.pop(image_id, None)

    def handle_pdf_task(self):
        """Handle slow tasks: PDF, PSD, XMIND"""
        while True:
            try:
                pdf_id = self.pdf_queue.get(timeout=2)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(e)
                continue
            task = self.tasks_map.get(pdf_id)
            if type(task) != tuple or len(task) < 1:
                continue
            task_info = pdf_id + ' ' + str(task[0])
            try:
                self.current_task_info[pdf_id] = task_info
                logging.info('Run task: %s' % task_info)
                logging.debug('Thread name: %s, threads is_alive: %s pdf_queue: %s pdf_queue size: %d'
                            % (threading.current_thread().name, self.threads_is_alive(), self.pdf_queue.queue, self.pdf_queue.qsize()))
                start_time = time.time()
                # run
                task[0](*task[1])
                self._set_result(pdf_id, 'success')
                finish_time = time.time()
                logging.info('Run task success: %s cost %ds \n' % (task_info, int(finish_time - start_time)))
                self.current_task_info.pop(pdf_id, None)
            except Exception as e:
                if len(e.args) > 0:
                    self._set_result(pdf_id, 'error_' + str(e.args[0]))
                else:
                    self._set_result(pdf_id, 'error_' + str(e))
                logger.exception('Failed to handle task %s, error: %s \n' % (task_info, e))
                self.current_task_info.pop(pdf_id, None)
            finally:
                self.tasks_map.pop(pdf_id, None)

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
                logging.debug('Thread name: %s, threads is_alive: %s video_queue: %s video_queue size: %d'
                            % (threading.current_thread().name, self.threads_is_alive(), self.video_queue.queue, self.video_queue.qsize()))
                start_time = time.time()
                # run
                task[0](*task[1])
                self._set_result(video_id, 'success')
                finish_time = time.time()
                logging.info('Run task success: %s cost %ds \n' % (task_info, int(finish_time - start_time)))
                self.current_task_info.pop(video_id, None)
            except Exception as e:
                # Some errors in seabobj are not properly thrown, resulting in index exceeding errors here
                if len(e.args) > 0:
                    self._set_result(video_id, 'error_' + str(e.args[0]))
                else:
                    self._set_result(video_id, 'error_' + str(e))
                logger.error('Failed to handle task %s, error: %s \n' % (task_info, e))
                self.current_task_info.pop(video_id, None)
            finally:
                self.tasks_map.pop(video_id, None)
                
    def handle_seadoc_task(self):
        while True:
            try:
                seadoc_id = self.seadoc_queue.get(timeout=2)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(e)
                continue
            task = self.tasks_map.get(seadoc_id)
            if type(task) != tuple or len(task) < 1:
                continue
            task_info = seadoc_id + ' ' + str(task[0])
            try:
                self.current_task_info[seadoc_id] = task_info
                logging.info('Run task: %s' % task_info)
                logging.debug('Thread name: %s, threads is_alive: %s seadoc_queue: %s seadoc_queue size: %d'
                            % (threading.current_thread().name, self.threads_is_alive(), self.seadoc_queue.queue, self.seadoc_queue.qsize()))
                start_time = time.time()
                # run
                task[0](*task[1])
                self._set_result(seadoc_id, 'success')
                finish_time = time.time()
                logging.info('Run task success: %s cost %ds \n' % (task_info, int(finish_time - start_time)))
                self.current_task_info.pop(seadoc_id, None)
            except Exception as e:
                # Some errors in seabobj are not properly thrown, resulting in index exceeding errors here
                if len(e.args) > 0:
                    self._set_result(seadoc_id, 'error_' + str(e.args[0]))
                else:
                    self._set_result(seadoc_id, 'error_' + str(e))
                logger.error('Failed to handle task %s, error: %s \n' % (task_info, e))
                self.current_task_info.pop(seadoc_id, None)
            finally:
                self.tasks_map.pop(seadoc_id, None)

    def run(self, task_workers=3):
        image_name = 'ImageManager Thread-'
        pdf_name = 'PdfManager Thread-'
        video_name = 'VideoManager Thread-'
        seadoc_name = 'SeadocManager Thread-'
        for thread_num in range(task_workers):
            image_t = threading.Thread(target=self.handle_image_task, name=image_name+str(thread_num))
            pdf_t = threading.Thread(target=self.handle_pdf_task, name=pdf_name+str(thread_num))
            video_t = threading.Thread(target=self.handle_video_task, name=video_name+str(thread_num))
            seadoc_t = threading.Thread(target=self.handle_seadoc_task, name=seadoc_name+str(thread_num))
            image_t.setDaemon(True)
            pdf_t.setDaemon(True)
            video_t.setDaemon(True)
            seadoc_t.setDaemon(True)
            image_t.start()
            pdf_t.start()
            video_t.start()
            seadoc_t.start()
            self.threads.append(image_t)
            self.threads.append(pdf_t)
            self.threads.append(video_t)
            self.threads.append(seadoc_t)

        # start the thread monitor
        monitor = threading.Thread(target=self.check_and_restart_threads, name="ThreadMonitor")
        monitor.setDaemon(True)
        monitor.start()

thumbnail_task_manager = ThumbnailManager()
