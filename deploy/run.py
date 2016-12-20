#!/usr/bin/env python

from __future__ import print_function

import jinja2
import os
import subprocess
import time

__metaclass__ = type

class InvalidProjectError(Exception):
    pass


NGINX_VARS = {
    'CA_CERT': os.environ.get('CA_CERT', ''),
    'CLIENT_MAX_BODY_SIZE': os.environ.get('CLIENT_MAX_BODY_SIZE', '10m'),
    'KEEPALIVE_TIMEOUT': os.environ.get('KEEPALIVE_TIMEOUT', '0'),
    'INCLUDE_SERVER_CONF': os.environ.get('INCLUDE_SERVER_CONF', None),
    'SERVER_NAME': os.environ.get('SERVER_NAME', ''),
    'SSL_BUNDLE': os.environ.get('SSL_BUNDLE', ''),
    'STATIC_URL': os.environ.get('STATIC_URL', '/static/'),
    'STATIC_ROOT': os.environ.get('STATIC_ROOT', '/static/'),
    'USE_HSTS': bool(os.environ.get('USE_HSTS', '1')),
}

SUPERVISOR_VARS = {
    'APP_MODULE': os.environ.get('APP_MODULE', 'proj.wsgi'),
    'GUNICORN_ARGS': os.environ.get('GUNICORN_ARGS', ''),
    'WWW_USER': os.environ.get('WWW_USER', 'www-data'),
}

GUNICORN_VARS = {
}

ENV = jinja2.Environment(
    autoescape=False,
    loader=jinja2.FileSystemLoader([
        '{}/docker/templates'.format(os.environ['APP_ROOT']),
         os.environ['TEMPLATE_DIR'],
    ]),
    undefined=jinja2.StrictUndefined,
)

def render_template(name, tpl_vars, outfile):
    template = ENV.get_template(name)
    with open(outfile, 'w') as fil:
        print(template.render(**tpl_vars), file=fil)

def render_templates():
    render_template(
        'nginx.conf.jinja',
        NGINX_VARS,
        '/etc/nginx.conf'
    )
    render_template(
        'supervisord.conf.jinja',
        SUPERVISOR_VARS,
        '/etc/supervisord.conf'
    )
    render_template(
        'gunicorn.conf.jinja',
        GUNICORN_VARS,
        '/etc/gunicorn.conf'
    )


class DjangoHook:
    def __init__(self):
        try:
            import django
        except ImportError:
            raise InvalidProjectError
        self.manage_path = os.path.join(os.environ['APP_ROOT'], 'manage.py')
        if not os.path.exists(self.manage_path):
            raise InvalidProjectError
        try:
            if 'django' not in subprocess.check_output(
                    self.manage_path).decode('utf-8', errors='ignore'):
                raise InvalidProjectError
        except subprocess.CalledProcessError:
            raise InvalidProjectError
        print('Detected a django project...')

    def add_clearsessions_cron_job(self):
        print('Adding clearsessions daily cron job.')
        path = '/etc/cron.daily/clearsessions'
        with open(path, 'w') as fil:
            print(
                "#!/bin/bash\n"
                "{} clearsessions >/dev/null 2>&1\n".format(self.manage_path),
                file=fil
            )
        os.chmod(path, 0o755)

    def collectstatic(self):
        print('Collecting static files.')
        subprocess.check_call([
            self.manage_path,
            'collectstatic',
            '-l',
            '--noinput'
        ])

    def migrate_db(self):
        has_db = bool(
            subprocess.check_output([
                self.manage_path,
                'shell',
                '-c',
                'from django.conf import settings; '
                'print(settings.DATABASES or "")'
            ]).strip()
        )
        if not has_db:
            return

        print('Waiting for database to be ready.')
        for _ in range(20):
            output = subprocess.check_output([
                self.manage_path,
                'shell',
                '-c',
                'from django.db.utils import OperationalError\n'
                'from django.db import connection\n'
                'try:\n'
                '    connection.cursor()\n'
                'except OperationalError:\n'
                '    print("Database not ready yet")'
            ])
            if not output:
                break
            else:
                time.sleep(1)
        else:
            raise RuntimeError('Database is not ready to accept connections.')

        print('Running migrations on database.')
        subprocess.check_call([self.manage_path, 'migrate'])

    def process(self):
        self.add_clearsessions_cron_job()
        self.migrate_db()
        self.collectstatic()

def main():
    render_templates()
    try:
        proj = DjangoHook()
    except InvalidProjectError:
        pass
    else:
        proj.process()

if __name__ == '__main__':
    main()