import os
import re
import urllib.parse
import posixpath
from seafile_thumbnail.constants import TEXT, IMAGE, DOCUMENT, SPREADSHEET, SVG, PDF, MARKDOWN, VIDEO, \
    AUDIO, XMIND, SEADOC, TEXT_PREVIEW_EXT

from seaserv import seafile_api

from seafile_thumbnail import settings

PREVIEW_FILEEXT = {
    IMAGE: ('gif', 'jpeg', 'jpg', 'png', 'ico', 'bmp', 'tif', 'tiff', 'psd', 'webp', 'jfif', 'heic'),
    DOCUMENT: ('doc', 'docx', 'docxf', 'oform', 'ppt', 'pptx', 'odt', 'fodt', 'odp', 'fodp', 'odg'),
    SPREADSHEET: ('xls', 'xlsx', 'ods', 'fods'),
    SVG: ('svg',),
    PDF: ('pdf', 'ai'),
    MARKDOWN: ('markdown', 'md'),
    VIDEO: ('mp4', 'ogv', 'webm', 'mov'),
    AUDIO: ('mp3', 'oga', 'ogg', 'wav', 'flac', 'opus'),
    XMIND: ('xmind',),
    SEADOC: ('sdoc',),
}
def gen_fileext_type_map():
    """
    Generate previewed file extension and file type relation map.
    """
    d = {}
    for filetype in list(PREVIEW_FILEEXT.keys()):
        for fileext in PREVIEW_FILEEXT.get(filetype):
            d[fileext] = filetype

    return d
FILEEXT_TYPE_MAP = gen_fileext_type_map()

def get_conf_text_ext():
    """
    Get the conf of text ext in constance settings, and remove space.
    """
    text_ext = TEXT_PREVIEW_EXT
    return [x.strip() for x in text_ext]


def get_file_type_and_ext(filename):
    """
    Return file type and extension if the file can be previewd online,
    otherwise, return unknown type.
    """
    fileExt = os.path.splitext(filename)[1][1:].lower()
    if fileExt in get_conf_text_ext():
        return (TEXT, fileExt)

    filetype = FILEEXT_TYPE_MAP.get(fileExt)
    if filetype:
        return (filetype, fileExt)
    else:
        return ('Unknown', fileExt)


def get_inner_path(repo_id, file_id, file_name, file_type=None):
    if file_type == IMAGE:
        token = seafile_api.get_fileserver_access_token(
        repo_id, file_id, 'view', '', use_onetime=True)
    else:
        token = seafile_api.get_fileserver_access_token(
            repo_id, file_id, 'view', '', use_onetime=False)
    if not token:
        raise ValueError(404, 'token not found.')
    inner_path = '%s/files/%s/%s' % (
        settings.INNER_FILE_SERVER_ROOT.rstrip('/'), token, urllib.parse.quote(file_name))

    return inner_path


def get_share_link_thumbnail_src(token, size, path):
    return posixpath.join("thumbnail", token, str(size), path.lstrip('/'))


def get_real_path_by_fs_and_req_path(s_type, fileshare_path, req_path):
    """ Return the real path of a file.

    The file could be a file in a shared dir or a shared file.
    """

    if s_type == 'd':
        if fileshare_path == '/':
            real_path = req_path
        else:
            real_path = posixpath.join(fileshare_path, req_path.lstrip('/'))
    else:
        real_path = fileshare_path

    return real_path

def session_require(func):
    def wrapper(self, *args, **kwargs):
        if re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/create/$', self.request.url) or \
                re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url):
            result = func(self, *args, **kwargs)
            return result
    return wrapper


def cache_check(request, info):
    etag = info.get('etag')
    if_none_match_headers = request.headers.get('if-none-match')
    if_none_match = if_none_match_headers[0] if if_none_match_headers else ''

    last_modified = info.get('last_modified')
    if_modified_since_headers = request.headers.get('if-modified-since')
    if_modified_since = if_modified_since_headers[0] if if_modified_since_headers else ''
    if (if_none_match and if_none_match == etag) \
            or (if_modified_since and if_modified_since == last_modified):
        return True
    else:
        return False


def get_thumbnail_src(repo_id, size, path):
    return posixpath.join("thumbnail", repo_id, str(size), path.lstrip('/'))