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
from seafile_thumbnail.constants import VIDEO, PDF, XMIND, EMPTY_BYTES
from seafile_thumbnail.settings import ENABLE_VIDEO_THUMBNAIL, THUMBNAIL_IMAGE_SIZE_LIMIT, THUMBNAIL_ROOT, \
    THUMBNAIL_IMAGE_ORIGINAL_SIZE_LIMIT, THUMBNAIL_EXTENSION

from seaserv import get_repo, get_file_size, seafile_api

try:  # Py2 and Py3 compatibility
    from urllib.request import urlretrieve
except:
    from urllib.request import urlretrieve

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

XMIND_IMAGE_SIZE = 1024


# =================Thumbnail================
class Thumbnail(object):
    def __init__(self, **info):
        self.__dict__.update(info)
        self.body = EMPTY_BYTES
        self.get()

    def get(self):
        if os.path.exists(self.thumbnail_path):
            with open(self.thumbnail_path, 'rb') as f:
                self.body = f.read()

        else:
            self.generate_thumbnail()

    def get_rotated_image(self, image):

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


    # def handle_image(self):
    #
    #     task_id = self.task_manage.add_xx_task()
    #
    #     while True:
    #
    #         if self.task_manager.query(task_id) == 'true':
    #             pass



    def generate_thumbnail(self):
        """ generate and save thumbnail if not exist

        before generate thumbnail, you should check:
        1. if repo exist: should exist;
        2. if repo is encrypted: not encrypted;
        """
        repo_id = self.repo_id
        path = self.file_path
        size = int(self.size)
        file_id = self.file_id
        file_name = self.file_name
        thumbnail_file = self.thumbnail_path
        if self.file_type == VIDEO and not ENABLE_VIDEO_THUMBNAIL:
            raise AssertionError(400, 'not configured.')

        repo = get_repo(repo_id)
        file_size = get_file_size(repo.store_id, repo.version, file_id)

        if self.file_type == VIDEO:
            # video thumbnails
            if ENABLE_VIDEO_THUMBNAIL:
                self.create_video_thumbnails(repo, file_id, path, size,
                                             thumbnail_file, file_size)
            else:
                raise AssertionError(400, 'not configured.')
            return
        if self.file_type == PDF:
            # pdf thumbnails
            self.create_pdf_thumbnails(repo, file_id, path, size,
                                       thumbnail_file, file_size)
            return

        if self.file_type == XMIND:
            self.extract_xmind_image(repo_id, size)
            return

        # image thumbnails
        if file_size > THUMBNAIL_IMAGE_SIZE_LIMIT * 1024 ** 2:
            raise AssertionError(400, 'file_size invalid.')

        if self.file_ext.lower() == 'psd':
            self.create_psd_thumbnails(repo, file_id, path, size,
                                       thumbnail_file, file_size)
            return

        # image thumbnail
        inner_path = get_inner_path(repo_id, file_id, file_name)
        try:
            image_file = urllib.request.urlopen(inner_path)
            f = BytesIO(image_file.read())
            self._create_thumbnail_common(f, thumbnail_file, size)
            return
        except Exception as e:
            logger.warning(e)
            raise AssertionError(500, 'Internal server error.')

    def create_psd_thumbnails(self, repo, file_id, path, size, thumbnail_file, file_size):
        try:
            from psd_tools import PSDImage
        except ImportError:
            logger.error("Could not find psd_tools installed. "
                         "Please install by 'pip install psd_tools'")
            raise AssertionError(500, 'Internal server error.')

        tmp_img_path = str(os.path.join(tempfile.gettempdir(), '%s.png' % file_id))
        t1 = timeit.default_timer()

        inner_path = get_inner_path(repo.id, file_id, self.file_name)

        tmp_file = os.path.join(tempfile.gettempdir(), file_id)
        urlretrieve(inner_path, tmp_file)
        psd = PSDImage.open(tmp_file)

        merged_image = psd.topil()
        merged_image.save(tmp_img_path)
        os.unlink(tmp_file)  # remove origin psd file

        t2 = timeit.default_timer()
        logger.debug('Extract psd image [%s](size: %s) takes: %s' % (path, file_size, (t2 - t1)))

        try:
            self._create_thumbnail_common(tmp_img_path, thumbnail_file, size)
            os.unlink(tmp_img_path)
            return
        except Exception as e:
            logger.error(e)
            os.unlink(tmp_img_path)
            raise AssertionError(500, 'Internal server error.')

    def create_pdf_thumbnails(self, repo, file_id, path, size, thumbnail_file, file_size):
        t1 = timeit.default_timer()
        inner_path = get_inner_path(repo.id, file_id, self.file_name)

        tmp_path = str(os.path.join(tempfile.gettempdir(), '%s.jpg' % file_id[:8]))
        pdf_file = urllib.request.urlopen(inner_path)
        pdf_stream = BytesIO(pdf_file.read())
        try:
            pdf_doc = fitz_open(stream=pdf_stream)
            page = pdf_doc[0]
            pix = page.get_pixmap()
            pix.save(tmp_path)
        except Exception as e:
            logger.error(e)
            raise AssertionError(500, 'Internal server error.')
        t2 = timeit.default_timer()
        logger.debug('Create PDF image of [%s](size: %s) takes: %s' % (path, file_size, (t2 - t1)))

        try:
            self._create_thumbnail_common(tmp_path, thumbnail_file, size)
            pdf_stream.close()
            pdf_doc.close()
            os.unlink(tmp_path)
            return
        except Exception as e:
            logger.error(e)
            pdf_stream.close()
            pdf_doc.close()
            os.unlink(tmp_path)
            raise AssertionError(500, 'Internal server error.')

    def create_video_thumbnails(self, repo, file_id, path, size, thumbnail_file, file_size):
        from moviepy.editor import VideoFileClip
        t1 = timeit.default_timer()
        tmp_image_path = os.path.join(
            tempfile.gettempdir(), file_id + '.png')
        tmp_video = os.path.join(tempfile.gettempdir(), file_id)
        inner_path = get_inner_path(repo.id, file_id, self.file_name)
        urllib.request.urlretrieve(inner_path, tmp_video)
        clip = VideoFileClip(tmp_video)
        clip.save_frame(
            tmp_image_path, t=settings.THUMBNAIL_VIDEO_FRAME_TIME)
        t2 = timeit.default_timer()
        logger.debug('Create Video image of [%s](size: %s) takes: %s' % (path, file_size, (t2 - t1)))
        try:
            self._create_thumbnail_common(tmp_image_path, thumbnail_file, size)
            os.unlink(tmp_image_path)
            return
        except Exception as e:
            logger.error(e)
            os.unlink(tmp_image_path)
            raise AssertionError(500, 'Internal server error.')

    def _create_thumbnail_common(self, fp, thumbnail_file, size):
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
            raise AssertionError(500, 'Thumbnail original size limit.')

        if image.mode not in ["1", "L", "P", "RGB"]:
            image = image.convert("RGB")

        image = self.get_rotated_image(image)
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
        image.save(thumbnail_file, THUMBNAIL_EXTENSION)
        # PIL to bytes
        byte_io = BytesIO()
        image.save(byte_io, format='JPEG')
        self.body = byte_io.read()

    def extract_xmind_image(self, repo_id, size=XMIND_IMAGE_SIZE):
        # get inner path
        inner_path = get_inner_path(repo_id, self.file_id, self.file_name)
        # extract xmind image
        xmind_file = urllib.request.urlopen(inner_path)
        xmind_file_str = BytesIO(xmind_file.read())
        try:
            xmind_zip_file = zipfile.ZipFile(xmind_file_str, 'r')
        except Exception as e:
            logger.error(e)
            raise AssertionError(500, 'Internal server error.')
        extracted_xmind_image = xmind_zip_file.read('Thumbnails/thumbnail.png')
        extracted_xmind_image_str = BytesIO(extracted_xmind_image)

        # save origin xmind image to thumbnail folder
        thumbnail_dir = os.path.join(THUMBNAIL_ROOT, str(size))
        if not os.path.exists(thumbnail_dir):
            os.makedirs(thumbnail_dir)
        local_xmind_image = os.path.join(thumbnail_dir, self.file_id)
        try:
            self._create_thumbnail_common(extracted_xmind_image_str, local_xmind_image, size)
            return
        except Exception as e:
            logger.error(e)
            raise AssertionError(500, 'Internal server error.')
