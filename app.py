import re
import logging
from seafile_thumbnail.http_request import HTTPRequest
from seafile_thumbnail.http_response import gen_error_response, gen_text_response, thumbnail_get, \
    share_link_thumbnail_create, gen_thumbnail_response, share_link_thumbnail_get, gen_cache_response
from seafile_thumbnail.serializers import ThumbnailSerializer
from seafile_thumbnail.utils import cache_check

logger = logging.getLogger(__name__)


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

        # serialize check
        try:
            serializer = ThumbnailSerializer(request)
            thumbnail_info = serializer.thumbnail_info
        except AssertionError as e:
            status_code, msg = e.args
            response_stat, response_body = gen_error_response(
                status_code, msg
            )
            await send(response_stat)
            await send(response_body)
            return
        except Exception as e:
            logger.warning(e)
            thumbnail_info = None

        # ========= router=======
        # ------ping
        if request.url in ('ping', 'ping/'):
            response_stat, response_body = gen_text_response('pong')
            await send(response_stat)
            await send(response_body)
            return
        # ------thumbnail
        elif re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/create/$', request.url):
            # cache
            try:
                if cache_check(request, thumbnail_info):
                    response_start, response_body = gen_cache_response()
                    await send(response_start)
                    await send(response_body)
                    return
            except Exception as e:
                logger.exception(e)
            response_start, response_body = await gen_thumbnail_response(
                request, thumbnail_info)
            await send(response_start)
            await send(response_body)
            return
        elif re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/(?P<size>[0-9]+)/(?P<path>.*)$', request.url):
            # cache
            try:
                if cache_check(request, thumbnail_info):
                    response_start, response_body = gen_cache_response()
                    await send(response_start)
                    await send(response_body)
                    return
            except Exception as e:
                logger.exception(e)
            response_start, response_body = await thumbnail_get(request, thumbnail_info)
            await send(response_start)
            await send(response_body)
            return
        elif re.match('^thumbnail/(?P<token>[a-f0-9]+)/create/$', request.url):
            # cache
            try:
                if cache_check(request, thumbnail_info):
                    response_start, response_body = gen_cache_response()
                    await send(response_start)
                    await send(response_body)
                    return
            except Exception as e:
                logger.exception(e)
            response_start, response_body = await share_link_thumbnail_create(request, thumbnail_info)
            await send(response_start)
            await send(response_body)
            return
        elif re.match('^thumbnail/(?P<token>[a-f0-9]+)/(?P<size>[0-9]+)/(?P<path>.*)$', request.url):
            # cache
            try:
                if cache_check(request, thumbnail_info):
                    response_start, response_body = gen_cache_response()
                    await send(response_start)
                    await send(response_body)
                    return
            except Exception as e:
                logger.exception(e)
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
