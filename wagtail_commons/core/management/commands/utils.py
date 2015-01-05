__author__ = 'brett@codigious.com'

import logging, os
from django.http import Http404

from wagtail.wagtailcore.models import Site, Page
import wagtail.wagtailimages.models
from wagtail.wagtailimages.models import get_image_model

try:
    from wagtail.wagtailimages.models import get_upload_to
except ImportError:
    def get_upload_to(instance, path):
        return instance.get_upload_to(path)

logger = logging.getLogger('wagtail_commons.core')


class BootstrapError(Exception):
    pass


def page_for_path(path, site=None):
    if not site:
        site = Site.objects.get(is_default_site=True)

    path_components = path.strip('/').split('/')

    try:
        response = site.root_page.route(None, path_components=path_components).page
    except Http404:
        logger.critical("Could not route {} for site {}".format(path, site))
        return None

    return response


def identity(val):
    return val


def image_for_name(val):
    val = os.path.basename(val)
    ImageModel = get_image_model()
    instance = ImageModel()

    file_name = get_upload_to(instance, val)
    image_query = ImageModel.objects.filter(file=file_name)
    if image_query.exists():
        return image_query.get()
    else:
        logger.fatal("Could not find image %s", val)
        raise BootstrapError
    return None


def model_by_natural_key(model_class):

    def f(val):
        return model_class.get_by_natural_key(val)

    return f


def document_for_name(val):
    return Document.objects.get(file=os.path.join('documents', val))


def to_markdown(val):
    return markdown.markdown(val)


def transformation_for_name(name):

    if name is None:
        return identity
    elif '$page' == name:
        return identity
    elif '$path' == name:
        return page_for_path
    elif '$image' == name:
        return image_for_name
    elif '$document' == name:
        return document_for_name
    elif 'markdown' == name:
        return to_markdown
    else:
        logger.critical("No transformation %s", name)

def transformation_for_foreign_key(field_object):

    related_model = field_object.rel.to

    if related_model == wagtail.wagtailimages.models.Image:
        return image_for_name
    else:
        return model_by_natural_key(related_model)

