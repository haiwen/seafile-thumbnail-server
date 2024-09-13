import json

import requests
import logging
import jwt
from seafile_thumbnail.settings import SEAHUB_SERVICE_URL, JWT_PRIVATE_KEY

logger = logging.getLogger(__name__)


def get_jwt_url(repo_id):
    jwt_url = '%s/api/v2.1/internal/repos/%s/check-thumbnail/' % (
        SEAHUB_SERVICE_URL.rstrip('/'), repo_id)
    return jwt_url




def jwt_permission_check(session_key, repo_id, path):
    jwt_url = get_jwt_url(repo_id)
    payload = {
        'is_internal': True
    }
    jwt_token = jwt.encode(payload, JWT_PRIVATE_KEY, algorithm='HS256')
    headers = {
        'Authorization': f'token {jwt_token}',
        'Cookie': "sessionid=%s" % session_key
    }
    try:
        response = requests.post(jwt_url, data={'path': path}, headers=headers)
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
        logger.error(e)
        return False
    
def jwt_share_link_permission_check(session_key, token):
    jwt_url = '%s/api/v2.1/internal/check-share-link-thumbnail/' % SEAHUB_SERVICE_URL.rstrip('/')
    
    payload = {
        'is_internal': True
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
            return False

        res = json.loads(response.text)
        if res["success"]:
            return True
        else:
            return False
    except Exception as e:
        logger.error(e)
        return False
