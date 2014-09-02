import logging
from wagtail_commons.core.management.commands.bootstrap_content import load_attributes_from_file, SiteNode, \
    get_relation_mappings
import os

from django.conf import settings
from wagtail.wagtailcore.models import Page, Site

__author__ = 'bgrace'

logger = logging.getLogger('wagtail_commons.core')


def live_preview(request):

    try:
        if u'/' == request.path:
            page = Site.find_for_request(request).root_page.specific
        else:
            logger.info("path: %s", '//'+request.path)
            page = Page.objects.get(url_path='//'+request.path).specific
    except Page.DoesNotExist:
        return {}

    content_file = os.path.join(settings.BOOTSTRAP_CONTENT_DIR, 'pages', request.path.strip('/') + '.yml')
    if not os.path.isfile(content_file):
        return {}

    content_attributes = load_attributes_from_file(content_file)

    try:
        del content_attributes['type']
    except KeyError:
        pass

    SiteNode.set_page_attributes(page, content_attributes,
                                 get_relation_mappings(os.path.join(settings.BOOTSTRAP_CONTENT_DIR, 'relations.yml')))

    return {'self': page}

