try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass
import logging
import os
import tempfile
import timeit
import zipfile
import urllib.request, urllib.error, urllib.parse
from io import BytesIO
from fitz import open as fitz_open
from PIL import Image


from seafile_thumbnail import settings
from seafile_thumbnail.utils import get_inner_path
from seafile_thumbnail.constants import VIDEO, PDF, XMIND
from seafile_thumbnail.settings import ENABLE_VIDEO_THUMBNAIL, THUMBNAIL_IMAGE_SIZE_LIMIT, THUMBNAIL_ROOT, \
    THUMBNAIL_IMAGE_ORIGINAL_SIZE_LIMIT, THUMBNAIL_EXTENSION
from seafile_thumbnail.task_queue import thumbnail_task_manager

from seaserv import get_repo, get_file_size, seafile_api

try:  # Py2 and Py3 compatibility
    from urllib.request import urlretrieve
except:
    from urllib.request import urlretrieve

logger = logging.getLogger(__name__)

XMIND_IMAGE_SIZE = 1024


def get_rotated_image(image):
    # get image's exif info
    try:
        exif = image._getexif() if image._getexif() else {}
    except Exception:
        return image

    orientation = exif.get(0x0112) if isinstance(exif, dict) else 1
    # rotate image according to Orientation info

    # im.transpose(method)
    # Returns a flipped or rotated copy of an image.
    # Method can be one of the following: FLIP_LEFT_RIGHT, FLIP_TOP_BOTTOM, ROTATE_90, ROTATE_180, or ROTATE_270.

    # expand: Optional expansion flag.
    # If true, expands the output image to make it large enough to hold the entire rotated image.
    # If false or omitted, make the output image the same size as the input image.

    if orientation == 2:
        # Vertical image
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    elif orientation == 3:
        # Rotation 180
        image = image.rotate(180)
    elif orientation == 4:
        image = image.rotate(180).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        # Horizontal image
    elif orientation == 5:
        # Horizontal image + Rotation 90 CCW
        image = image.rotate(-90, expand=True).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    elif orientation == 6:
        # Rotation 270
        image = image.rotate(-90, expand=True)
    elif orientation == 7:
        # Horizontal image + Rotation 270
        image = image.rotate(90, expand=True).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    elif orientation == 8:
        # Rotation 90
        image = image.rotate(90, expand=True)

    return image


def generate_thumbnail(request, thumbnail_info):
    """ generate and save thumbnail if not exist

    before generate thumbnail, you should check:
    1. if repo exist: should exist;
    2. if repo is encrypted: not encrypted;
    """
    size = int(thumbnail_info['size'])
    repo_id = thumbnail_info['repo_id']
    filetype = thumbnail_info['file_type']
    fileext = thumbnail_info['file_ext']
    file_size = thumbnail_info['file_size']
    file_id = thumbnail_info['file_id']
    thumbnail_file = thumbnail_info['thumbnail_path']
    path = thumbnail_info['file_path']
    file_name = thumbnail_info['file_name']

    if filetype == VIDEO and not ENABLE_VIDEO_THUMBNAIL:
        return (False, 400)
    if os.path.exists(thumbnail_file):
        return (True, 200)

    if filetype == VIDEO:
        # video thumbnails
        if ENABLE_VIDEO_THUMBNAIL:
            task_id = thumbnail_task_manager.add_video_task(create_video_thumbnails, repo_id, file_id, path, size,
                                                            thumbnail_file)
            return (task_id, 200)
        else:
            return (False, 400)
    if filetype == PDF:
        # pdf thumbnails
        task_id = thumbnail_task_manager.add_pdf_or_psd_create_task(create_pdf_thumbnails, repo_id, file_id, path,
                                                             size, thumbnail_file, file_size)
        return (task_id, 200)
    if filetype == XMIND:
        task_id = thumbnail_task_manager.add_xmind_create_task(extract_xmind_image, repo_id, path, size)
        return (task_id, 200)

    # image thumbnails
    if file_size > THUMBNAIL_IMAGE_SIZE_LIMIT * 1024 ** 2:
        return (False, 400)
    if fileext.lower() == 'psd':
        task_id = thumbnail_task_manager.add_pdf_or_psd_create_task(create_psd_thumbnails, repo_id, file_id, path,
                                                             size, thumbnail_file, file_size)
        return (task_id, 200)

    task_id = thumbnail_task_manager.add_image_creat_task(create_image_thumbnail, repo_id, file_id,
                                                          thumbnail_file, file_name, size)
    return (task_id, 200)


def create_image_thumbnail(repo_id, file_id, thumbnail_file, file_name, size):
    # image thumbnail
    inner_path = get_inner_path(repo_id, file_id, file_name)
    try:
        image_file = urllib.request.urlopen(inner_path)
        f = BytesIO(image_file.read())
        _create_thumbnail_common(f, thumbnail_file, size)
        return
    except Exception as e:
        logger.warning(e)
        return (False, 500)


def create_psd_thumbnails(repo_id, file_id, path, size, thumbnail_file, file_size):
    try:
        from psd_tools import PSDImage
    except ImportError:
        logger.error("Could not find psd_tools installed. "
                     "Please install by 'pip install psd_tools'")
        return (False, 500)

    tmp_img_path = str(os.path.join(tempfile.gettempdir(), '%s.png' % file_id))
    t1 = timeit.default_timer()

    inner_path = get_inner_path(repo_id, file_id, os.path.basename(path))

    tmp_file = os.path.join(tempfile.gettempdir(), file_id)
    urlretrieve(inner_path, tmp_file)
    psd = PSDImage.open(tmp_file)

    merged_image = psd.topil()
    merged_image.save(tmp_img_path)
    os.unlink(tmp_file)  # remove origin psd file

    t2 = timeit.default_timer()
    logger.debug('Extract psd image [%s](size: %s) takes: %s' % (path, file_size, (t2 - t1)))

    try:
        ret = _create_thumbnail_common(tmp_img_path, thumbnail_file, size)
        os.unlink(tmp_img_path)
        return ret
    except Exception as e:
        logger.warning(e)
        os.path.exists(tmp_img_path) and os.unlink(tmp_img_path)
        return (False, 500)


def create_pdf_thumbnails(repo_id, file_id, path, size, thumbnail_file, file_size):
    t1 = timeit.default_timer()
    inner_path = get_inner_path(repo_id, file_id, os.path.basename(path))
    tmp_path = str(os.path.join(tempfile.gettempdir(), '%s.png' % file_id[:8]))
    pdf_file = urllib.request.urlopen(inner_path)
    pdf_stream = BytesIO(pdf_file.read())
    try:
        pdf_doc = fitz_open(stream=pdf_stream)
        pdf_stream.close()
        page = pdf_doc[0]
        pix = page.get_pixmap()
        pix.save(tmp_path)
        pdf_doc.close()
    except Exception as e:
        logger.warning(e)
        return (False, 500)
    t2 = timeit.default_timer()
    logger.debug('Create PDF thumbnail of [%s](size: %s) takes: %s' % (path, file_size, (t2 - t1)))

    try:
        ret = _create_thumbnail_common(tmp_path, thumbnail_file, size)
        os.unlink(tmp_path)
        return ret
    except Exception as e:
        logger.warning(e)
        os.unlink(tmp_path)
        return (False, 500)


def create_video_thumbnails(repo_id, file_id, path, size, thumbnail_file):
    from moviepy.editor import VideoFileClip
    tmp_image_path = os.path.join(
        tempfile.gettempdir(), file_id + '.png')
    try:
        tmp_video = os.path.join(tempfile.gettempdir(), file_id)
        inner_path = get_inner_path(repo_id, file_id, os.path.basename(path))
        urllib.request.urlretrieve(inner_path, tmp_video)
        clip = VideoFileClip(tmp_video)
        clip.save_frame(tmp_image_path, t=settings.THUMBNAIL_VIDEO_FRAME_TIME)

        ret = _create_thumbnail_common(tmp_image_path, thumbnail_file, size)
        os.unlink(tmp_image_path)
        return ret
    except Exception as e:
        logger.warning(e)
        if os.path.exists(tmp_image_path):
            os.unlink(tmp_image_path)
        return (False, 500)


def _create_thumbnail_common(fp, thumbnail_file, size):
    """Common logic for creating image thumbnail.

    `fp` can be a filename (string) or a file object.
    """
    image = Image.open(fp)

    # check image memory cost size limit
    # use RGBA as default mode(4x8-bit pixels, true colour with transparency mask)
    # every pixel will cost 4 byte in RGBA mode
    width, height = image.size
    image_memory_cost = width * height * 4 / 1024 / 1024
    if image_memory_cost > THUMBNAIL_IMAGE_ORIGINAL_SIZE_LIMIT:
        return (False, 403)

    if image.mode not in ["1", "L", "P", "RGB"]:
        image = image.convert("RGB")

    image = get_rotated_image(image)
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    image.save(thumbnail_file, THUMBNAIL_EXTENSION)
    return (True, 200)


def extract_xmind_image(repo_id, path, size=XMIND_IMAGE_SIZE):
    # get inner path
    file_name = os.path.basename(path)
    file_id = seafile_api.get_file_id_by_path(repo_id, path)
    inner_path = get_inner_path(repo_id, file_id, file_name)

    # extract xmind image
    xmind_file = urllib.request.urlopen(inner_path)
    xmind_file_str = BytesIO(xmind_file.read())
    try:
        xmind_zip_file = zipfile.ZipFile(xmind_file_str, 'r')
    except Exception as e:
        logger.error(e)
        return (False, 500)
    extracted_xmind_image = xmind_zip_file.read('Thumbnails/thumbnail.png')
    extracted_xmind_image_str = BytesIO(extracted_xmind_image)

    # save origin xmind image to thumbnail folder
    thumbnail_dir = os.path.join(THUMBNAIL_ROOT, str(size))
    if not os.path.exists(thumbnail_dir):
        os.makedirs(thumbnail_dir)
    local_xmind_image = os.path.join(thumbnail_dir, file_id)

    try:
        ret = _create_thumbnail_common(extracted_xmind_image_str, local_xmind_image, size)
        return ret
    except Exception as e:
        logger.warning(e)
        return (False, 500)
