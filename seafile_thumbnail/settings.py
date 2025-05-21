import os
import sys

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), os.pardir)

# environment
# os.environ['CCNET_CONF_DIR'] = '/data/conf'
# os.environ['SEAFILE_CONF_DIR'] = '/opt/seafile-data'
# os.environ['SEAFILE_CENTRAL_CONF_DIR'] = '/data/conf'


# url
URL_PREFIX = '/'
SEAFILE_SERVER_URL = 'http://127.0.0.1:8000'

# dir
CONF_DIR = '/data/conf/'
LOG_DIR = '.'
# LOG_DIR = os.path.join(os.path.dirname(PROJECT_ROOT), 'logs') # abs path

# VIDEO thumbnail
ENABLE_VIDEO_THUMBNAIL = True
THUMBNAIL_VIDEO_FRAME_TIME = 5  # use the frame at 5 second as thumbnail
SAFETY_MARGIN = 0.1
# xmind thumbnail
ENABLE_XMIND_THUMBNAIL = True
# pdf thumbnails
ENABLE_PDF_THUMBNAIL = True

# size(MB) limit for generate thumbnail
THUMBNAIL_IMAGE_SIZE_LIMIT = 30
THUMBNAIL_IMAGE_ORIGINAL_SIZE_LIMIT = 256

# for thumbnail: height(px) and width(px)
THUMBNAIL_DEFAULT_SIZE = 256
THUMBNAIL_SIZE_FOR_GRID = 512
THUMBNAIL_SIZE_FOR_ORIGINAL = 1024

# Absolute filesystem path to the directory that will hold thumbnail files.
SEAHUB_DATA_ROOT = os.path.join(PROJECT_ROOT, '../../seahub-data')
if os.path.exists(SEAHUB_DATA_ROOT):
    THUMBNAIL_ROOT = os.path.join(SEAHUB_DATA_ROOT, 'thumbnail')
else:
    THUMBNAIL_ROOT = os.path.join(PROJECT_ROOT, 'seahub/thumbnail/thumb')

THUMBNAIL_EXTENSION = 'jpeg'


# session key
SESSION_KEY = 'sessionid'

JWT_PRIVATE_KEY = ""
# thread count
TASK_WORKERS = 3


# ======================== local settings ======================== #
try:
    from local_settings import *
except ImportError as e:
    pass

try:
    if os.path.exists(CONF_DIR):
        sys.path.insert(0, CONF_DIR)
    from seafile_thumbnail_settings import *
except ImportError as e:
    pass

SEAFILE_SERVER_URL = os.getenv('SEAFILE_SERVER_URL') or SEAFILE_SERVER_URL
JWT_PRIVATE_KEY = os.getenv('JWT_PRIVATE_KEY') or JWT_PRIVATE_KEY
