import logging
import os

from django.template.loader import select_template

from wagtail.wagtailcore.models import Page, Orderable
from wagtail.wagtailcore.util import camelcase_to_underscore

logger = logging.getLogger(__name__)


class PathOverrideable:

    def get_template(self, request, mode='', **kwargs):
        path = request.path.strip('/')
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

        templates.append(self.template)  # add the default template as the last one to seek
        
        logger.debug("Adding candidate template based on model name only: %s", self.template)
        selected_template = select_template(templates)
        logger.debug("Selected template: %s", selected_template.name)
        
        return selected_template
