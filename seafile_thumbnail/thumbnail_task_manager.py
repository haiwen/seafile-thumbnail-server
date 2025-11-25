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
        self.image_queue = queue.Queue(32)
        self.video_queue = queue.Queue(32)

        self.seadoc_queue = queue.Queue(32)
        self.current_task_info = {}
        self.threads = []

    def is_valid_task_id(self, task_id):
        return task_id in (self.tasks_map.keys() | self.task_results_map.keys())
    
    def threads_is_alive(self):
        info = {}
        for t in self.threads:
            info[t.name] = t.is_alive()
        return info

    def add_image_creat_task(self, func, repo, file_id, thumbnail_file, size):
        if self.image_queue.full():
            logger.warning('thumbnail server busy, queue size: %d, current tasks: %s, threads is_alive: %s'
                            % (self.image_queue.qsize(), self.current_task_info,
                            self.threads_is_alive()))
            return ('thumbnail server busy.', 503)
        task_id = str(uuid.uuid4())
        task = (func, (repo, file_id, thumbnail_file, size))
        self.image_queue.put(task_id)
        self.tasks_map[task_id] = task
        return task_id, 200

    def add_pdf_or_psd_create_task(self, func, repo_id, file_id, path, size, thumbnail_file, file_size):
        if self.image_queue.full():
            logger.warning('thumbnail server busy, queue size: %d, current tasks: %s, threads is_alive: %s'
                            % (self.image_queue.qsize(), self.current_task_info,
                            self.threads_is_alive()))
            return ('thumbnail server busy.', 503)
        task_id = str(uuid.uuid4())
        task = (func, (repo_id, file_id, path, size, thumbnail_file, file_size))
        self.image_queue.put(task_id)
        self.tasks_map[task_id] = task
        return task_id, 200

    def add_xmind_create_task(self, func, repo_id, file_id, size):
        if self.image_queue.full():
            logger.warning('thumbnail server busy, queue size: %d, current tasks: %s, threads is_alive: %s'
                            % (self.image_queue.qsize(), self.current_task_info,
                            self.threads_is_alive()))
            return ('thumbnail server busy.', 503)
        task_id = str(uuid.uuid4())
        task = (func, (repo_id, file_id, size))
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

    def add_video_task(self, func, repo, file_id, size, thumbnail_file):
        if self.video_queue.full():
            logger.warning('thumbnail server busy, queue size: %d, current tasks: %s, threads is_alive: %s'
                            % (self.video_queue.qsize(), self.current_task_info,
                            self.threads_is_alive()))
            return ('thumbnail server busy.', 503)
        task_id = str(uuid.uuid4())
        task = (func, (repo, file_id, size, thumbnail_file))
        self.video_queue.put(task_id)
        self.tasks_map[task_id] = task
        return task_id, 200

    def query_status(self, task_id):
        if not self.is_valid_task_id(task_id):
            error = 'task id: %s invalid'% task_id
            logger.warning(error)
            return True, error
        task_result = self.task_results_map.pop(task_id, None)
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
                    elif thread.name.startswith('SeadocManager'):
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
                self.task_results_map[image_id] = 'success'

                finish_time = time.time()
                logging.info('Run task success: %s cost %ds \n' % (task_info, int(finish_time - start_time)))
                self.current_task_info.pop(image_id, None)
            except Exception as e:
                # Some errors in seabobj are not properly thrown, resulting in index exceeding errors here
                if len(e.args) > 0:
                    self.task_results_map[image_id] = 'error_' + str(e.args[0])
                else:
                    self.task_results_map[image_id] = 'error_' + str(e)
                logger.exception('Failed to handle task %s, error: %s \n' % (task_info, e))
                
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
                logging.debug('Thread name: %s, threads is_alive: %s video_queue: %s video_queue size: %d'
                            % (threading.current_thread().name, self.threads_is_alive(), self.video_queue.queue, self.video_queue.qsize()))
                start_time = time.time()
                # run
                task[0](*task[1])
                self.task_results_map[video_id] = 'success'
                finish_time = time.time()
                logging.info('Run task success: %s cost %ds \n' % (task_info, int(finish_time - start_time)))
                self.current_task_info.pop(video_id, None)
            except Exception as e:
                # Some errors in seabobj are not properly thrown, resulting in index exceeding errors here
                if len(e.args) > 0:
                    self.task_results_map[video_id] = 'error_' + str(e.args[0])
                else:
                    self.task_results_map[video_id] = 'error_' + str(e)
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
                self.task_results_map[seadoc_id] = 'success'
                finish_time = time.time()
                logging.info('Run task success: %s cost %ds \n' % (task_info, int(finish_time - start_time)))
                self.current_task_info.pop(seadoc_id, None)
            except Exception as e:
                # Some errors in seabobj are not properly thrown, resulting in index exceeding errors here
                if len(e.args) > 0:
                    self.task_results_map[seadoc_id] = 'error_' + str(e.args[0])
                else:
                    self.task_results_map[seadoc_id] = 'error_' + str(e)
                logger.error('Failed to handle task %s, error: %s \n' % (task_info, e))
                self.current_task_info.pop(seadoc_id, None)
            finally:
                self.tasks_map.pop(seadoc_id, None)

    def run(self, task_workers=3):
        image_name = 'ImageManager Thread-'
        video_name = 'VideoManager Thread-'
        seadoc_name = 'SeadocManager Thread-'
        for thread_num in range(task_workers):
            image_t = threading.Thread(target=self.handle_image_task, name=image_name+str(thread_num))
            video_t = threading.Thread(target=self.handle_video_task, name=video_name+str(thread_num))
            seadoc_t = threading.Thread(target=self.handle_seadoc_task, name=seadoc_name+str(thread_num))
            image_t.setDaemon(True)
            video_t.setDaemon(True)
            seadoc_t.setDaemon(True)
            image_t.start()
            video_t.start()
            seadoc_t.start()
            self.threads.append(image_t)
            self.threads.append(video_t)
            self.threads.append(seadoc_t)

        # start the thread monitor
        monitor = threading.Thread(target=self.check_and_restart_threads, name="ThreadMonitor")
        monitor.setDaemon(True)
        monitor.start()

thumbnail_task_manager = ThumbnailManager()
