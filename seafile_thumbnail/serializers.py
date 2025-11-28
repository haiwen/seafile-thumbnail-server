import hashlib
import os
import re
import logging
import posixpath
from email.utils import formatdate

from seafile_thumbnail import settings
from seafile_thumbnail.constants import IMAGE, VIDEO, XMIND, PDF, SVG, SEADOC
from seafile_thumbnail.utils import get_file_type_and_ext, normalize_dir_path, get_real_path_by_fs_and_req_path, \
    normalize_share_cache_key, normalize_file_path
from seafile_thumbnail.seahub_api import jwt_permission_check, jwt_share_link_permission_check
from seafile_thumbnail.cache import thumbnail_cache
from seafile_thumbnail.utils import SeafileAPI

logger = logging.getLogger(__name__)


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
        self.update_save_path()

    def resource_check(self):
        # get share real path
        file_path = self.params.get('file_path', '')
        if re.match('^/thumbnail/(?P<token>[a-f0-9]+)/create/$', self.request.url):
            path = get_real_path_by_fs_and_req_path(self.params['share_type'], self.params['share_path'], self.params['file_path'])
            self.params['share_create_file_path'] = path
            file_path = path
        if re.match('^/thumbnail/(?P<token>[a-f0-9]+)/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url):
            path = get_real_path_by_fs_and_req_path(self.params['share_type'], self.params['share_path'], self.params['file_path'])
            self.params['file_path'] = path
            file_path = path
        size = self.params['size']
        repo_id = self.params['repo_id']
        file_path = normalize_file_path(file_path)
        file_name = os.path.basename(file_path)
        filetype, fileext = get_file_type_and_ext(file_name)
        seafile_api = SeafileAPI(repo_id)
        repo = seafile_api.get_repo_info()
        if not repo:
            err_msg = "Library does not exist."
            raise AssertionError(400, err_msg)
        if repo.get('is_encrypted'):
            err_msg = "Permission denied."
            raise AssertionError(403, err_msg)

        file_id = seafile_api.get_file_id_by_path(repo, file_path)
        if not file_id:
            err_msg = "File does not exist."
            raise AssertionError(404, err_msg)

        origin_repo_id = repo.get('origin_repo_id')
        self.get_enable_file_type()
        if filetype not in self.enable_file_type:
            raise AssertionError(400, 'file_type invalid.')

        thumbnail_dir = os.path.join(settings.THUMBNAIL_ROOT, str(size))
        thumbnail_file = os.path.join(thumbnail_dir, file_id)
        if not os.path.exists(thumbnail_dir):
            os.makedirs(thumbnail_dir)

        file_obj = seafile_api.get_dirent_by_path(repo, file_path)
        file_size = file_obj.size
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
            'etag': etag,
            'origin_repo_id': origin_repo_id,
            'origin_parent_path': repo.get('path')
        }

    def get_enable_file_type(self):
        enable_file_type = [IMAGE, SVG, SEADOC]
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
        if re.match('^/thumbnail/(?P<repo_id>[-0-9a-f]{36})/create/$', self.request.url):
            match = re.match('^/thumbnail/(?P<repo_id>[-0-9a-f]{36})/create/$', self.request.url)
            query_dict = self.request.query_dict
            path = query_dict['path'][0] if 'path' in query_dict else None
            size = query_dict['size'][0] if 'size' in query_dict else None
            repo_id = match.group('repo_id')

            if not size:
                size = settings.THUMBNAIL_DEFAULT_SIZE
                
            if int(size) not in settings.THUMBNAIL_SIZE_LIMIT:
                err_msg = 'Thumbnail size is invalid, available sizes are %s' % ','.join(str(i) for i in settings.THUMBNAIL_SIZE_LIMIT)
                raise AssertionError(400, err_msg)

            if not path:
                err_msg = "Invalid arguments."
                raise AssertionError(400, err_msg)
        elif re.match('^/thumbnail/(?P<repo_id>[-0-9a-f]{36})/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url):
            match = re.match('^/thumbnail/(?P<repo_id>[-0-9a-f]{36})/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url)
            repo_id = match.group('repo_id')
            size = match.group('size')
            path = match.group('path')

            if int(size) not in settings.THUMBNAIL_SIZE_LIMIT:
                err_msg = 'Thumbnail size is invalid, available sizes are %s' % ','.join(str(i) for i in settings.THUMBNAIL_SIZE_LIMIT)
                raise AssertionError(400, err_msg)

            if not path:
                err_msg = "Invalid arguments."
                raise AssertionError(400, err_msg)
        elif re.match('^/thumbnail/(?P<token>[a-f0-9]+)/create/$', self.request.url):
            match = re.match('^/thumbnail/(?P<token>[a-f0-9]+)/create/$', self.request.url)
            token = match.group('token')
            query_dict = self.request.query_dict
            path = query_dict['path'][0] if 'path' in query_dict else None
            size = query_dict['size'][0] if 'size' in query_dict else None

            if not size:
                size = settings.THUMBNAIL_DEFAULT_SIZE
            
            if int(size) not in settings.THUMBNAIL_SIZE_LIMIT:
                err_msg = 'Thumbnail size is invalid, available sizes are %s' % ','.join(str(i) for i in settings.THUMBNAIL_SIZE_LIMIT)
                raise AssertionError(400, err_msg)

            if not path or '../' in path:
                err_msg = "Invalid arguments."
                raise AssertionError(400, err_msg)
        elif re.match('^/thumbnail/(?P<token>[a-f0-9]+)/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url):
            match = re.match('^/thumbnail/(?P<token>[a-f0-9]+)/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url)
            token = match.group('token')
            size = match.group('size')
            path = match.group('path')

            if int(size) not in settings.THUMBNAIL_SIZE_LIMIT:
                err_msg = 'Thumbnail size is invalid, available sizes are %s' % ','.join(str(i) for i in settings.THUMBNAIL_SIZE_LIMIT)
                raise AssertionError(400, err_msg)
            
            if not path or '../' in path:
                err_msg = "Invalid arguments."
                raise AssertionError(400, err_msg)
        else:
            err_msg = 'Page not found.'
            raise AssertionError(404, err_msg)

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

        if re.match('^/thumbnail/(?P<repo_id>[-0-9a-f]{36})/create/$', self.request.url) or \
                re.match('^/thumbnail/(?P<repo_id>[-0-9a-f]{36})/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url):
            self.permission_check()
        elif re.match('^/thumbnail/(?P<token>[a-f0-9]+)/(?P<size>[0-9]+)/(?P<path>.*)$', self.request.url) or \
                re.match('^/thumbnail/(?P<token>[a-f0-9]+)/create/$', self.request.url):
            self.jwt_share_permission_check()

    def permission_check(self):
        dir_path = normalize_dir_path(os.path.dirname(self.params['file_path']))
        auth_token_list = self.request.headers.get('authorization')
        auth_token = auth_token_list[0] if auth_token_list else None
        if auth_token:
            perm_key_md5 = hashlib.md5((self.params['repo_id'] + dir_path + auth_token).encode('utf-8')).hexdigest()
        else:
            perm_key_md5 = hashlib.md5((self.params['repo_id'] + dir_path + self.session_key).encode('utf-8')).hexdigest()
        perm_cache = thumbnail_cache.get(perm_key_md5)
        if perm_cache:
            return
        permission = jwt_permission_check(self.session_key, self.params['repo_id'], self.params['file_path'], auth_token)
        if not permission:
            err_msg = "Permission denied."
            raise AssertionError(403, err_msg)
        thumbnail_cache.set(perm_key_md5, permission)

    def jwt_share_permission_check(self):
        token = self.params['token']
        sessionid = self.session_key
        perm_key = normalize_share_cache_key(token, sessionid)
        perm_cache = thumbnail_cache.get(perm_key)
        if perm_cache:
            self.params['repo_id'] = perm_cache[0]
            self.params['share_path'] = perm_cache[1]
            self.params['share_type'] = perm_cache[2]
            return
        success, repo_id, share_path, share_type = jwt_share_link_permission_check(self.session_key, self.params['token'])
        if not success:
            err_msg = "Permission denied."
            raise AssertionError(403, err_msg)
        share_cache_value = (repo_id, share_path, share_type)
        self.params['repo_id'] = repo_id
        self.params['share_path'] = share_path
        self.params['share_type'] = share_type
        thumbnail_cache.set(perm_key, share_cache_value)
        
        
    def update_save_path(self):
        thumbnail_info = self.thumbnail_info
        filetype = thumbnail_info.get('file_type')
        if filetype not in [SEADOC, ]:
            return
        file_path = thumbnail_info.get('file_path')
        file_path = normalize_file_path(file_path)
        origin_repo_id = thumbnail_info.get('origin_repo_id')
        origin_parent_path = thumbnail_info.get('origin_parent_path')
        repo_id = thumbnail_info.get('repo_id')
        if origin_repo_id:
            repo_id = origin_repo_id
            file_path = posixpath.join(origin_parent_path, file_path.lstrip('/'))

        old_thumbnail_dir = thumbnail_info.get('thumbnail_dir')
        file_id = thumbnail_info.get('file_id')
        
        
        seafile_api = SeafileAPI(repo_id)
        file_uuid = seafile_api.get_file_uuid_by_path(repo_id, file_path)
        if not file_uuid:
            return
        thumbnail_dir = os.path.join(old_thumbnail_dir, file_uuid)
        if not os.path.exists(thumbnail_dir):
            os.makedirs(thumbnail_dir)
            
        thumbnail_file = os.path.join(thumbnail_dir, file_id)
        self.thumbnail_info.update({
            'thumbnail_path': thumbnail_file
        })
