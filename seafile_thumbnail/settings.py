import os
import sys

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), os.pardir)

# environment
# os.environ['CCNET_CONF_DIR'] = '/data/conf'
# os.environ['SEAFILE_CONF_DIR'] = '/opt/seafile-data'
# os.environ['SEAFILE_CENTRAL_CONF_DIR'] = '/data/conf'


# url
URL_PREFIX = '/'
INNER_FILE_SERVER_ROOT = 'http://127.0.0.1:8082'
SEAHUB_SERVICE_URL = 'http://127.0.0.1:8000'

# dir
CONF_DIR = '/data/conf/'
THUMBNAIL_DIR = '/data/seahub-data/thumbnail'
LOG_DIR = '/data/seahub-data/logs'

# VIDEO thumbnail
ENABLE_VIDEO_THUMBNAIL = True
THUMBNAIL_VIDEO_FRAME_TIME = 5  # use the frame at 5 second as thumbnail
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


# ======================== local settings ======================== #
try:
    from local_settings import *
except ImportError as e:
    pass

try:
    if os.path.exists(CONF_DIR):
        sys.path.insert(0, CONF_DIR)
    from seatable_thumbnail_settings import *
except ImportError as e:
    pass


