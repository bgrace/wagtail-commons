__author__ = 'brett@codigious.com'

from wagtail.wagtailcore.models import Site, Page

def page_for_path(path, site=None):
    if not site:
        site = Site.objects.get(is_default_site=True)

    path_components = path.strip('/').split('/')
    return site.root_page.route(None, path_components=path_components).page