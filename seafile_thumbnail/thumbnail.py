import posixpath
import subprocess
import logging
import os
import shutil
import tempfile
import timeit
import zipfile
from io import BytesIO
from PIL import Image

from seafile_thumbnail.screenshot import get_playwright_manager
from seafile_thumbnail.errors import FileInvalidError
from seafile_thumbnail.utils import get_file_content_by_obj_id, need_generate_thumbnail, normalize_file_path, SeafileAPI, \
    gen_thumbnail_access_token, stream_file_to_path
from seafile_thumbnail.constants import VIDEO, PDF, XMIND, SVG, SEADOC
from seafile_thumbnail.settings import ENABLE_VIDEO_THUMBNAIL, THUMBNAIL_IMAGE_SIZE_LIMIT, THUMBNAIL_ROOT, \
    THUMBNAIL_IMAGE_ORIGINAL_SIZE_LIMIT, THUMBNAIL_EXTENSION, THUMBNAIL_VIDEO_FRAME_TIME, SAFETY_MARGIN, \
    INNER_SEAHUB_SERVICE_URL, THUMBNAIL_PDF_SIZE_LIMIT
from seafile_thumbnail.thumbnail_task_manager import thumbnail_task_manager

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

try:
    import pillow_avif
except ImportError:
    pass

logger = logging.getLogger(__name__)

XMIND_IMAGE_SIZE = 1024
MAX_PAGE_AREA = 8000000  # 8 million square points
# If the page size is large but does not exceed the limit, reduce DPI
LARGE_WIDTH_HEIGHT_THRESHOLD = 2000
LARGE_AREA_THRESHOLD = 3000000
# PDF size threshold for detailed page size checking (bytes)
LARGE_PDF_SIZE_THRESHOLD = THUMBNAIL_PDF_SIZE_LIMIT * 1024 * 1024  # 50MB

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
    origin_repo_id = thumbnail_info['origin_repo_id']   
    filetype = thumbnail_info['file_type']
    fileext = thumbnail_info['file_ext']
    file_size = thumbnail_info['file_size']
    file_id = thumbnail_info['file_id']
    thumbnail_file = thumbnail_info['thumbnail_path']
    path = thumbnail_info['file_path']
    origin_parent_path = thumbnail_info['origin_parent_path']
   
    if origin_repo_id:
        repo_id = origin_repo_id
        path = posixpath.join(origin_parent_path, path.lstrip('/'))
        
    if filetype == VIDEO and not ENABLE_VIDEO_THUMBNAIL:
        return (False, 400)
    if not need_generate_thumbnail(thumbnail_info):
        return (True, 200)

    if filetype == VIDEO:
        # video thumbnails
        task_id, status = thumbnail_task_manager.add_video_task(create_video_thumbnails, repo_id, file_id, path, 
                                                                size, thumbnail_file, file_size)
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
        task_id, status = thumbnail_task_manager.add_xmind_create_task(extract_xmind_image, repo_id, file_id, path, size, file_size)
        if status != 200:
                return (task_id, status)
        return (task_id, 200)

    # image thumbnails
    if file_size > THUMBNAIL_IMAGE_SIZE_LIMIT * 1024 ** 2:
        return ('The image size exceeds the limit', 400)
    if fileext.lower() in ('psd', 'psb'):
        task_id, status = thumbnail_task_manager.add_pdf_or_psd_create_task(create_psd_thumbnails, repo_id, file_id, path,
                                                             size, thumbnail_file, file_size)
        if status != 200:
                return (task_id, status)
        return (task_id, 200)
    
    if filetype == SVG:
        task_id, status = thumbnail_task_manager.add_svg_create_task(create_svg_thumbnails, repo_id, file_id, path,
                                                                     size, thumbnail_file, file_size)
        if status != 200:
            return (task_id, status)
        return (task_id, 200)
    
    if filetype == SEADOC:
        task_id, status = thumbnail_task_manager.add_seadoc_create_task(create_seadoc_thumbnail, request, repo_id, file_id,
                                                                            path,
                                                                            size, thumbnail_file, file_size)
        if status != 200:
            return (task_id, status)
        return (task_id, 200)
    
    task_id, status = thumbnail_task_manager.add_image_creat_task(create_image_thumbnail, repo_id, file_id, path,
                                                          thumbnail_file, size)

    if status != 200:
        return (task_id, status)
    return (task_id, 200)


def create_image_thumbnail(repo_id, file_id, thumbnail_file, size):
    image_file = None
    f = None
    try:
        image_file = get_file_content_by_obj_id(repo_id, file_id)
        if image_file == b'':
            raise Exception('Image file is empty')
        f = BytesIO(image_file)
        _create_thumbnail_common(f, thumbnail_file, size)
    finally:
        if f is not None:
            f.close()
        if image_file is not None:
            del image_file
    return


def create_psd_thumbnails(repo_id, file_id, path, size, thumbnail_file, file_size):
    try:
        from psd_tools import PSDImage
    except ImportError:
        logger.error("Could not find psd_tools installed. "
                     "Please install by 'pip install psd_tools'")
        return

    tmp_img_path = str(os.path.join(tempfile.gettempdir(), '%s.png' % file_id))
    tmp_file = None
    f = None
    psd = None
    merged_image = None
    
    try:
        t1 = timeit.default_timer()
        tmp_file = get_file_content_by_obj_id(repo_id, file_id)
        f = BytesIO(tmp_file)
        psd = PSDImage.open(f)
        merged_image = psd.topil()
        merged_image.save(tmp_img_path)
        t2 = timeit.default_timer()
        logger.debug('Extract psd image [%s](size: %s) takes: %s' % (path, file_size, (t2 - t1)))

        _create_thumbnail_common(tmp_img_path, thumbnail_file, size)
    except Exception as e:
        logger.warning(e)
    finally:
        if merged_image is not None:
            merged_image.close()
        if f is not None:
            f.close()
        if tmp_file is not None:
            del tmp_file
        if os.path.exists(tmp_img_path):
            os.unlink(tmp_img_path)
    return


def pdf_to_images(pdf_input, prefix_path, dpi=150, file_size=0):
    """Convert PDF to images.
    
    Args:
        pdf_input: Either bytes content or file path (str)
        prefix_path: Output path prefix
        dpi: Resolution
        file_size: File size in bytes (used for large file detection)
    """
    # Determine if input is bytes or file path
    if isinstance(pdf_input, bytes):
        tmpfile = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        tmpfile.write(pdf_input)
        tmpfile.close()
        tmp_file = tmpfile.name
        cleanup_tmp = True
        check_size = len(pdf_input)
    else:
        # pdf_input is a file path
        tmp_file = pdf_input
        cleanup_tmp = False
        check_size = file_size
    
    try:
        if check_size > LARGE_PDF_SIZE_THRESHOLD:
            pdf_info_command = [
                'pdfinfo',
                '-f', '1',
                '-l', '1',
                tmp_file
            ]
            try:
                page_info = subprocess.check_output(pdf_info_command, stderr=subprocess.PIPE).decode('utf-8')
                page_size = None
                for line in page_info.split('\n'):
                    if 'Page    1 size:' in line:
                        page_size = line.strip()
                        break
                # check page size
                if page_size:
                    # format: "Page    1 size:  6000 x 6000 pts"
                    parts = page_size.split(':', 1)[1].strip().split('x')
                    if len(parts) >= 2:
                        width = float(parts[0].strip())
                        height = float(parts[1].split('pts')[0].strip())
                        area = width * height
                        if area > MAX_PAGE_AREA:
                            raise Exception(f'PDF page area too large: {area:.0f} sq pts (limit: {MAX_PAGE_AREA})')

                        if (width > LARGE_WIDTH_HEIGHT_THRESHOLD or height > LARGE_WIDTH_HEIGHT_THRESHOLD or 
                            area > LARGE_AREA_THRESHOLD):
                            dpi = 72  # use min dpi
                            logger.info(f'Large PDF page detected ({width}x{height}), reducing DPI to {dpi}')
                            
            except Exception as e:
                # If it is clear that the page was skipped due to being too large, throw the exception again 
                if 'PDF page too large' in str(e) or 'PDF page area too large' in str(e):
                    raise 
                dpi = 72
        
        command = [
            'pdftoppm',
            '-png',
            '-r', str(dpi),
            '-f', '1',
            '-l', '1',
            '-scale-to', '1024',
            '-singlefile', tmp_file,
            '-o', prefix_path
        ]
        try:
            subprocess.check_output(command, timeout=60, stderr=subprocess.STDOUT)
        except subprocess.TimeoutExpired:
            raise FileInvalidError('PDF processing timeout')
        except subprocess.CalledProcessError as e:
            output = e.output.decode(errors='replace').strip() if e.output else str(e)
            raise FileInvalidError(f'pdftoppm failed: {output}')
    finally:
        if cleanup_tmp and os.path.exists(tmp_file):
            os.unlink(tmp_file)


def create_pdf_thumbnails(repo_id, file_id, path, size, thumbnail_file, file_size):
    """Create PDF thumbnail.
    
    For large files (> THUMBNAIL_IMAGE_SIZE_LIMIT), use streaming to avoid memory issues.
    For small files, load into memory for better performance.
    """
    t1 = timeit.default_timer()
    tmp_dir = tempfile.mkdtemp(prefix=f'{file_id}_')
    tmp_prefix = os.path.join(tmp_dir, 'page')
    tmp_png_path = tmp_prefix + '.png'  # pdftoppm outputs to this path
    tmp_pdf_path = os.path.join(tmp_dir, 'source.pdf')
    pdf_input = None
    size_limit_bytes = THUMBNAIL_IMAGE_SIZE_LIMIT * 1024 * 1024
    
    try:
        if file_size > size_limit_bytes:
            # Large file: use streaming to write to temp file, then pass file path
            stream_file_to_path(repo_id, file_id, tmp_pdf_path)
            pdf_to_images(tmp_pdf_path, tmp_prefix, file_size=file_size)
        else:
            # Small file: load into memory directly
            pdf_input = get_file_content_by_obj_id(repo_id, file_id)
            pdf_to_images(pdf_input, tmp_prefix)
            del pdf_input
            pdf_input = None
        
        t2 = timeit.default_timer()
        logger.debug('Create PDF thumbnail of [%s](size: %s) takes: %s' % (path, file_size, (t2 - t1)))

        if not os.path.exists(tmp_png_path) or os.path.getsize(tmp_png_path) == 0:
            raise FileInvalidError('The thumbnail image generated by pdftoppm is empty')

        _create_thumbnail_common(tmp_png_path, thumbnail_file, size)
    except Exception as e:
        if isinstance(e, FileInvalidError):
            raise
        raise
    finally:
        if pdf_input is not None:
            del pdf_input
        # Cleanup temp files
        if os.path.exists(tmp_pdf_path):
            os.unlink(tmp_pdf_path)
        if os.path.exists(tmp_png_path):
            os.unlink(tmp_png_path)
        if os.path.exists(tmp_dir):
            os.rmdir(tmp_dir)
    return


def create_video_thumbnails(repo_id, file_id, size, thumbnail_file, file_size=0):
    """Create video thumbnail.
    
    For large files (> THUMBNAIL_IMAGE_SIZE_LIMIT), use streaming to avoid memory issues.
    For small files, load into memory for better performance.
    """
    tmp_dir = tempfile.mkdtemp(prefix=f'{file_id}_')
    tmp_image_path = os.path.join(tmp_dir, 'thumbnail.png')
    tmp_video_path = os.path.join(tmp_dir, 'source.mp4')
    size_limit_bytes = THUMBNAIL_IMAGE_SIZE_LIMIT * 1024 * 1024
    
    try:
        if file_size > size_limit_bytes:
            # Large file: use streaming to avoid memory issues
            bytes_written = stream_file_to_path(repo_id, file_id, tmp_video_path)
            if bytes_written == 0:
                raise FileInvalidError('Video file is empty')
        else:
            # Small file: load into memory for better performance
            video_content = get_file_content_by_obj_id(repo_id, file_id)
            if not video_content:
                raise FileInvalidError('Video file is empty')
            with open(tmp_video_path, 'wb') as f:
                f.write(video_content)
            del video_content
        
        # get video duration
        duration_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                       '-of', 'default=noprint_wrappers=1:nokey=1', tmp_video_path]
        try:
            duration = float(subprocess.check_output(duration_cmd, stderr=subprocess.STDOUT).decode().strip())
        except subprocess.CalledProcessError as e:
            output = e.output.decode(errors='replace').strip() if e.output else str(e)
            raise FileInvalidError(f'ffprobe failed: {output}')
        if THUMBNAIL_VIDEO_FRAME_TIME <= duration - SAFETY_MARGIN:
            frame_time = THUMBNAIL_VIDEO_FRAME_TIME
        else:
            frame_time = duration / 2
        ffmpeg_cmd = ['ffmpeg', '-i', tmp_video_path, '-ss', str(frame_time), 
                      '-vframes', '1', '-nostdin', tmp_image_path]
        try:
            subprocess.check_output(ffmpeg_cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            output = e.output.decode(errors='replace').strip() if e.output else str(e)
            raise FileInvalidError(f'ffmpeg failed: {output}')
        
        if os.path.exists(tmp_image_path) and os.path.getsize(tmp_image_path) > 0:
            _create_thumbnail_common(tmp_image_path, thumbnail_file, size)
            return True
        else:
            raise FileInvalidError('The thumbnail image generated by ffmpeg is empty')
    finally:
        # Cleanup temp files
        if tmp_image_path and os.path.exists(tmp_image_path):
            os.unlink(tmp_image_path)
        if tmp_video_path and os.path.exists(tmp_video_path):
            os.remove(tmp_video_path)
        if tmp_dir and os.path.exists(tmp_dir):
            os.rmdir(tmp_dir)
    

def create_svg_thumbnails(repo_id, file_id, path, size, thumbnail_file, file_size):
    try:
        import cairosvg
    except ImportError:
        logger.error("Could not find cairosvg installed. "
                     "Please install by 'pip install cairosvg' (requires system cairo library)")
        raise Exception("Missing dependency: cairosvg")
    
    svg_content = None
    tmp_png_path = os.path.join(tempfile.gettempdir(), f"{file_id}.png")
    
    try:
        svg_content = get_file_content_by_obj_id(repo_id, file_id)
        t1 = timeit.default_timer()
        cairosvg.svg2png(
            bytestring=svg_content,
            write_to=tmp_png_path,
            dpi=200,
            output_width=size,
            output_height=size
        )
        # MEMORY FIX: delete svg_content after conversion
        del svg_content
        svg_content = None
        
        t2 = timeit.default_timer()
        logger.debug(f"Convert SVG [{path}] to PNG takes: {t2 - t1:.2f}s (size: {file_size} bytes)")
        
        _create_thumbnail_common(tmp_png_path, thumbnail_file, size)
    except Exception as e:
        logger.exception(e)
        logger.error(f"Failed to generate SVG thumbnail for [{path}]: {str(e)}")
        raise e
    finally:
        if svg_content is not None:
            del svg_content
        if os.path.exists(tmp_png_path):
            os.unlink(tmp_png_path)
    return
def _create_thumbnail_common(fp, thumbnail_file, size, fix_width=False, path=None):
    """Common logic for creating image thumbnail.

    `fp` can be a filename (string) or a file object.
    """
    image = Image.open(fp)

    # check image memory cost size limit
    # use RGBA as default mode(4x8-bit pixels, true colour with transparency mask)
    # every pixel will cost 4 byte in RGBA mode
    try:
        width, height = image.size
        
        thumbnail_image_size = width * height * 4 / 1024 / 1024
        if thumbnail_image_size > THUMBNAIL_IMAGE_ORIGINAL_SIZE_LIMIT:
            raise Exception('Image memory cost exceeds the limit')
            
        if image.mode not in ["1", "L", "P", "RGB", "RGBA"]:
            image = image.convert("RGB")
        image = get_rotated_image(image)
        if fix_width:
            image.thumbnail((size, 100000), Image.Resampling.LANCZOS)
        else:
            image.thumbnail((size, size), Image.Resampling.LANCZOS)
        save_type = THUMBNAIL_EXTENSION
        if image.mode in ['RGBA', 'P']:
            save_type = 'png'
        image.save(thumbnail_file, save_type, icc_profile=image.info.get('icc_profile'))
        
        # future remove
        if fix_width:
            image2 = Image.open(thumbnail_file)
            width2, height2 = image2.size
            logger.debug(f"sdoc screenshot size: w:{width}, h:{height}  sdoc thumbnail_size:w:{width2}, h:{height2}, path:{path}")
    finally:
        image.close()
    return


def extract_xmind_image(repo_id, file_id, size=XMIND_IMAGE_SIZE, file_size=0):
    """Extract thumbnail from XMIND file.
    
    For large files (> THUMBNAIL_IMAGE_SIZE_LIMIT), use streaming to avoid memory issues.
    For small files, load into memory for better performance.
    """
    xmind_file = None
    xmind_file_str = None
    xmind_zip_file = None
    extracted_xmind_image_str = None
    tmp_xmind_path = os.path.join(tempfile.gettempdir(), file_id + '.xmind')
    size_limit_bytes = THUMBNAIL_IMAGE_SIZE_LIMIT * 1024 * 1024
    
    try:
        if file_size > size_limit_bytes:
            # Large file: use streaming to write to temp file
            stream_file_to_path(repo_id, file_id, tmp_xmind_path)
            xmind_zip_file = zipfile.ZipFile(tmp_xmind_path, 'r')
        else:
            # Small file: load into memory directly
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
    finally:
        if extracted_xmind_image_str is not None:
            extracted_xmind_image_str.close()
        if xmind_zip_file is not None:
            xmind_zip_file.close()
        if xmind_file_str is not None:
            xmind_file_str.close()
        if xmind_file is not None:
            del xmind_file
        if os.path.exists(tmp_xmind_path):
            os.unlink(tmp_xmind_path)
    return

def create_seadoc_thumbnail(request, repo_id, file_id, path, size, thumbnail_file, file_size):
    path = normalize_file_path(path)
    tmp_dir = tempfile.mkdtemp(prefix=f'{file_id}_')
    tmp_png_path = os.path.join(tmp_dir, 'screenshot.png')
    access_token = gen_thumbnail_access_token()
    seadoc_preview_url = f"{INNER_SEAHUB_SERVICE_URL.rstrip('/')}/repo/{repo_id}/sdoc/preview/{path}?access_token={access_token}"

    try:
        t1 = timeit.default_timer()
        get_playwright_manager().screenshot_from_url(seadoc_preview_url, tmp_png_path, request=request, access_token=access_token)
        t2 = timeit.default_timer()
        logger.debug(f"Convert SDOC [{path}] to PNG takes: {t2 - t1:.2f}s")
        if not os.path.exists(tmp_png_path) or os.path.getsize(tmp_png_path) == 0:
            raise FileInvalidError('The screenshot generated for SDOC is empty')
        _create_thumbnail_common(tmp_png_path, thumbnail_file, size, fix_width=True, path=path)
        return
    except Exception as e:
        if isinstance(e, FileInvalidError):
            logger.warning(f"File invalid for SDOC thumbnail for {path}, seadoc_preview_url: {seadoc_preview_url}")
        else:
            logger.error(f"Failed to generate SDOC thumbnail for {path}: {str(e)}, seadoc_preview_url: {seadoc_preview_url}")
        raise
    finally:
        if os.path.exists(tmp_png_path):
            os.unlink(tmp_png_path)
        if os.path.exists(tmp_dir):
            os.rmdir(tmp_dir)
    


def remove_thumbnail_by_dir(file_uuid):
    
    for item in os.listdir(THUMBNAIL_ROOT):
        size_dir = os.path.join(THUMBNAIL_ROOT, item)
        if not os.path.isdir(size_dir):
            continue
        
        target_folder = os.path.join(size_dir, file_uuid)
        
        if not os.path.exists(target_folder):
            continue
        
        try:
            for filename in os.listdir(target_folder):
                file_path = os.path.join(target_folder, filename)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
        except Exception as e:
            pass
