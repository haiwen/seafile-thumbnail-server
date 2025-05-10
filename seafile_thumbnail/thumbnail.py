import subprocess
import logging
import os
import tempfile
import timeit
import zipfile
from io import BytesIO
from PIL import Image

from seafile_thumbnail.utils import get_file_content_by_obj_id
from seafile_thumbnail.constants import VIDEO, PDF, XMIND
from seafile_thumbnail.settings import ENABLE_VIDEO_THUMBNAIL, THUMBNAIL_IMAGE_SIZE_LIMIT, THUMBNAIL_ROOT, \
    THUMBNAIL_IMAGE_ORIGINAL_SIZE_LIMIT, THUMBNAIL_EXTENSION, THUMBNAIL_VIDEO_FRAME_TIME, SAFETY_MARGIN
from seafile_thumbnail.thumbnail_task_manager import thumbnail_task_manager
from seaserv import seafile_api

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

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

    if filetype == VIDEO and not ENABLE_VIDEO_THUMBNAIL:
        return (False, 400)
    if os.path.exists(thumbnail_file):
        return (True, 200)

    if filetype == VIDEO:
        # video thumbnails
        task_id, status = thumbnail_task_manager.add_video_task(create_video_thumbnails, repo_id, file_id, size,
                                                        thumbnail_file)
        if status != 200:
            return (task_id, status)
        return (task_id, 200)
    if filetype == PDF:
        # pdf thumbnails
        task_id, status = thumbnail_task_manager.add_pdf_or_psd_create_task(create_pdf_thumbnails, repo_id, file_id, path,
                                                             size, thumbnail_file, file_size)
        if status != 200:
                return (task_id, status)
        return (task_id, 200)
    if filetype == XMIND:
        task_id, status = thumbnail_task_manager.add_xmind_create_task(extract_xmind_image, repo_id, path, size)
        if status != 200:
                return (task_id, status)
        return (task_id, 200)

    # image thumbnails
    if file_size > THUMBNAIL_IMAGE_SIZE_LIMIT * 1024 ** 2:
        return ('The image size exceeds the limit', 400)
    if fileext.lower() == 'psd':
        task_id, status = thumbnail_task_manager.add_pdf_or_psd_create_task(create_psd_thumbnails, repo_id, file_id, path,
                                                             size, thumbnail_file, file_size)
        if status != 200:
                return (task_id, status)
        return (task_id, 200)

    task_id, status = thumbnail_task_manager.add_image_creat_task(create_image_thumbnail, repo_id, file_id,
                                                          thumbnail_file, size)
    if status != 200:
        return (task_id, status)
    return (task_id, 200)


def create_image_thumbnail(repo_id, file_id, thumbnail_file, size):
    # image thumbnail
    image_file = get_file_content_by_obj_id(repo_id, file_id)
    if image_file == b'':
        raise Exception('Image file is empty')
    f = BytesIO(image_file)
    _create_thumbnail_common(f, thumbnail_file, size)
    return


def create_psd_thumbnails(repo_id, file_id, path, size, thumbnail_file, file_size):
    try:
        from psd_tools import PSDImage
    except ImportError:
        logger.error("Could not find psd_tools installed. "
                     "Please install by 'pip install psd_tools'")
        return

    tmp_img_path = str(os.path.join(tempfile.gettempdir(), '%s.png' % file_id))
    t1 = timeit.default_timer()
    tmp_file = get_file_content_by_obj_id(repo_id, file_id)
    f = BytesIO(tmp_file)
    psd = PSDImage.open(f)

    merged_image = psd.topil()
    merged_image.save(tmp_img_path)

    t2 = timeit.default_timer()
    logger.debug('Extract psd image [%s](size: %s) takes: %s' % (path, file_size, (t2 - t1)))

    try:
        _create_thumbnail_common(tmp_img_path, thumbnail_file, size)
        os.unlink(tmp_img_path)
        return
    except Exception as e:
        logger.warning(e)
        os.path.exists(tmp_img_path) and os.unlink(tmp_img_path)
        return


def pdf_bytes_to_images(pdf_bytes, prefix_path, dpi=200):
    with tempfile.NamedTemporaryFile(delete=True, suffix='.pdf') as tmpfile:
        tmpfile.write(pdf_bytes)
        tmp_file = tmpfile.name
        command = [
            'pdftoppm',
            '-png',
            '-r', str(dpi),
            '-f', '1',
            '-l', '1',
            '-singlefile', tmp_file,
            '-o', prefix_path
        ]
        subprocess.check_output(command)


def create_pdf_thumbnails(repo_id, file_id, path, size, thumbnail_file, file_size):
    t1 = timeit.default_timer()
    tmp_path = str(os.path.join(tempfile.gettempdir(), '%s' % file_id[:8]))
    image_file = get_file_content_by_obj_id(repo_id, file_id)
    pdf_bytes_to_images(image_file, tmp_path)
    tmp_path = tmp_path + '.png'
    t2 = timeit.default_timer()
    logger.debug('Create PDF thumbnail of [%s](size: %s) takes: %s' % (path, file_size, (t2 - t1)))

    try:
        _create_thumbnail_common(tmp_path, thumbnail_file, size)
        os.unlink(tmp_path)
        return
    except Exception as e:
        logger.warning(e)
        os.unlink(tmp_path)
        return


def create_video_thumbnails(repo_id, file_id, size, thumbnail_file):
    tmp_image_path = os.path.join(
        tempfile.gettempdir(), file_id + '.png')
    try:
        tmp_video = get_file_content_by_obj_id(repo_id, file_id)
        if tmp_video == b'':
            raise Exception('Video file is empty')
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmpfile:
            tmpfile.write(tmp_video)
            tmpfile.seek(0)
            tmp_video_path = tmpfile.name
        
        # get video duration
        duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                       '-of', 'default=noprint_wrappers=1:nokey=1', tmp_video_path]
        duration = float(subprocess.check_output(duration_cmd).decode().strip())
        if THUMBNAIL_VIDEO_FRAME_TIME <= duration - SAFETY_MARGIN:
            frame_time = THUMBNAIL_VIDEO_FRAME_TIME
        else:
            frame_time = duration / 2
        subprocess.check_output(['ffmpeg', '-i', tmp_video_path, '-ss', str(frame_time), 
                               '-vframes', '1', '-nostdin', tmp_image_path])
        
        if os.path.exists(tmp_image_path) and os.path.getsize(tmp_image_path) > 0:
            _create_thumbnail_common(tmp_image_path, thumbnail_file, size)
            os.unlink(tmp_image_path)
            os.remove(tmp_video_path)
            return True
        else:
            raise Exception("Failed to generate video thumbnail")
            
    except Exception as e:
        if os.path.exists(tmp_image_path):
            os.unlink(tmp_image_path)
            os.remove(tmp_video_path)
        raise e


def _create_thumbnail_common(fp, thumbnail_file, size):
    """Common logic for creating image thumbnail.

    `fp` can be a filename (string) or a file object.
    """
    image = Image.open(fp)

    # check image memory cost size limit
    # use RGBA as default mode(4x8-bit pixels, true colour with transparency mask)
    # every pixel will cost 4 byte in RGBA mode
    width, height = image.size
    thumbnail_image_size = width * height * 4 / 1024 / 1024
    if thumbnail_image_size > THUMBNAIL_IMAGE_ORIGINAL_SIZE_LIMIT:
        logger.warning('Image memory cost exceeds the limit')
        return

    if image.mode not in ["1", "L", "P", "RGB", "RGBA"]:
        image = image.convert("RGB")

    image = get_rotated_image(image)
    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    save_type = THUMBNAIL_EXTENSION
    if image.mode in ['RGBA', 'P']:
        save_type = 'png'
    image.save(thumbnail_file, save_type, icc_profile=image.info.get('icc_profile'))
    return


def extract_xmind_image(repo_id, path, size=XMIND_IMAGE_SIZE):
    file_id = seafile_api.get_file_id_by_path(repo_id, path)
    xmind_file = get_file_content_by_obj_id(repo_id, file_id)
    xmind_file_str = BytesIO(xmind_file)
    
    xmind_zip_file = zipfile.ZipFile(xmind_file_str, 'r')
    extracted_xmind_image = xmind_zip_file.read('Thumbnails/thumbnail.png')
    extracted_xmind_image_str = BytesIO(extracted_xmind_image)

    # save origin xmind image to thumbnail folder
    thumbnail_dir = os.path.join(THUMBNAIL_ROOT, str(size))
    if not os.path.exists(thumbnail_dir):
        os.makedirs(thumbnail_dir)
    local_xmind_image = os.path.join(thumbnail_dir, file_id)

    _create_thumbnail_common(extracted_xmind_image_str, local_xmind_image, size)
    return
