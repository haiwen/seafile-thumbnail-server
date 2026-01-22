import os
import hashlib
import gc
import posixpath
import uuid
import jwt
import time
from seafile_thumbnail.settings import JWT_PRIVATE_KEY
from seafile_thumbnail.constants import TEXT, IMAGE, DOCUMENT, SPREADSHEET, SVG, PDF, MARKDOWN, VIDEO, \
    AUDIO, XMIND, SEADOC, TEXT_PREVIEW_EXT
from sqlalchemy import text
from seafobj import fs_mgr, commit_mgr
from seafile_thumbnail.db import init_db_session_class

PREVIEW_FILEEXT = {
    IMAGE: ('gif', 'jpeg', 'jpg', 'png', 'ico', 'bmp', 'tif', 'tiff', 'psd', 'webp', 'jfif', 'heic'),
    DOCUMENT: ('doc', 'docx', 'docxf', 'oform', 'ppt', 'pptx', 'odt', 'fodt', 'odp', 'fodp', 'odg'),
    SPREADSHEET: ('xls', 'xlsx', 'ods', 'fods'),
    SVG: ('svg',),
    PDF: ('pdf', 'ai'),
    MARKDOWN: ('markdown', 'md'),
    VIDEO: ('mp4', 'ogv', 'webm', 'mov', 'm4v'),
    AUDIO: ('mp3', 'oga', 'ogg', 'wav', 'flac', 'opus'),
    XMIND: ('xmind',),
    SEADOC: ('sdoc',),
}
ZERO_OBJ_ID = '0000000000000000000000000000000000000000'
LARGE_FILE_THRESHOLD = 1024 * 1024 * 1024 # 1GB, trigger garbage collection for large file.



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


def get_share_link_thumbnail_src(token, size, path):
    return posixpath.join("thumbnail", token, str(size), path.lstrip('/'))


def normalize_dir_path(path):
    """Add '/' at the end of directory path if necessary.

    And make sure path starts with '/'
    """

    path = path.strip('/')
    if path == '':
        return '/'
    else:
        return '/' + path + '/'

def normalize_file_path(path):
    """Remove '/' at the end of file path if necessary.

    And make sure path starts with '/'
    """

    path = path.strip('/')
    if path == '':
        return ''
    else:
        return '/' + path

def normalize_share_cache_key(token, sessionid):
    return token + '_' + sessionid


def get_file_content_by_obj_id(repo_id, obj_id):
    if obj_id == ZERO_OBJ_ID:
        return b''
    f = None
    try:
        f = fs_mgr.load_seafile(repo_id, 1, obj_id)
        b_content = f.get_content()
        if not b_content.strip():
            return b''
        return b_content
    except Exception as e:
        raise Exception('Failed to get file content by obj id: %s' % e)
    finally:
        # MEMORY FIX: Clear SeaFile object's cached content to prevent memory leak
        # The _content field caches the entire file content and is never released
        if f is not None:
            f._content = None
            f.blocks = None


def stream_file_to_path(repo_id, obj_id, dest_path, chunk_size=8*1024*1024):
    """Stream file content to a destination path without loading entire file into memory.
    
    This function reads the file in chunks and writes directly to disk, which is
    memory-efficient for large files like videos.
    
    Args:
        repo_id: Repository ID
        obj_id: File object ID  
        dest_path: Destination file path to write to
        chunk_size: Size of chunks to read at a time (default 8MB)
    
    Returns:
        Total bytes written
    """
    if obj_id == ZERO_OBJ_ID:
        raise Exception('Cannot stream empty file')
    
    total_written = 0
    try:
        f = fs_mgr.load_seafile(repo_id, 1, obj_id)
        stream = f.get_stream()
        
        with open(dest_path, 'wb') as dest_file:
            while True:
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                dest_file.write(chunk)
                total_written += len(chunk)
                del chunk
        if total_written > LARGE_FILE_THRESHOLD:
            gc.collect()

        return total_written
        return total_written
    except Exception as e:
        if os.path.exists(dest_path):
            os.unlink(dest_path)
        raise Exception('Failed to stream file content: %s' % e)


def uuid_str_to_36_chars(file_uuid):
    if len(file_uuid) == 32:
        return str(uuid.UUID(file_uuid))
    else:
        return file_uuid
    
    
def gen_thumbnail_access_token(file_uuid):
    access_token = jwt.encode({
        'file_uuid': file_uuid,
        'exp': int(time.time()) + 30000,
    },
        JWT_PRIVATE_KEY,
        algorithm='HS256'
    )
    return access_token


class SeafileAPI(object):
    def __init__(self, repo_id):
        self.repo_id = repo_id
        self.db_session_class = init_db_session_class('seafile')
        self.seahub_db_session_class = init_db_session_class()

    def get_repo_info(self):
        with self.db_session_class() as session:
            sql = text("""
                SELECT v.origin_repo as origin_repo_id, i.is_encrypted, v.path as path
                FROM Repo r 
                LEFT JOIN VirtualRepo v ON r.repo_id = v.repo_id
                LEFT JOIN RepoInfo i on r.repo_id = i.repo_id
                WHERE r.repo_id = :repo_id
            """)

            result = session.execute(sql, {"repo_id": self.repo_id}).first()
            if not result:
                return None
            repo = {
                'repo_id': self.repo_id,
                'origin_repo_id': result.origin_repo_id,
                'is_encrypted': result.is_encrypted,
                'path': result.path
            }
            return repo

    
    def _get_repo_head_commit(self):
        try:
            with self.db_session_class() as session:
                sql = text("""SELECT b.commit_id, r.type
                            from Branch as b inner join RepoInfo as r
                            where b.repo_id=r.repo_id and b.repo_id=:repo_id"""
                )
                res = session.execute(sql, {'repo_id': self.repo_id}).first()
                return res
        except Exception as e:
            raise e
    
    def get_dirent_by_path(self, repo, file_path):
        commit_id = self._get_repo_head_commit()[0]
        commit = commit_mgr.load_commit(self.repo_id, 0, commit_id)
        root_id = commit.root_id
        parent_path = os.path.dirname(file_path)
        origin_repo_id = repo.get('origin_repo_id')
        if origin_repo_id:
            dir = fs_mgr.get_seafdir_by_path(origin_repo_id, 1, root_id, parent_path)
        else:
            dir = fs_mgr.get_seafdir_by_path(self.repo_id, 1, root_id, parent_path)
        return dir.lookup_dent(os.path.basename(file_path))
    
    
    def get_file_id_by_path(self, repo, file_path):
        origin_repo_id = repo.get('origin_repo_id')
        commit_id = self._get_repo_head_commit()[0]
        commit = commit_mgr.load_commit(self.repo_id, 0, commit_id)
        root_id = commit.root_id
        if origin_repo_id:
            file_id = fs_mgr.get_file_id_by_path(origin_repo_id, 1, root_id, file_path)
        else:
            file_id = fs_mgr.get_file_id_by_path(self.repo_id, 1, root_id, file_path)

        return file_id

    def get_file_uuid_by_path(self, repo_id, file_path):
        file_name = os.path.basename(file_path)
        parent_path = os.path.dirname(file_path)
        parent_path = parent_path.rstrip('/') if parent_path != '/' else '/'
        md5_repo_id_parent_path = hashlib.md5((repo_id + parent_path).encode('utf-8')).hexdigest()
        with self.seahub_db_session_class() as seahub_db_session:
            sql = text("""
            SELECT uuid FROM tags_fileuuidmap
            WHERE repo_id_parent_path_md5=:repo_id_parent_path_md5
            AND filename=:filename
            """)

            result = seahub_db_session.execute(sql, {
                "repo_id_parent_path_md5": md5_repo_id_parent_path,
                "filename": file_name
            }).first()
            if not result:
                return None
            
            uuid = uuid_str_to_36_chars(result.uuid)
            return uuid
