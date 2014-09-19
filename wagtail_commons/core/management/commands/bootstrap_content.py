import logging
from django.db.models.fields.related import RelatedField
import re

import glob
import codecs
import os
from io import StringIO
from optparse import make_option
from wagtail.wagtaildocs.models import Document

import yaml, yaml.parser
import markdown

from django.core.management.base import BaseCommand, CommandError
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.template import Template, Context, add_to_builtins
#from django.template import add_to_builtins
from django.conf import settings

from wagtail.wagtailcore.models import Site
from wagtail.wagtailcore.models import Page
from wagtail.wagtailimages.models import get_image_model

try:
    from wagtail.wagtailimages.models import get_upload_to
except ImportError:
    def get_upload_to(instance, path):
        return instance.get_upload_to(path)



__author__ = 'brett@codigious.com'

add_to_builtins("wagtail_commons.core.templatetags.bootstrap_wagtail_tags")
logger = logging.getLogger('wagtail_commons.core')


def get_page_type_class(content_type):
    (app_label, model) = content_type.split('.')
    page_type = ContentType.objects.get(app_label=app_label, model=model)
    return page_type.model_class()


def parse_file(content_root_path, name):
    path = os.path.join(content_root_path, name)
    if not os.path.isfile(path):
        return {}

    f = file(path)
    stream = yaml.load_all(f)
    doc = stream.next()
    stream.close()
    f.close()
    return doc


def get_page_defaults(content_root_path=None):
    if not content_root_path:
        content_root_path = settings.BOOTSTRAP_CONTENT_DIR
    return parse_file(content_root_path, 'pages.yml')


def get_relation_mappings(content_root_path=None):
    if not content_root_path:
        content_root_path = settings.BOOTSTRAP_CONTENT_DIR
    return parse_file(content_root_path, 'relations.yml')


def document_extractor(f):
    delimiter = u'---'
    line = f.next().rstrip(u'\n\r')

    assert delimiter == line,\
        "Malformed input in{0}\n: Line {1}\nExpected first line to only contain '{2}'".format(f, line, delimiter)

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


def load_attributes_from_file(path):
    f = codecs.open(path, encoding='utf-8')
    stream = yaml.load_all(f)
    content_attributes = stream.next()
    stream.close()
    f.seek(0)
    documents = document_extractor(f)
    f.close()

    for key in documents:
        rendered_markdown = Template(documents[key].getvalue()).render(Context())
        db_safe_html = markdown.markdown(rendered_markdown, extensions=['extra', ])
        content_attributes[key] = db_safe_html

    return content_attributes


def load_content(content_directory_path, content_root_path=None):

    content_directory_path = os.path.abspath(content_directory_path)
    if content_root_path:
        content_root_path = os.path.abspath(content_root_path)
    else:
        content_root_path = content_directory_path

    contents_paths = sorted(glob.glob("{0}/*.yml".format(content_directory_path)))

    p = re.compile(r'(?:\d+\s+)?(.*)')  # used to strip numbers from start of file, e.g., 001 sample.yml -> sample.yml
    contents = []

    for path in contents_paths:

        content_attributes = load_attributes_from_file(path)

        if not 'path' in content_attributes:
            computed_path = path[len(content_root_path):-4].strip('/')  # get the bare slug

            # break apart the path so we can remove leading digits from the final component
            path_components = computed_path.split('/')
            normalized_base_path = p.search(path_components[-1]).group(1)
            path_components[-1] = normalized_base_path
            computed_path = '/'.join(path_components)
            computed_path = '/' + computed_path + '/'  # normalize by surrounding with /
            content_attributes['path'] = computed_path

        contents.append(content_attributes)

    sub_directories = [os.path.join(content_directory_path, name) for name in os.listdir(content_directory_path)
                       if os.path.isdir(os.path.join(content_directory_path, name))]

    for directory in sub_directories:
        contents = contents + load_content(content_directory_path=directory,
                                           content_root_path=content_root_path)

    return contents


class SiteNode(object):

    attribute_regex = re.compile(r'(\w*)(?:\[(\w*)\])?')

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
        self.deferred_relations = []

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


    @staticmethod
    def set_page_attributes(page, page_properties, relation_mappings=None):

        def interpolate(page, index, doc, val):
            if "$page" == val:
                return page
            if "$index" == val:
                return index
            if "$doc" == val:
                return doc
            return val

        if not relation_mappings:
            relation_mappings = dict()

        deferred_relations = []
        page_data_mappings = relation_mappings.get(str(page.__class__.__name__))

        for attr, doc in page_properties.items():
            field_name, index = SiteNode.attribute_regex.search(attr).groups()

            # This is a relation, they payload (doc) should be a list of related model instances to deserialize
            field = getattr(page, field_name)
            (field_object, model, direct, m2m) = page._meta.get_field_by_name(field_name)

            if direct:
                if isinstance(field_object, models.ForeignKey):
                    attr_mapper = page_data_mappings[attr]
                    if "$image" == attr_mapper:
                        ImageModel = get_image_model()
                        image_instance = ImageModel()
                        file_name = get_upload_to(image_instance, os.path.basename(doc))
                        image_query = ImageModel.objects.filter(file=file_name)
                        if image_query.exists():
                            setattr(page, attr, image_query.get())
                        else:
                            logger.fatal("Could not find image %s on page %s", doc, page.url)
                            setattr(page, attr, None)
                    else:
                        logger.warn("Don't know what to do with %s->%s on %s", attr, doc, page.url)
                else: # we don't yet support a way of setting a one-to-one here
                    setattr(page, attr, doc)

            # It's a relation, there are two supported syntaxes
            else:
                relation = field
                model = relation.model
                mappings = relation_mappings.get(str(model.__name__), dict())

                # @-notation was used, so this is a markdown-rendered text field. index is the subfield, doc is the text
                if index:
                    create_attrs = {name: interpolate(page, index, doc, val) for name, val in mappings.items()}
                    relation.add(model(**create_attrs))

                # This relation is defined as basic YAML, without any markdown rendering
                else:
                    # The doc is a list of serialized models
                    related_objects = []

                    defer_assignment = False
                    for related_object in doc:

                        common_keys = set(mappings).intersection(related_object)
                        create_attrs = {}
                        for k in common_keys:
                            create_attrs[k] = interpolate(page, index, doc, mappings[k])


                        for rel_attr, rel_doc in related_object.items():
                            if rel_attr in create_attrs:
                                mapping_doc = create_attrs[rel_attr]
                            else:
                                mapping_doc = rel_doc

                            if isinstance(mapping_doc, str):
                                if '$' == mapping_doc[0]:
                                    defer_assignment = True
                            else:
                                defer_assignment = True

                            create_attrs[rel_attr] = rel_doc

                        # for rel_doc in create_attrs.values():
                        #     print "Checking {}".format(rel_doc)
                        #     if isinstance(rel_doc, str):
                        #         defer_assignment = defer_assignment or '$' == rel_doc[0]

                        related_objects.append(create_attrs)

                    if defer_assignment:
                        deferred_relations.append((page, attr, related_objects))
                        #model=page, rel_name=attr, create_attrs_list=related_objects)
                    else:
                        related_models = []
                        for create_attrs in related_objects:
                            related_models.append(model(**create_attrs))

                        setattr(page, attr, related_models)

        return deferred_relations



    def instantiate_page(self, owner_user,
                         page_property_defaults=None,
                         relation_mappings=None,
                         dry_run=True):

        if not page_property_defaults:
            page_property_defaults = dict()

        if not relation_mappings:
            relation_mappings = dict()

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

        self.deferred_relations = self.set_page_attributes(page, page_properties, relation_mappings=relation_mappings)

        if not dry_run:
            self.parent_page.add_child(instance=page)
            page.save()

        self.page = page

        for child in self.children:
            child.parent_page = self.page
            child.instantiate_page(owner_user=owner_user, page_property_defaults=page_property_defaults,
                                   dry_run=dry_run, relation_mappings=relation_mappings)

        return self.page


    def transformation_for_name(self, name):

        def identity(val):
            return val

        def page_for_path(val):
            url_path = '///' + val.strip('/') + '/'
            try:
                return Page.objects.get(url_path=url_path).specific
            except Page.DoesNotExist:
                logger.critical("Couldn't find page %s (%s)", val, url_path)
                return None

        def image_for_name(val):
            ImageModel = get_image_model()
            instance = ImageModel()
            return ImageModel.objects.get(file=get_upload_to(instance, val))

        def document_for_name(val):
            return Document.objects.get(file=os.path.join('documents', val))

        def to_markdown(val):
            return markdown.markdown(val)

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

    def instantiate_deferred_models(self, owner_user,
                                    page_property_defaults=None,
                                    relation_mappings=None,
                                    dry_run=True):

        for (page, relation_name, objects) in self.deferred_relations:
            field = getattr(page, relation_name)
            (field_object, _, _, _) = page._meta.get_field_by_name(relation_name)
            model = field_object.model
            model_mapper = relation_mappings[model.__name__]

            related_objects = []
            for object in objects:
                new_obj = model()

                for attr, val in object.items():
                    transformation = self.transformation_for_name(model_mapper.get(attr, None))
                    setattr(new_obj, attr, transformation(val))

                related_objects.append(new_obj)

            setattr(page, relation_name, related_objects)
            page.save()

        for child in self.children:
            child.instantiate_deferred_models(owner_user,
                                              page_property_defaults=None,
                                              relation_mappings=relation_mappings,
                                              dry_run=dry_run)


        
class Command(BaseCommand):
    args = '<content directory>'
    help = 'Creates content from markdown and yaml files, found in <content directory>/pages'

    option_list = BaseCommand.option_list + (
        make_option('--content', dest='content_path', type='string', ),
        make_option('--owner', dest='owner', type='string'),
        make_option('--dry', dest='dry', action='store_true'),
    )

    option_list = BaseCommand.option_list + (
        make_option('--content', dest='content_path', type='string', ),
        make_option('--owner', dest='owner', type='string'),
        make_option('--dry', dest='dry', action='store_true'),
    )

    def handle(self, *args, **options):

        if not options['content_path']:
            raise CommandError("Pass --content <content dir>, where <content dir>/pages contain .yml files")

        if not options['owner']:
            raise CommandError("Pass --owner <username>, where <username> will be the content owner")

        content_path = options['content_path']
        owner_user = User.objects.get(username=options['owner'])
        dry_run = options['dry']

        contents = load_content(os.path.join(content_path, 'pages'))

        try:
            site = Site.objects.get(is_default_site=True)
            if site.root_page:
                site.root_page.delete()
        except Site.DoesNotExist:
            site = Site(is_default_site=True)


        root = Page.get_first_root_node()
        for child in root.get_children():
            child.delete()

        home_page_candidates = [page for page in contents if page['path'] == '/']
        assert len(home_page_candidates) == 1, ("Expected one page with a path of '/', got %s" %len(home_page_candidates))
        home_page_attrs = home_page_candidates[0]

        content_root = SiteNode(full_path='/', page_properties=home_page_attrs, parent_page=root)
        for page_attrs in contents:
            new_node = SiteNode(full_path=page_attrs['path'], page_properties=page_attrs)
            content_root.add_node(new_node)

        page_property_defaults = get_page_defaults(content_path)
        relation_mappings = get_relation_mappings(content_path)

        home_page = content_root.instantiate_page(owner_user=owner_user,
                                                  page_property_defaults=page_property_defaults,
                                                  relation_mappings=relation_mappings,
                                                  dry_run=dry_run)

        if dry_run:
            self.stdout.write("Dry run, exiting without making changes")
            return

        content_root.instantiate_deferred_models(owner_user=owner_user,
                                                 page_property_defaults=page_property_defaults,
                                                 relation_mappings=relation_mappings,
                                                 dry_run=dry_run)

        site.root_page = home_page
        site.save()


