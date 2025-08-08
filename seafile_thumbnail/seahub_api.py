import time
import json
import requests
import logging
import jwt
from seafile_thumbnail.settings import INNER_SEAHUB_SERVICE_URL, JWT_PRIVATE_KEY

logger = logging.getLogger(__name__)


def get_jwt_url(repo_id):
    jwt_url = '%s/api/v2.1/internal/repos/%s/check-thumbnail/' % (
        INNER_SEAHUB_SERVICE_URL.rstrip('/'), repo_id)
    return jwt_url


def get_user_auth_url(repo_id):
    url = '%s/api/v2.1/internal/repos/%s/check-thumbnail/user-token/' % (
        INNER_SEAHUB_SERVICE_URL.rstrip('/'), repo_id)
    return url


def jwt_permission_check(session_key, repo_id, path, auth_token=None):
    url = get_jwt_url(repo_id)
    if auth_token:
        url = get_user_auth_url(repo_id)
        headers = {
            'Authorization': auth_token
        }
    else:
        payload = {
            'is_internal': True,
            'exp': int(time.time()) + 300
        }
        jwt_token = jwt.encode(payload, JWT_PRIVATE_KEY, algorithm='HS256')
        headers = {
            'Authorization': f'token {jwt_token}',
            'Cookie': "sessionid=%s" % session_key
        }
    try:
        response = requests.post(url, data={'path': path}, headers=headers)
        if response.status_code != 200:
            error_msg = 'Internal Server Error'
            logger.error(error_msg)
            return False

        res = json.loads(response.text)
        if res["success"]:
            return True
        else:
            return False
    except Exception as e:
        logger.error("Permission verification failed: %s" % e)
        return False


def jwt_share_link_permission_check(session_key, token):
    jwt_url = '%s/api/v2.1/internal/check-share-link-thumbnail/' % INNER_SEAHUB_SERVICE_URL.rstrip('/')
    
    payload = {
        'is_internal': True,
        'exp': int(time.time()) + 300
    }
    jwt_token = jwt.encode(payload, JWT_PRIVATE_KEY, algorithm='HS256')
    headers = {
        'Authorization': f'token {jwt_token}',
        'Cookie': "sessionid=%s" % session_key
    }
    try:
        response = requests.post(jwt_url, data={'token': token}, headers=headers)
        if response.status_code != 200:
            error_msg = 'Internal Server Error'
            logger.error(error_msg)
            return False, None, None, None

        res = json.loads(response.text)
        success = res['success']
        share_path = res['share_path']
        repo_id = res['repo_id']
        share_type = res['share_type']
        if success:
            return success, repo_id, share_path, share_type
        else:
            return False, None, None, None
    except Exception as e:
        logger.error("Permission verification failed: %s" % e)
        return False, None, None, None
