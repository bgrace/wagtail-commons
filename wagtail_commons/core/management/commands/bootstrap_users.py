from django.conf import settings

__author__ = 'brett@codigious.com'

import codecs
import os
from optparse import make_option

import yaml
import yaml.parser
from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    args = '<content directory>'
    help = 'Create users, found in <content directory>/users.yml'

    option_list = BaseCommand.option_list + (
        make_option('--content', dest='content_path', type='string', ),
    )

    def handle(self, *args, **options):

        if options['content_path']:
            path = options['content_path']
        elif settings.BOOTSTRAP_CONTENT_DIR:
            path = settings.BOOTSTRAP_CONTENT_DIR
        else:
            raise CommandError("Pass --content <content dir>, where <content dir>/pages contain .yml files")

        if not os.path.isdir(path):
            raise CommandError("Content dir '{0}' does not exist or is not a directory".format(path))

        content_path = os.path.join(path, 'users.yml')
        if not os.path.isfile(content_path):
            raise CommandError("Could not find file '{0}'".format(content_path))

        f = codecs.open(content_path, encoding='utf-8')
        stream = yaml.load_all(f)
        users = next(stream)
        f.close()

        for user in users:
            try:
                u = User.objects.create(username=user['username'],
                                        email=user['email'],
                                        first_name=user['first_name'],
                                        last_name=user['last_name'],
                                        is_superuser=user['is_superuser'],
                                        is_staff=user['is_staff'])
                u.set_password(user['password'])
                u.save()
                self.stdout.write("Created {0}".format(user['username']))
            except IntegrityError:
                self.stderr.write("Could not create {0}, already exists?".format(user['username']))