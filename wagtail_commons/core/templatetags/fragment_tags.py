from django import template
from wagtail.wagtailcore.templatetags.wagtailcore_tags import richtext

__author__ = 'bgrace'

register = template.Library()


class TextFragmentNode(template.Node):

    def __init__(self, fragment_name):
        self.fragment_name = fragment_name

    def render(self, context):
        page = context['self']
        fragment = [f for f in page.fragments.all() if f.name == self.fragment_name]
        if fragment:
            return richtext(fragment[0].fragment)
        else:
            return u''

@register.tag()
def fragment(parser, token):
    try:
        # split_contents() knows not to split quoted strings.
        tag_name, format_string = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires a single argument" % token.contents.split()[0])

    if not (format_string[0] == format_string[-1] and format_string[0] in ('"', "'")):
        raise template.TemplateSyntaxError("%r tag's argument should be in quotes" % tag_name)
    return TextFragmentNode(format_string[1:-1])
