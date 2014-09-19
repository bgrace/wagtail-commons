import logging
from wagtail_commons.core.templatetags.fragment_tags import TextFragmentNode
import os

from django.template.loader import select_template
from django.utils.html import escape
from django.db import models

from wagtail.wagtailadmin.edit_handlers import FieldPanel
from wagtail.wagtailcore.fields import RichTextField
from wagtail.wagtailcore.models import Page
from wagtail.wagtailcore.rich_text import LINK_HANDLERS
from wagtail.wagtailcore.utils import camelcase_to_underscore

logger = logging.getLogger(__name__)


class ProtoPageLinkHandler(object):

    @staticmethod
    def get_db_attributes(tag):
        try:
            page_id = tag['data-id']
        except KeyError:
            url_path = '///' + tag['href'].strip('/') + '/'
            page = Page.objects.get(url_path=url_path)
            page_id = page.id

        return {'id': page_id}

    @staticmethod
    def expand_db_attributes(attrs, for_editor):

        try:
            try:
                page = Page.objects.get(url_path='///' + attrs['href'].strip() + '/')
            except KeyError:
                page = Page.objects.get(id=attrs['id'])

            if for_editor:
                editor_attrs = 'data-linktype="page" data-id="%d" ' % page.id
            else:
                editor_attrs = ''

            return '<a %shref="%s">' % (editor_attrs, escape(page.url))
        except Page.DoesNotExist:
            return "<a style='background: red; color: white'>Broken link: %s</a>" % attrs


LINK_HANDLERS['proto-page'] = ProtoPageLinkHandler

class TemplateIntrospectable(object):

    @property
    def template_fragments(self):
        try:
            return self._template_fragments
        except AttributeError:
            template = self.get_template(None)
            self._template_fragments = self.find_fragments(template.nodelist, [])
            return self._template_fragments

    def find_fragments(self, nodelist, text_fragment_nodes=None):

        if text_fragment_nodes is None:
            text_fragment_nodes = []

        for node in nodelist:
            if isinstance(node, TextFragmentNode):
                text_fragment_nodes.append(node)
            try:
                self.find_fragments(node.nodelist, text_fragment_nodes)
            except AttributeError:
                pass

        return text_fragment_nodes


class PathOverrideable(object):

    def get_template(self, request, mode='', **kwargs):
        try:
            return self._path_overrideable_template
        except AttributeError:

            path = self.url.strip('/')
            model_name = camelcase_to_underscore(self.specific_class.__name__)

            if mode:
                mode = ':'+mode

            model_template = model_name + mode + '.html'

            full_path = os.path.join('default', path+mode+'.html')
            templates = [full_path]
            logger.debug("Adding candidate template based on URL: %s", full_path)

            previous_index = len(path)
            while True:
                previous_index = path.rfind('/', 0, previous_index)
                if previous_index == -1:
                    break

                candidate = os.path.join('default', path[0:previous_index+1], model_template)
                templates.append(candidate)
                logger.debug("Adding candidate template for path-based model override: %s", candidate)

            #templates.append("%s/%s" % (self.specific_class._meta.app_label, model_name))
            templates.append(self.template)  # add the default template as the last one to seek

            logger.debug("Adding candidate template based on model name only: %s", self.template)
            selected_template = select_template(templates)
            logger.debug("Selected template: %s", selected_template.name)

            self._path_overrideable_template = selected_template
            return self._path_overrideable_template


class PageTextFragment(models.Model):

    name = models.CharField(max_length=255, editable=False)
    fragment = RichTextField()

    def __unicode__(self):
        return self.name

    panels = [
       # FieldPanel('name'),
        FieldPanel('fragment'),
        ]

    class Meta:
        abstract = True


class TextFragmented(object):
    pass

