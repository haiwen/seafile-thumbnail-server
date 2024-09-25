import os
import re
from email.utils import formatdate

from seafile_thumbnail import settings
from seafile_thumbnail.constants import IMAGE, VIDEO, XMIND, PDF
from seafile_thumbnail.utils import get_file_type_and_ext
from seafile_thumbnail.utils import get_real_path_by_fs_and_req_path
from seafile_thumbnail.seahub_api import jwt_permission_check, jwt_share_link_permission_check
from seaserv import get_repo, seafile_api, get_file_size


class ThumbnailSerializer(object):
    def __init__(self, request):
        self.request = request
        self.check()
        self.gen_thumbnail_info()

    def check(self):
        self.params_check()
        self.session_check()
        self.resource_check()

    def gen_thumbnail_info(self):
        thumbnail_info = {}
        thumbnail_info.update(self.params)
        thumbnail_info.update(self.resource)
        self.thumbnail_info = thumbnail_info

    def resource_check(self):
        # get share real path
        if re.match('^thumbnail/(?P<token>[a-f0-9]+)/create/$', self.request.url) or \
        re.match('^thumbnail/(?P<token>[a-f0-9]+)/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url):
            path = get_real_path_by_fs_and_req_path(self.params['share_type'], self.params['share_path'], self.params['file_path'])
            self.params['file_path'] = path

        size = self.params['size']
        repo_id = self.params['repo_id']
        file_path = self.params['file_path']
        file_name = os.path.basename(file_path)
        filetype, fileext = get_file_type_and_ext(file_name)

        # resource check
        repo = get_repo(repo_id)
        if not repo:
            err_msg = "Library does not exist."
            raise AssertionError(400, err_msg)
        if repo.encrypted:
            err_msg = "Permission denied."
            raise AssertionError(403, err_msg)
        file_obj = seafile_api.get_dirent_by_path(repo_id, file_path)
        file_id = file_obj.obj_id
        file_size = get_file_size(repo.store_id, repo.version, file_id)
        self.get_enable_file_type()
        if filetype not in self.enable_file_type:
            raise AssertionError(400, 'file_type invalid.')

        thumbnail_dir = os.path.join(settings.THUMBNAIL_DIR, str(size))
        thumbnail_file = os.path.join(thumbnail_dir, file_id)
        if not os.path.exists(thumbnail_dir):
            os.makedirs(thumbnail_dir)
        file_obj = seafile_api.get_dirent_by_path(repo_id, file_path)
        last_modified_time = file_obj.mtime
        last_modified = formatdate(int(last_modified_time), usegmt=True)
        etag = '"' + file_id + '"'
        self.resource = {
            'file_size': file_size,
            'file_id': file_id,
            'file_ext': fileext,
            'file_type': filetype,
            'file_name': file_name,
            'thumbnail_dir': thumbnail_dir,
            'thumbnail_path': thumbnail_file,
            'last_modified': last_modified,
            'etag': etag
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
        repo_id = None
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
        elif re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url):
            match = re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url)
            repo_id = match.group('repo_id')
            size = match.group('size')
            path = match.group('path')

            if not path:
                err_msg = "Invalid arguments."
                raise AssertionError(400, err_msg)
        elif re.match('^thumbnail/(?P<token>[a-f0-9]+)/create/$', self.request.url):
            match = re.match('^thumbnail/(?P<token>[a-f0-9]+)/create/$', self.request.url)
            token = match.group('token')
            path = self.request.query_dict['path'][0]
            size = self.request.query_dict['size'][0]
            if not size:
                size = settings.THUMBNAIL_DEFAULT_SIZE
            if not path or '../' in path:
                err_msg = "Invalid arguments."
                raise AssertionError(400, err_msg)
        elif re.match('^thumbnail/(?P<token>[a-f0-9]+)/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url):
            match = re.match('^thumbnail/(?P<token>[a-f0-9]+)/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url)
            token = match.group('token')
            size = match.group('size')
            path = match.group('path')

            if not path or '../' in path:
                err_msg = "Invalid arguments."
                raise AssertionError(400, err_msg)

        self.params = {
            'repo_id': repo_id,
            'size': size,
            'token': token,
            'file_path': path,
        }

    def session_check(self):
        try:
            session_key = self.request.cookies[settings.SESSION_KEY]
        except:
            session_key = ''
        self.session_key = session_key

        if re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/create/$', self.request.url) or \
                re.match('^thumbnail/(?P<repo_id>[-0-9a-f]{36})/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url):
            self.permission_check()
        elif re.match('^thumbnail/(?P<token>[a-f0-9]+)/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url) or \
                re.match('^thumbnail/(?P<token>[a-f0-9]+)/create/$', self.request.url):
            self.jwt_share_permission_check()

    def permission_check(self):
        permission = jwt_permission_check(self.session_key, self.params['repo_id'], self.params['file_path'])
        if not permission:
            err_msg = "Permission denied."
            raise AssertionError(403, err_msg)

    def jwt_share_permission_check(self):
        success, repo_id, share_path, share_type = jwt_share_link_permission_check(self.session_key, self.params['token'])
        self.params['repo_id'] = repo_id
        self.params['share_path'] = share_path
        self.params['share_type'] = share_type
        if not success:
            err_msg = "Permission denied."
            raise AssertionError(403, err_msg)