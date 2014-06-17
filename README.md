===============
Wagtail Commons
===============

## bootstrap_content

This adds a django management command which will recursively import a
directory of .yml files, in order to create pages in an instance of
Wagtail CMS.

This is a django management commend for use with Wagtail that
recursively consumes a directory with yaml-based front matter and
markdown contents. For example, if you have the following files:

    foo.yml
    foo/bar.yml
    foo/baz.yml

Where foo.yml looks like:

    ---
    title: Is Lorem Really Ipsum?
    type: core.standardpage
    --- @intro

    Lorem ipsum *blah blah* dolor blah blah

And the other pages, are similar, you will get the pages /foo/,
/foo/bar/ and /foo/baz/. Each one is instantiated according the `type`
attribute found in the first yaml doc. For delimiters of the form

    --- @some_attr

the script will consume the entire contents, render it as markdown,
and then assign the result to the attrribute `some_attr`.

## PathOverrideable mixin for Page

PathOverrideable is mixin for Page classes, which reimplements the
Page.get_template method. It allows the page template to be overriden
based on the incoming request's URL path. For example, it allows the
designer to supply a different template for `/foo/`, `/foo/bar/`, and
`/foo/baz/`. Simply provide a template with the appropriate path
name. For example, supposing your `TEMPLATE_DIRS` contains
`templates`, simply provide:

    templates/default/foo.html
    templates/default/foo/bar.html
    templates/default/foo/baz.html

Assuming that the pages at `/foo/bar/` and `/foo/baz/` are of type
`QuxPage`, then they may also be overriden as follows:

    templates/default/foo/qux_page.html

This will override the template for every page of type `QuxPage` which
has `/foo/` as an ancestor.

In all cases, if an override cannot be found, the value of the Page
object's `template` property will be returned.

Inspired by Mezzanine's template search facility.
