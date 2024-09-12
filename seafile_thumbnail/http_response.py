import re
import os.path
from urllib.parse import quote
import json

from seafile_thumbnail.constants import TEXT_CONTENT_TYPE, THUMBNAIL_CONTENT_TYPE, EMPTY_BYTES
from seafile_thumbnail.utils import get_thumbnail_src, get_share_link_thumbnail_src


def gen_response_start(status, content_type):
    return {
        'type': 'http.response.start',
        'status': status,
        'headers': [
            [b'Content-Type', content_type]
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


def gen_thumbnail_response(thumbnail, etag, last_modified):
    response_start = gen_response_start(200, THUMBNAIL_CONTENT_TYPE)
    response_body = gen_response_body(thumbnail)

    # cache
    if thumbnail:
        response_start['headers'].append([b'Cache-Control', b'max-age=604800, public'])
        response_start['headers'].append([b'ETag', etag.encode('utf-8')])
        response_start['headers'].append([b'Last-Modified', last_modified.encode('utf-8')])

    return response_start, response_body


def thumbnail_path_exits(thumbnail_path):
    while True:
        if os.path.exists(thumbnail_path):
            return thumbnail_path


async def create_thumbnail_response(request, repo_id, file_path, size, etag, last_modified, thumbnail_path):
    content_type = 'application/json; charset=utf-8'
    result = {}
    await thumbnail_path_exits(thumbnail_path)
    response_start = gen_response_start(200, content_type)
    response_start['headers'].append([b'Cache-Control', b'max-age=604800, public'])
    response_start['headers'].append([b'ETag', etag.encode('utf-8')])
    response_start['headers'].append([b'Last-Modified', last_modified.encode('utf-8')])

    if re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/create/$', request.url):
        src = get_thumbnail_src(repo_id, size, file_path)
    else:
        match = re.match('^thumbnail/(?P<token>[a-f0-9]+)/create/$', request.url)
        tm_token = match.group('token')
        req_path = request.query_dict['path'][0]
        src = get_share_link_thumbnail_src(tm_token, size, req_path)

    result['encoded_thumbnail_src'] = quote(src)
    result = json.dumps(result)
    result_b = str(result).encode('utf-8')
    response_body = gen_response_body(result_b)
    return response_start, response_body


def gen_cache_response():
    response_start = gen_response_start(304, THUMBNAIL_CONTENT_TYPE)
    response_body = gen_response_body(EMPTY_BYTES)

    return response_start, response_body
