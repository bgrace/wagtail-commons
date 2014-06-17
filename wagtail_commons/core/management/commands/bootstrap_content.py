import glob
import codecs
from io import StringIO, BytesIO
from optparse import make_option
import datetime
from faker import Faker
import yaml, yaml.parser
import markdown
import random

from django.contrib.auth.models import User
from django.template.defaultfilters import slugify
from django.contrib.contenttypes.models import ContentType

from wagtail.wagtailadmin.views.pages import get_page_edit_handler
from wagtail.wagtailcore.models import Site

import pprint

__author__ = 'brett@codigious.com'

from django.core.management.base import BaseCommand, CommandError
from core.models import *

owner = User.objects.get(id=1)


def get_page_type_class(content_type):
    (app_label, model) = content_type.split('.')
    page_type = ContentType.objects.get(app_label=app_label, model=model)
    return page_type.model_class()


def document_extractor(f):
    delimiter = '---'
    assert delimiter+'\n' == f.next(), "Malformed input {0}, Expected first line to only contain '{1}'".format(f, delimiter)

    contents = dict()
    key = None

    for line in f:
        if line[0:3] == delimiter:
            if line[3:5] == ' @':
                key = line[5:-1]
                contents[key] = StringIO()
                continue

        if key:
            unix_line = line.replace('\r\n', '\n')
            contents[key].write(unix_line)

    return contents


def load_content(content_directory_path, content_root_path=None):

    content_directory_path = os.path.abspath(content_directory_path)
    if content_root_path:
        content_root_path = os.path.abspath(content_root_path)
    else:
        content_root_path = content_directory_path

    contents_paths = glob.glob("{0}/*.yml".format(content_directory_path))
    contents = []
    for path in contents_paths:
        f = codecs.open(path, encoding='utf-8')
        stream = yaml.load_all(f)
        front_matter = stream.next()
        stream.close()
        f.seek(0)
        documents = document_extractor(f)

        if not 'path' in front_matter:
            computed_path = '/' + path[len(content_root_path):-4].strip('/') + '/'
            front_matter['path'] = computed_path

        for key in documents:
            front_matter[key] = markdown.markdown(documents[key].getvalue())
        contents.append(front_matter)

    sub_directories = [os.path.join(content_directory_path, name) for name in os.listdir(content_directory_path)
                       if os.path.isdir(os.path.join(content_directory_path, name))]

    for directory in sub_directories:
        contents = contents + load_content(content_directory_path=directory,
                                           content_root_path=content_root_path)

    return contents


class SiteNode:

    def __init__(self, full_path, page_properties=None, parent_page=None):
        self.children = []
        self.full_path = full_path.rstrip('/')+'/'
        last_component_index = self.full_path[0:-1].rfind('/')
        self.slug = self.full_path[last_component_index+1:-1]
        if not self.slug and self.full_path == '/':
            self.slug = '/'
        self.page_properties = page_properties
        self.parent_page = parent_page
        self.page = None

    def __str__(self):
        return self.full_path

    def add_node(self, new_node):
        # we only care about the part of the new node's path that is not a prefix of this node's path
        assert 0 == new_node.full_path.find(self.full_path), "Trying to add a node which is not a proper descendent"
        assert len(new_node.full_path) >= len(self.full_path), "New node too short to be placed here: {0} vs. {1}".\
            format(new_node.full_path, self.full_path)

        if new_node.full_path == self.full_path:
            self.page_properties = new_node.page_properties
            return

        remainder_path = new_node.full_path[len(self.full_path):]
        remainder_path = '/'+remainder_path.strip('/')+'/'
        this_node_slug = remainder_path[1:remainder_path.find('/', 1)]

        ancestor = [child for child in self.children if child.slug == this_node_slug]

        if ancestor:
            assert len(ancestor) == 1, "Siblings with same slug?"
            ancestor[0].add_node(new_node)
        else:
            if remainder_path.strip('/') == this_node_slug:  # leaf node
                self.children.append(new_node)
            else:
                intermediate_node = SiteNode(full_path=self.full_path+this_node_slug)
                self.children.append(intermediate_node)
                intermediate_node.add_node(new_node)

    def instantiate_page(self, owner_user, page_property_defaults={}):
        page_properties = dict(page_property_defaults.items() + self.page_properties.items())
        page_class = get_page_type_class(page_properties['type'])
        page_properties.pop('type', None)

        page = page_class(owner=owner_user)
        page.live = True
        page.has_unpublished_changes = False
        page.show_in_menus = True
        page.slug = self.slug[0:50]

        # for all other page attributes, set them dynamically
        page.title = page_properties['title']
        for attr in page_properties:
            setattr(page, attr, page_properties[attr])

        self.parent_page.add_child(instance=page)
        page.save()
        self.page = page

        for child in self.children:
            child.parent_page = self.page
            child.instantiate_page(owner_user=owner_user, page_property_defaults=page_property_defaults)

        return self.page

        
class Command(BaseCommand):
    args = '<content directory>'
    help = 'Creates content from markdown and yaml files, found in <content directory>/pages'

    option_list = BaseCommand.option_list + (
        make_option('--content', dest='content_path', type='string', ),

    )

    def handle(self, *args, **options):
        if len(args) != 1:
            raise Exception("Only accepts one argument, path to content directory containing a 'pages' directory")

        content_path = args[0]

        contents = load_content(os.path.join(content_path, 'pages'))

        root = Page.get_first_root_node()

        return
        
        home_page_attrs = {'type': 'core.homepage',
                           'title': "Sunset Gardens",
                           'body': "Placeholder for home page copy",
                           'menu_title': "Home"}

        content_root = SiteNode(full_path='/', page_properties=home_page_attrs, parent_page=root)
        for page_attrs in contents:
            new_node = SiteNode(full_path=page_attrs['path'], page_properties=page_attrs)
            content_root.add_node(new_node)

        home_page = content_root.instantiate_page(owner_user=owner, page_property_defaults={'type': 'core.standardpage'})

        site = Site.objects.get(is_default_site=True)
        old_root_page = site.root_page
        site.root_page = home_page
        site.save()

        if old_root_page:
            old_root_page.delete()

        create_site_menus(home_page)

