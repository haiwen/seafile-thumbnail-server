import os
import configparser
import logging







def get_config(config_file):
    config = configparser.ConfigParser()
    try:
        config.read(config_file)
    except Exception as e:
        logger.critical("Failed to read config file %s: %s" % (config_file, e))
        raise RuntimeError("Failed to read config file %s: %s" % (config_file, e))

    return config


def get_seahub_db_name():
    seahub_conf_dir = os.environ.get('SEAFILE_CENTRAL_CONF_DIR') or os.environ.get('CCNET_CONF_DIR')
    if not seahub_conf_dir:
        error_msg = 'Environment variable seahub_conf_dir is not define.'
        return None, error_msg

    seahub_conf_path = os.path.join(seahub_conf_dir, 'seafevents.conf')
    config = configparser.ConfigParser()
    config.read(seahub_conf_path)

    if config.has_section('DATABASE'):
        db_name = config.get('DATABASE', 'name', fallback='seahub')
    else:
        db_name = 'seahub'

    if config.get('DATABASE', 'type') != 'mysql':
        error_msg = 'Failed to init seahub db, only mysql db supported.'
        return None, error_msg
    return db_name, None


class SeahubDB(object):
    def __init__(self):
        self.seahub_db_conn = None
        self.seahub_db_cursor = None
        self.init_seahub_db()
        self.db_name = get_seahub_db_name()[0]
        if self.seahub_db_cursor is None:
            raise RuntimeError('Failed to init seahub db.')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_seahub_db()

    def init_seahub_db(self):
        try:
            import pymysql
            pymysql.install_as_MySQLdb()
        except ImportError as e:
            logger.warning('Failed to init seahub db: %s.' % e)
            return

        seahub_conf_dir = os.environ.get('SEAFILE_CENTRAL_CONF_DIR') or os.environ.get('CCNET_CONF_DIR')
        if not seahub_conf_dir:
            logging.warning('Environment variable seahub_conf_dir is not define')
            return

        seahub_conf_path = os.path.join(seahub_conf_dir, 'seafevents.conf')
        seahub_config = get_config(seahub_conf_path)

        if not seahub_config.has_section('DATABASE'):
            logger.warning('Failed to init seahub db, can not find db info in seahub.conf.')
            return

        if seahub_config.get('DATABASE', 'type') != 'mysql':
            logger.warning('Failed to init seahub db, only mysql db supported.')
            return
        db_name = seahub_config.get('DATABASE', 'name', fallback='seahub')
        db_host = seahub_config.get('DATABASE', 'host', fallback='127.0.0.1')
        db_port = seahub_config.getint('DATABASE', 'port', fallback=3306)
        db_user = seahub_config.get('DATABASE', 'username')
        db_passwd = seahub_config.get('DATABASE', 'password')
        try:
            self.seahub_db_conn = pymysql.connect(host=db_host, port=db_port, user=db_user,
                                                 passwd=db_passwd, db=db_name, charset='utf8')
            self.seahub_db_conn.autocommit(True)
            self.seahub_db_cursor = self.seahub_db_conn.cursor()
        except Exception as e:
            self.cursor = None
            logger.warning('Failed to init seahub db: %s.' % e)
            return

    def close_seahub_db(self):
        if self.seahub_db_cursor:
            self.seahub_db_cursor.close()
        if self.seahub_db_conn:
            self.seahub_db_conn.close()

    def get_valid_file_link_by_token(self, token):
        sql = f"""
            SELECT repo_id, path, s_type, password
            FROM
                `{self.db_name}`.`share_fileshare`
            WHERE
                token = '{token}'
        """
        with self.seahub_db_cursor as cursor:
            cursor.execute(sql)
            data = cursor.fetchone()
            repo_id = data[0]
            path = data[1]
            s_type = data[2]

            return repo_id, path, s_type


    def session_info(self, data):
        info = {
            'session_key': data[0],
            'session_data': data[1],
            'expire_date': data[2]
        }
        return info

    def get_django_session_by_session_key(self, session_key):
        sql = f"""
        SELECT *
        FROM `{self.db_name}`.`django_session`
        WHERE session_key = '{session_key}'
        """
        with self.seahub_db_cursor as cursor:
            cursor.execute(sql)
            data = cursor.fetchone()
            return self.session_info(data)
