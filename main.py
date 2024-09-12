import re
import os

from seafile_thumbnail.http_request import HTTPRequest
from seafile_thumbnail.http_response import gen_error_response, gen_text_response, gen_thumbnail_response, \
    gen_cache_response, create_thumbnail_response, get_thumbnail_response
from seafile_thumbnail.serializers import ThumbnailSerializer
from seafile_thumbnail.thumbnail import Thumbnail
from seafile_thumbnail.utils import cache_check
from seafile_thumbnail.task_queue import thumbnail_task_manager
import uvicorn


class App:
    def __init__(self):
        thumbnail_task_manager.run()

    async def __call__(self, scope, receive, send):
        # request
        request = HTTPRequest(**scope)
        if request.method != 'GET':
            response_stat, response_body = gen_error_response(
                405, 'Method %s not allowed' % request.method
            )
            await send(response_stat)
            await send(response_body)
            return

        # ========= router=======
        # ------ping
        if request.url in ('ping', 'ping/'):
            response_stat, response_body = gen_text_response('pong')
            await send(response_stat)
            await send(response_body)
            return
        # ------thumbnail
        elif re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/create/$', request.url) or \
                re.match('^thumbnail/(?P<token>[a-f0-9]+)/create/$', request.url):
            serializer = ThumbnailSerializer(request)
            thumbnail_info = serializer.thumbnail_info
            thumbnail = Thumbnail(**thumbnail_info)
            last_modified = thumbnail.last_modified
            etag = thumbnail.etag
            repo_id = thumbnail.repo_id
            file_path = thumbnail.file_path
            size = thumbnail.size
            thumbnail_path = thumbnail.thumbnail_path
            response_start, response_body = await create_thumbnail_response(request,
                                                                            repo_id, file_path, size, etag,
                                                                            last_modified, thumbnail_path)
            await send(response_start)
            await send(response_body)
            return
        elif re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/(?P<size>[0-9]+)/(?P<path>.*)$', request.url) or \
                re.match('^thumbnail/(?P<token>[a-f0-9]+)/(?P<size>[0-9]+)/(?P<path>.*)$', request.url):
            serializer = ThumbnailSerializer(request)
            thumbnail_info = serializer.thumbnail_info
            if not os.path.exists(thumbnail_info['thumbnail_path']):
                thumbnail = Thumbnail(**thumbnail_info)
                last_modified = thumbnail.last_modified
                etag = thumbnail.etag
                response_start, response_body = await gen_thumbnail_response(
                    thumbnail_info['thumbnail_path'], etag, last_modified)
                await send(response_start)
                await send(response_body)
                return
            with open(thumbnail_info['thumbnail_path'], 'rb') as f:
                thumbnail = f.read()
                last_modified = thumbnail_info['last_modified']
                etag = thumbnail_info['etag']
                response_start, response_body = get_thumbnail_response(
                    thumbnail, etag, last_modified)
                await send(response_start)
                await send(response_body)
                return
        else:
            response_stat, response_body = gen_error_response(
                404, 'Not Found'
            )
            await send(response_stat)
            await send(response_body)
            return


app = App()


def run():
    config = uvicorn.Config("main:app", port=8001)
    server = uvicorn.Server(config)
    server.run()


if __name__ == '__main__':
    run()
