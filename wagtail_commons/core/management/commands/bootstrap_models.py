import logging
import re
import glob
import codecs
import os
from io import StringIO
from optparse import make_option
from collections import ChainMap

import yaml, yaml.parser
import markdown

from django.db.models.fields.related import RelatedField
from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.template import Template, Context, add_to_builtins
#from django.template import add_to_builtins
from django.conf import settings
from django.db.models.loading import get_model

from wagtail.wagtailcore.models import Site
from wagtail.wagtailcore.models import Page
from wagtail.wagtailimages.models import get_image_model

try:
    from wagtail.wagtailimages.models import get_upload_to
except ImportError:
    def get_upload_to(instance, path):
        return instance.get_upload_to(path)

from . import utils

__author__ = 'brett@codigious.com'

add_to_builtins("wagtail_commons.core.templatetags.bootstrap_wagtail_tags")
logger = logging.getLogger('wagtail_commons.core')


class ModelBuilder(object):

    def __init__(self, content_type, model_attrs, model_meta_attrs):
        app_label, model_name = content_type.split('.')
        self.app_label = app_label
        self.model_name = model_name
        self.model_meta_attrs =model_meta_attrs
        self.model_class = get_model(app_label, model_name)
        self.model_attrs = model_attrs
        self.instance = None

        try:
            self.natural_key = self.model_meta_attrs['natural_key']
        except KeyError:
            self.natural_key = None


    def get_instance_for_natural_key(self, attrs):
        if self.natural_key:
            try:
                return self.model_class.objects.get_by_natural_key(attrs[self.natural_key])
            except self.model_class.DoesNotExist:
                pass

        return self.model_class()

    def instantiate(self):
        logger.info("Creating %s", self.model_class)

        for attrs in self.model_attrs:
            self.instantiate_object(attrs)

    def interpolate(self, field_name, attrs):

        def identity(val):
            return val

        def this(val):
            return self.instance

        def path(val):
            return utils.page_for_path(val).specific

        mapping = {'$identity': identity,
                   '$self': this,
                   '$path': path}

        transformation = attrs.get(field_name, '$identity')
        function = mapping[transformation]

        return function


    def instantiate_related_objects(self, related_model, related_objects, meta_attrs):

        new_objects = []
        for obj_attrs in related_objects:
            new_obj = related_model()

            input_attrs = ChainMap(obj_attrs, meta_attrs)
            for field_name, field_value in input_attrs.items():
                f = self.interpolate(field_name, meta_attrs)
                setattr(new_obj, field_name, f(field_value))

            new_objects.append(new_obj)

        return new_objects


    def instantiate_object(self, attrs):
        instance = self.get_instance_for_natural_key(attrs)
        self.instance = instance

        deferred_objects = []

        for field_name, field_value in attrs.items():
            (field_object, model, direct, m2m) = instance._meta.get_field_by_name(field_name)

            if direct:
                if isinstance(field_object, models.ForeignKey):
                    f = utils.transformation_for_foreign_key(field_object)
                    related_value = f(field_value)
                    setattr(instance, field_name, related_value)
                    #raise Exception("Foreign Keys on models are unsupported, field {} = {}, type: {}".format(field_name, field_value, field_object))
                else:
                    setattr(instance, field_name, field_value)

        self.instance.save()

        for field_name, field_value in attrs.items():
            (field_object, model, direct, m2m) = instance._meta.get_field_by_name(field_name)

            if not direct:
                related_model = field_object.model
                model_meta_attrs = self.model_meta_attrs.get(field_name, {})
                related_objects = self.instantiate_related_objects(related_model, field_value, model_meta_attrs)
                #setattr(instance, field_name, related_objects)
                deferred_objects.append((field_name, related_objects))

        for field_name, related_objects in deferred_objects:
           for related_object in related_objects:
               related_object.save()


def load_attributes_from_file(path):
    f = codecs.open(path, encoding='utf-8')
    stream = yaml.load_all(f)
    meta_attrs = next(stream)

    try:
        attrs = next(stream)
    except StopIteration:
        attrs = meta_attrs
        meta_attrs = {}

    stream.close()
    f.close()

    return attrs, meta_attrs


def load_content(content_directory_path):

    content_directory_path = os.path.abspath(content_directory_path)
    contents_paths = sorted(glob.glob("{0}/*.yml".format(content_directory_path)))

    p = re.compile(r'(?:\d+\s+)?(.*)')  # used to strip numbers from start of file, e.g., 001 sample.yml -> sample.yml
    contents = []

    for path in contents_paths:
        content_type = os.path.basename(path)[:-4]

        content_attributes, meta_attrs = load_attributes_from_file(path)
        contents.append(ModelBuilder(content_type, model_attrs=content_attributes, model_meta_attrs=meta_attrs))


    return contents


class Command(BaseCommand):
    args = '<content directory>'
    help = 'Creates models from markdown and yaml files, found in <content directory>/models'

    option_list = BaseCommand.option_list + (
        make_option('--content', dest='content_path', type='string', ),
    )

    def handle(self, *args, **options):

        if not options['content_path']:
            content_path = settings.BOOTSTRAP_CONTENT_DIR
        else:
            content_path = options['content_path']

        contents = load_content(os.path.join(content_path, 'models'))

        for builder in contents:
            builder.instantiate()


