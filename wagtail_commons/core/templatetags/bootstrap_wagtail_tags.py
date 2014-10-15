from django import template
import datetime
from wagtail.wagtailcore.models import Page
from wagtail.wagtailcore.rich_text import EMBED_HANDLERS, LINK_HANDLERS
from wagtail.wagtailimages.models import get_image_model

try:
    from wagtail.wagtailimages.models import get_upload_to
except ImportError:
    def get_upload_to(instance, path):
        return instance.get_upload_to(path)

__author__ = 'bgrace'

register = template.Library()


class CurrentTimeNode(template.Node):

    def __init__(self, format_string):
        self.format_string = format_string

    def render(self, context):
        return datetime.datetime.now().strftime(self.format_string)


@register.tag(name="current_time")
def do_current_time(parser, token):
    try:
        # split_contents() knows not to split quoted strings.
        tag_name, format_string = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires a single argument" % token.contents.split()[0])
    if not (format_string[0] == format_string[-1] and format_string[0] in ('"', "'")):
        raise template.TemplateSyntaxError("%r tag's argument should be in quotes" % tag_name)
    return CurrentTimeNode(format_string[1:-1])


@register.simple_tag(takes_context=False)
def image(image_filename, format, alt_text):

    Image = get_image_model()
    instance = Image()
    path = get_upload_to(instance, image_filename)
    query = Image.objects.filter(file=path)
    if not query.exists():
        return "<span style='background: red; color: white'>MISSING IMAGE %s</span>" % image_filename
    else:
        image = query.get()
        embed_handler = EMBED_HANDLERS['image']
        image_attrs = embed_handler.get_db_attributes({'data-id': image.id,
                                                       'data-format': format,
                                                       'data-alt': alt_text})
        image_attrs['embedtype'] = 'image'

        embed_attr_str = u''
        for k, v in image_attrs.items():
            embed_attr_str += u" {0}=\"{1}\"".format(k, v)

        return "<embed{0}/>".format(embed_attr_str)

@register.simple_tag(takes_context=False)
def page(path):
    path = '///'+path.strip('/')+'/'
    page_query = Page.objects.filter(url_path=path)

    if not page_query.exists():
        assert False, "No such page %s" % path
    else:
        page = page_query.get()
        link_handler = LINK_HANDLERS['page']

        link_tag = '<a linktype="page">'

        return "THERE BE A LINK HERE"


def unquoted(tag_name, arg):
    if arg[0] == arg[-1] and arg[0] in ('"', "'"):
        return arg[1:-1]
    else:
        raise template.TemplateSyntaxError("%r tag requires the url path to be quoted" % tag_name)


@register.tag(name='link')
def do_link(parser, token):

    try:
        tag_name, url_path = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires one argument, the url path of the page being linked")

    url_path = unquoted(tag_name, url_path)

    nodelist = parser.parse(('endlink',))
    parser.delete_first_token()

    return WagtailInternalPageLinkNode(nodelist, url_path)


class WagtailInternalPageLinkNode(template.Node):

    def __init__(self, nodelist, url_path):
        self.nodelist = nodelist
        self.url_path = url_path

    def render(self, context):
        inner_content = self.nodelist.render(context)
        return u'<a data-linktype="proto-page" href="{0}">{1}</a>'.format(self.url_path, inner_content)






