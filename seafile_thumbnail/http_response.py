import logging
import time
import os.path
import os
import json
from urllib.parse import quote

from seafile_thumbnail.settings import THUMBNAIL_EXTENSION
from seafile_thumbnail.thumbnail import generate_thumbnail
from seafile_thumbnail.constants import TEXT_CONTENT_TYPE, THUMBNAIL_CONTENT_TYPE, EMPTY_BYTES
from seafile_thumbnail.utils import get_thumbnail_src, get_share_link_thumbnail_src
from seafile_thumbnail.task_queue import thumbnail_task_manager

logger = logging.getLogger(__name__)

TIME_OUT = 30


def gen_response_start(status, content_type):
    return {
        'type': 'http.response.start',
        'status': status,
        'headers': [
            [b'Content-Type', content_type],
            [b'Cache-Control', b'max-age=604800, private']
        ]
    }


def gen_response_body(body):
    return {
        'type': 'http.response.body',
        'body': body
    }


def gen_error_response(status, error_msg):
    response_start = gen_response_start(status, TEXT_CONTENT_TYPE)
    response_body = gen_response_body(error_msg.encode('utf-8'))

    return response_start, response_body


def gen_text_response(text):
    response_start = gen_response_start(200, TEXT_CONTENT_TYPE)
    response_body = gen_response_body(text.encode('utf-8'))

    return response_start, response_body


def gen_cache_response():
    response_start = gen_response_start(304, THUMBNAIL_CONTENT_TYPE)
    response_body = gen_response_body(EMPTY_BYTES)

    return response_start, response_body


async def gen_thumbnail_response(request, thumbnail_info):
    content_type = 'application/json; charset=utf-8'
    result = {}
    repo_id = thumbnail_info['repo_id']
    size = thumbnail_info['size']
    path = thumbnail_info['file_path']
    last_modified = thumbnail_info['last_modified']
    etag = thumbnail_info['etag']
    task_id, status = generate_thumbnail(request, thumbnail_info)
    if status == 400:
        err_msg = 'Failed to create thumbnail.'
        return gen_error_response(status, err_msg)
    if not isinstance(task_id, bool):
        start_time = time.time()
        while True:
            if thumbnail_task_manager.query_status(task_id)[0]:
                break
            if time.time() - start_time > TIME_OUT:
                return gen_error_response(400, 'Timeout Error.')
            time.sleep(0.2)
    src = get_thumbnail_src(repo_id, size, path)
    result['encoded_thumbnail_src'] = quote(src)
    result = json.dumps(result)
    result_b = str(result).encode('utf-8')

    response_start = gen_response_start(200, content_type)
    response_body = gen_response_body(result_b)
    return response_start, response_body


async def thumbnail_get(request, thumbnail_info):
    """
    handle thumbnail src from repo file list
    return thumbnail file to web
    """
    thumbnail_file = thumbnail_info['thumbnail_path']
    last_modified = thumbnail_info['last_modified']
    etag = thumbnail_info['etag']
    if not os.path.exists(thumbnail_file):
        task_id, status = generate_thumbnail(request, thumbnail_info)
        if status == 400:
            err_msg = 'Failed to create thumbnail.'
            return gen_error_response(status, err_msg)
        
        start_time = time.time()
        while True:
            if thumbnail_task_manager.query_status(task_id)[0]:
                break
            if time.time() - start_time > TIME_OUT:
                return gen_error_response(400, 'Timeout Error.')
            time.sleep(0.2)
    try:
        with open(thumbnail_file, 'rb') as f:
            thumbnail = f.read()
            response_start = gen_response_start(200, 'image/' + THUMBNAIL_EXTENSION)
            response_body = gen_response_body(thumbnail)
            if thumbnail:
                response_start['headers'].append([b'Cache-Control', b'max-age=604800, private'])
                response_start['headers'].append([b'Last-Modified', last_modified.encode('utf-8')])
                response_start['headers'].append([b'ETag', etag.encode('utf-8')])

            return response_start, response_body
    except:
        err_msg = 'Failed to create thumbnail.'
        return gen_error_response(400, err_msg)


async def share_link_thumbnail_create(request, thumbnail_info):
    """generate thumbnail from dir download link page

    return thumbnail src to web
    """
    content_type = 'application/json; charset=utf-8'
    result = {}
    token = thumbnail_info['token']
    size = thumbnail_info['size']
    file_name = thumbnail_info['file_name']
    last_modified = thumbnail_info['last_modified']
    etag = thumbnail_info['etag']

    task_id, status = generate_thumbnail(request, thumbnail_info)
    if status == 400:
        err_msg = 'Failed to create thumbnail.'
        return gen_error_response(status, err_msg)
    if not isinstance(task_id, bool):
        start_time = time.time()
        while True:
            if thumbnail_task_manager.query_status(task_id)[0]:
                break
            if time.time() - start_time > TIME_OUT:
                return gen_error_response(400, 'Timeout Error.')
            time.sleep(0.2)
    src = get_share_link_thumbnail_src(token, size, file_name)
    result['encoded_thumbnail_src'] = quote(src)
    result = json.dumps(result)
    result_b = str(result).encode('utf-8')
    response_start = gen_response_start(200, content_type)
    response_body = gen_response_body(result_b)
    return response_start, response_body


async def share_link_thumbnail_get(request, thumbnail_info):
    """ handle thumbnail src from dir download link page

    return thumbnail file to web
    """
    thumbnail_file = thumbnail_info['thumbnail_path']
    last_modified = thumbnail_info['last_modified']
    etag = thumbnail_info['etag']

    
    if not os.path.exists(thumbnail_file):
        task_id, status = generate_thumbnail(request, thumbnail_info)
        if status == 400:
            err_msg = 'Failed to create thumbnail.'
            return gen_error_response(status, err_msg)
        
        start_time = time.time()
        while True:
            if thumbnail_task_manager.query_status(task_id)[0]:
                break
            if time.time() - start_time > TIME_OUT:
                return gen_error_response(400, 'Timeout Error.')
            time.sleep(0.2)
    
    try:
        with open(thumbnail_file, 'rb') as f:
            thumbnail = f.read()
            response_start = gen_response_start(200, 'image/' + THUMBNAIL_EXTENSION)
            response_start['headers'].append([b'Cache-Control', b'max-age=604800, private'])
            response_start['headers'].append([b'ETag', etag.encode('utf-8')])
            response_start['headers'].append([b'Last-Modified', last_modified.encode('utf-8')])
            response_body = gen_response_body(thumbnail)
            return response_start, response_body
    except:
        err_msg = 'Failed to create thumbnail.'
        return gen_error_response(400, err_msg)
