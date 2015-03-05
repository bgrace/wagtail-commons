import logging
from collections import Counter
from django.conf import settings
from django.core.files import File
from wagtail.wagtailimages.models import get_image_model

try:
    from wagtail.wagtailimages.models import get_upload_to
except ImportError:
    def get_upload_to(instance, path):
        return instance.get_upload_to(path)

__author__ = 'brett@codigious.com'

import filecmp
import os

from optparse import make_option
from django.contrib.auth.models import User

from django.core.management.base import BaseCommand, CommandError

# <embed alt="urn" embedtype="image" format="right" id="1"/>

logger = logging.getLogger(__name__)

class DocumentImporter(object):

    ImageModel = get_image_model()
    image_instance = ImageModel()

    def __init__(self, path, owner, stdout, stderr):
        # TODO remove dependency on stdout/stderr (this is invoked by other management scripts...)

        self.library_path = path
        self.owner = owner
        self.stdout = stdout
        self.stderr = stderr
        self.results = Counter({'total': 0,
                                'unchanged': 0,
                                'altered': 0,
                                'inserted': 0,
                                'ignored': 0})

    def increment_stat(self, stat):
        self.results.update({stat: 1})

    def import_images(self):
        self.add_images_to_library(self.library_path)

    def add_file(self, path):
        basename = os.path.basename(path)

        image = self.ImageModel(uploaded_by_user=self.owner)

        try:
            with open(path, 'rb') as image_file:
                image.file.save(basename, File(image_file), save=True)

            image.title = basename
            image.save()
            return image
        except TypeError:
            logger.fatal("Not an image? %s", path)
            return None

    def update_file(self, path):
        basename = os.path.basename(path)
        image = self.get_image_record(path)
        os.remove(image.file.path)
        with open(path, 'rb') as image_file:
            image.file.save(basename, File(image_file), save=True)
        image.save()
        return image

    def is_duplicate_name(self, path):
        file_name = get_upload_to(self.image_instance, os.path.basename(path))
        image_query = self.ImageModel.objects.filter(file=file_name)
        return image_query.exists()

    def get_image_record(self, path):
        file_name = get_upload_to(self.image_instance, os.path.basename(path))
        image = self.ImageModel.objects.get(file=file_name)
        return image

    def is_duplicate_image(self, path):
        image = self.get_image_record(path)
        return filecmp.cmp(image.file.path, path)

    def add_images_to_library(self, path):

        for path in [os.path.join(path, p) for p in os.listdir(path)]:
            if os.path.isdir(path):
                self.add_images_to_library(path)
            elif os.path.isfile(path):
                self.increment_stat('total')
                if self.is_duplicate_name(path):
                    if self.is_duplicate_image(path):
                        #self.stdout.write("Unchanged: {0} (skipped)".format(path))
                        self.increment_stat('unchanged')
                    else:
                        image = self.update_file(path)
                        self.stdout.write("Updated: {0} (updating image, retaining id {1})".format(path, image.id))
                        self.increment_stat('altered')
                else:
                    self.stdout.write("Adding new image {0}".format(path))
                    if self.add_file(path):
                        self.increment_stat('inserted')
                    else:
                        self.increment_stat('ignored')

    def get_results(self):
        return self.results



class Command(BaseCommand):
    args = '<content directory>'
    help = 'Imports files found in <content directory>/document-library into the Wagtail Document Library'

    option_list = BaseCommand.option_list + (
        make_option('--content', dest='content_path', type='string', ),
        make_option('--owner', dest='owner', type='string'),
    )

    def handle(self, *args, **options):

        if options['content_path']:
            path = options['content_path']
        elif settings.BOOTSTRAP_CONTENT_DIR:
            path = settings.BOOTSTRAP_CONTENT_DIR
        else:
            raise CommandError("Pass --content <content dir>, where <content dir>/pages contain .yml files")


        if not options['owner']:
            owner = None
        else:
            try:
                owner = User.objects.get(username=options['owner'])
            except User.DoesNotExist:
                raise CommandError("Owner with username '{0}' does not exist".format(options['owner']))

        if not os.path.isdir(path):
            raise CommandError("Content dir '{0}' does not exist or is not a directory".format(path))

        content_path = os.path.join(path, 'image-library')
        if not os.path.isdir(content_path):
            raise CommandError("Could not find image library '{0}'".format(content_path))

        importer = DocumentImporter(path=content_path, owner=owner, stdout=self.stdout, stderr=self.stderr)
        importer.import_documents()
        results = importer.get_results()
        print("Total: {0}, unchanged: {1}, replaced: {2}, new: {3}, ignored: {4}".format(results['total'],
                                                                                         results['unchanged'],
                                                                                         results['altered'],
                                                                                         results['inserted'],
                                                                                         results['ignored']))



