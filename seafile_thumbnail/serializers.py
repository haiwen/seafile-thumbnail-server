import os
import re
from django.conf import settings as dj_settings
from django.contrib.sessions.backends.db import SessionStore
from email.utils import formatdate

from seafile_thumbnail import settings
from seafile_thumbnail.constants import IMAGE, VIDEO, XMIND, PDF
from seafile_thumbnail.seahub_db import SeahubDB
from seafile_thumbnail.utils import session_require, get_file_type_and_ext
from seafile_thumbnail.utils import get_real_path_by_fs_and_req_path
from seaserv import get_repo, get_file_id_by_path, seafile_api

dj_settings.configure(SECRET_KEY=settings.SEAHUB_WEB_SECRET_KEY)
session_store = SessionStore()


class ThumbnailSerializer(object):
    def __init__(self, request):
        self.db_cursor = SeahubDB()
        self.request = request
        self.check()
        self.gen_thumbnail_info()
        self.db_cursor.close_seahub_db()

    def check(self):
        self.params_check()
        self.session_check()
        self.resource_check()

    def gen_thumbnail_info(self):
        thumbnail_info = {}
        thumbnail_info.update(self.params)

        if re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/create/$', self.request.url) or \
        re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url):
            thumbnail_info.update(self.session_data)

        thumbnail_info.update(self.resource)
        self.thumbnail_info = thumbnail_info


    def resource_check(self):
        file_path = self.params['file_path']
        repo_id = self.params['repo_id']
        size = self.params['size']
        file_obj = seafile_api.get_dirent_by_path(repo_id, file_path)
        file_id = file_obj.obj_id
        thumbnail_dir = os.path.join(settings.THUMBNAIL_DIR, str(size))
        thumbnail_file = os.path.join(thumbnail_dir, file_id)
        if not os.path.exists(thumbnail_dir):
            os.makedirs(thumbnail_dir)
        last_modified_time = file_obj.mtime
        last_modified = formatdate(int(last_modified_time), usegmt=True)
        etag = '"' + file_id + '"'

        self.resource = {
            'file_id': file_id,
            'thumbnail_dir': thumbnail_dir,
            'thumbnail_path': thumbnail_file,
            'last_modified': last_modified,
            'etag': etag,
        }


    def get_enable_file_type(self):
        enable_file_type = [IMAGE]
        if settings.ENABLE_VIDEO_THUMBNAIL:
            enable_file_type.append(VIDEO)
        if settings.ENABLE_XMIND_THUMBNAIL:
            enable_file_type.append(XMIND)
        if settings.ENABLE_PDF_THUMBNAIL:
            enable_file_type.append(PDF)
        self.enable_file_type = enable_file_type

    def params_check(self):
        token = None
        if re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/create/$', self.request.url):
            match = re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/create/$', self.request.url)
            query_dict = self.request.query_dict
            path = query_dict['path'][0]
            size = query_dict['size'][0]
            repo_id = match.group('repo_id')

            if not size:
                size = settings.THUMBNAIL_DEFAULT_SIZE
            if not path:
                err_msg = "Invalid arguments."
                raise AssertionError(400, err_msg)

            file_name = os.path.basename(path)
            filetype, fileext = get_file_type_and_ext(file_name)
        elif re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url):
            match = re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url)
            repo_id = match.group('repo_id')
            size = match.group('size')
            path = match.group('path')

            if not path:
                err_msg = "Invalid arguments."
                raise AssertionError(400, err_msg)

            file_name = os.path.basename(path)
            filetype, fileext = get_file_type_and_ext(file_name)
        elif re.match('^thumbnail/(?P<token>[a-f0-9]+)/create/$', self.request.url):
            match = re.match('^thumbnail/(?P<token>[a-f0-9]+)/create/$', self.request.url)
            token = match.group('token')
            req_path = self.request.query_dict['path'][0]
            size = self.request.query_dict['size'][0]

            if not size:
                size = settings.THUMBNAIL_DEFAULT_SIZE
            if not req_path or '../' in req_path:
                err_msg = "Invalid arguments."
                raise AssertionError(400, err_msg)

            repo_id, path, stype = self.db_cursor.get_valid_file_link_by_token(token)
            path = get_real_path_by_fs_and_req_path(stype, path, req_path)
            file_name = os.path.basename(path)
            filetype, fileext = get_file_type_and_ext(file_name)
        elif re.match('^thumbnail/(?P<token>[a-f0-9]+)/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url):
            match = re.match('^thumbnail/(?P<token>[a-f0-9]+)/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url)
            token = match.group('token')
            size = match.group('size')
            req_path = match.group('path')

            if not req_path or '../' in req_path:
                err_msg = "Invalid arguments."
                raise AssertionError(400, err_msg)

            repo_id, path, stype = self.db_cursor.get_valid_file_link_by_token(token)
            path = get_real_path_by_fs_and_req_path(stype, path, req_path)
            file_name = os.path.basename(path)
            filetype, fileext = get_file_type_and_ext(file_name)

        repo = get_repo(repo_id)
        if not repo:
            err_msg = "Library does not exist."
            raise AssertionError(400, err_msg)
        if repo.encrypted:
            err_msg = "Permission denied."
            raise AssertionError(403, err_msg)
        self.get_enable_file_type()
        if filetype not in self.enable_file_type:
            raise AssertionError(400, 'file_type invalid.')

        self.params = {
            'repo_id': repo_id,
            'file_name': file_name,
            'size': size,
            'file_ext': fileext,
            'file_type': filetype,
            'token': token,
            'file_path': path,
        }

    def parse_django_session(self, session_data):
        # django/contrib/sessions/backends/base.py
        return session_store.decode(session_data)

    @session_require
    def session_check(self):
        session_key = self.request.cookies[settings.SESSION_KEY]
        django_session = self.db_cursor.get_django_session_by_session_key(session_key)
        self.session_data = self.parse_django_session(django_session['session_data'])
        self.session_data['session_key'] = session_key
        username = self.session_data.get('_auth_user_name')
        if username:
            self.session_data['username'] = username

        if not username:
            raise AssertionError(400, 'django session invalid.')

