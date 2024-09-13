import re
from seafile_thumbnail.http_request import HTTPRequest
from seafile_thumbnail.http_response import gen_error_response, gen_text_response, thumbnail_get, \
    share_link_thumbnail_create, gen_thumbnail_response, share_link_thumbnail_get
from seafile_thumbnail.serializers import ThumbnailSerializer


class App:
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
        elif re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/create/$', request.url):
            serializer = ThumbnailSerializer(request)
            thumbnail_info = serializer.thumbnail_info
            response_start, response_body = await gen_thumbnail_response(
                request, thumbnail_info)
            await send(response_start)
            await send(response_body)
            return
        elif re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/(?P<size>[0-9]+)/(?P<path>.*)$', request.url):
            serializer = ThumbnailSerializer(request)
            thumbnail_info = serializer.thumbnail_info
            response_start, response_body = await thumbnail_get(request, thumbnail_info)
            await send(response_start)
            await send(response_body)
            return
        elif re.match('^thumbnail/(?P<token>[a-f0-9]+)/create/$', request.url):
            serializer = ThumbnailSerializer(request)
            thumbnail_info = serializer.thumbnail_info
            response_start, response_body = await share_link_thumbnail_create(request, thumbnail_info)
            await send(response_start)
            await send(response_body)
            return
        elif re.match('^thumbnail/(?P<token>[a-f0-9]+)/(?P<size>[0-9]+)/(?P<path>.*)$', request.url):
            serializer = ThumbnailSerializer(request)
            thumbnail_info = serializer.thumbnail_info
            response_start, response_body = await share_link_thumbnail_get(request, thumbnail_info)
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
