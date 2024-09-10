# import queue
# import threading
# import logging
# import time
# import uuid
# from seafevents.seafevent_server.utils import export_event_log_to_excel, export_org_event_log_to_excel
#
# logger = logging.getLogger(__name__)
#
#
# class ThumbnailManager(object):
#
#     def __init__(self):
#         self.app = None
#         self.tasks_map = {}
#         self.task_results_map = {}
#         self.image_queue = queue.Queue(10)
#         self.video_queue = queue.Queue(10)
#         self.current_task_info = {}
#         self.threads = []
#         self.conf = {
#             'workers': 3,
#             'expire_time': 30 * 60
#         }
#
#     def init(self, app, workers, task_expire_time, config):
#         self.app = app
#         self.conf['expire_time'] = task_expire_time
#         self.conf['workers'] = workers
#
#     def is_valid_task_id(self, task_id):
#         return task_id in (self.tasks_map.keys() | self.task_results_map.keys())
#
#     def add_image_creat_task(self, start_time, end_time, log_type):
#         task_id = str(uuid.uuid4())
#         task = (export_event_log_to_excel, (start_time, end_time, log_type, task_id))
#
#         self.tasks_queue.put(task_id)
#         self.tasks_map[task_id] = task
#         return task_id
#
#     def add_video_task(self, start_time, end_time, log_type, org_id):
#         task_id = str(uuid.uuid4())
#         task = (export_org_event_log_to_excel, (start_time, end_time, log_type, task_id, org_id))
#
#         self.tasks_queue.put(task_id)
#         self.tasks_map[task_id] = task
#         return task_id
#
#     def query_status(self, task_id):
#         task_result = self.task_results_map.pop(task_id, None)
#         if task_result == 'success':
#             return True, None
#         if isinstance(task_result, str) and task_result.startswith('error_'):
#             return True, task_result[6:]
#         return False, None
#
#     def threads_is_alive(self):
#         info = {}
#         for t in self.threads:
#             info[t.name] = t.is_alive()
#         return info
#
#     def handle_task(self):
#         while True:
#             try:
#                 image_id = self.image_queue.get(timeout=2)
#                 # video_id = self.video_queue.get(timeout=2)
#             except queue.Empty:
#                 continue
#             except Exception as e:
#                 logger.error(e)
#                 continue
#             task = self.tasks_map.get(image_id)
#             if type(task) != tuple or len(task) < 1:
#                 continue
#             if type(task[0]).__name__ != 'function':
#                 continue
#             task_info = image_id + ' ' + str(task[0])
#             try:
#                 self.current_task_info[image_id] = task_info
#                 logging.info('Run task: %s' % task_info)
#                 start_time = time.time()
#
#                 # run
#                 task[0](*task[1])
#                 self.task_results_map[image_id] = 'success'
#
#                 finish_time = time.time()
#                 logging.info('Run task success: %s cost %ds \n' % (task_info, int(finish_time - start_time)))
#                 self.current_task_info.pop(image_id, None)
#             except Exception as e:
#                 self.task_results_map[image_id] = 'error_' + str(e.args[0])
#                 logger.exception(e)
#                 logger.error('Failed to handle task %s, error: %s \n' % (task_info, e))
#                 self.current_task_info.pop(image_id, None)
#             finally:
#                 self.tasks_map.pop(image_id, None)
#
#     def run(self):
#         thread_num = self.conf['workers']
#         for i in range(thread_num):
#             t_name = 'TaskManager Thread-' + str(i)
#             t = threading.Thread(target=self.handle_task, name=t_name)
#             self.threads.append(t)
#             t.setDaemon(True)
#             t.start()
#
#
# thumbnail_task_manager = ThumbnailManager()
