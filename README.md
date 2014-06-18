===============
Wagtail Commons
===============

## About

While working on two different Wagtail sites, here are some things I
used... *on both of them*.

## Installation

```
pip install -e git://github.com/bgrace/wagtail-commons.git#egg=wagtail-commons --upgrade
```

Add to `INSTALLED_APPS`:

```
INSTALLED_APPS = (
    ...
    wagtail_commons.core,
    ...
)
```

## Management command: bootstrap_content

This adds a Django management command which will recursively import a
directory of .yml files, in order to create pages in an instance of
Wagtail CMS.

### Introduction

This is a django management commend for use with Wagtail that
recursively consumes a directory with yaml-based front matter and
markdown contents. For example, if you have the following files:

    foo.yml
    foo/bar.yml
    foo/baz.yml

Where foo.yml looks like:

    ---
    title: Is Lorem Really Ipsum?
    type: demo.standardpage
    --- @body

    Lorem ipsum *blah blah* dolor blah blah

And the other pages, are similar, you will get the pages /foo/,
/foo/bar/ and /foo/baz/. Each one is instantiated according the `type`
attribute found in the first yaml doc. For delimiters of the form

    --- @some_attr

the script will consume the entire contents, render it as markdown,
and then assign the result to the attrribute `some_attr`.

**WARNING**: This command is destructive by design. It finds your root
  page, _deletes it and everything below it_, and creates a brand new
  root. So if you have put content in your database, it will be gone
  after you run it. It is intended to be executed repeatedly as you
  evolve your content, and meant to discourage creating content "by
  hand" during the design/development phase.

### Invocation

Run as `python manage.py bootstrap_content --content <page definitions directory> --owner <username>`

For example:

`./manage.py bootstrap_content --content ../resources/content --owner johndoe`

### Page owner

Wagtail expects each page to have an owner. You must supply the
username of a Django user who will be the owner the Pages that will be
created with the `--owner` argument. This is a required argument.

### Content Directory Structure

Use the `--content` argument to tell the importer where to begin
searching for content. The example command above will look at
`../resources/content/pages.yml` for some configuration, and then it
will recursively consume the contents of `../resources/content/pages`,
looking for any file with an extension of `.yml`.

#### pages.yml

The attributes in pages.yml will be added to every page definition,
unless the page definition provides a value. For example, most of the
pages in one of my projects are of type 'core.standardpage'. So my
pages.yml looks like:

```
---
type: core.standardpage
---
```

#### Page definition files

Page definition files are a mixture of YAML and markdown, with a .yml
extension. The command uses, or perhaps abuses, the YAML concept of
embedding multiple documents in a single file, and recognizes an
alternative syntax to embed multiple markdown documents. While this is
grotesquely out of spec for both parsers, it seems friendly to the
humans who have to edit it.

For example, suppose a page definition file is placed at
`contents/pages/lorem.yml` and it looks like this:

```
---
type: demo.standardpage
title: Lorem in the Mist
--- @intro
A brief history of *lorem ipsum*.
--- @body
## The early years

Lorem ipsum was first ipsetur dolet sinatra lectibemur indemus
singlemaltscotchitum et valar morghulis megatonda whimsy.

Et cetera ceteribus
```

The document must begin with `---` on a line by itself in order to be
interpeted as YAML by the YAML parser. Any attributes defined in the
section will be applied to the Page object. After the first YAML
document is consumed, the command will look for documents delimeted by
`--- @some_attr`, where `some_attr` corresponds to some (for now,
string-based) Django model field. The markdown processor will convert
the contents to HTML, which will be assigned to the corresponding
attribute. Currently this command only supports attributes that can be
assigned to fields expecting string data. In other words there is a
**huge, gaping hole in its capabilities**. Sorry about that. I'll
probably need to add it for my own purposes, so sit tight.

For example, the above example will be interpreted in the following way:

- Create a new page object of type demo.StandardPage
- Make its owner the `User` object corresponding to the `--owner` flag
- Set the URL path of the page to `/lorem/` (inferred by placement in the contents directory)
- Set the `title` of the page to 'Lorem in the Mist'
- Set the `intro` of the page to "A brief history of &lt;i&gt;lorem ipsum&lt;/i&gt;"
- Set the `body` of the page to "&lt;h2&gt;The early years&lt;/h2&gt;..." (and so on)

### Directory layout and site map

In general, the directory layout is the sitemap. The slug for the Page
is inferred from the path leading to the page definition, and the name
of the page definition file, less the extension. So a page found at
`$CONTENT_ROOT/pages/kingdom/phyllum/class/order/species/roygbiv.yml`
would have the URL path
`/kingdom/phyllum/class/order/species/roygbiv/`. However, you need to
have a page definition present at every intermediate level. So you
would actually need:

```
pages/kingdom.yml
pages/kingdom/phyllum.yml
pages/kingdom/phyllum/class.yml
pages/kingdom/phyllum/class/order.yml
pages/kingdom/phyllum/class/species.yml
pages/kingdom/phyllum/class/species/roygbiv.yml
```

(Note: I believe that this is an intrinsic limitation of Wagtail,
since each Page must have a parent.)

### Defining the root page

Your site needs a home page, with a url path of `/`. But you're not
going to call your page definition `/.yml`, right? Right. Fortunately,
your YAML front matter can contain an optional attribute, `path`,
which overrides inferred URL. *You must* have a page definition with:

```
---
path: /
(... other attributes)
```

For example, one of my sites has a file `pages/home.yml`, which looks
like this:

```
---
path: /
title: Home
type: core.homepage
--- @body
Lorem facta est
```

It doesn't matter where in the content directory hierarchy this file
exists. In fact, you can use the `path` override to enforce a
completely flat directory layout. The path-based URL inference is
purely a convenience.

## PathOverrideable mixin for Page

I created this package for myself as a repository of Wagtail
miscellanea. The first one of which is a way for a Page to override
the template based on the URL which it is attempting to serve.

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
object's `template` property will be returned, i.e., whatever template
would normally be selected in the absence of this mixin.

Inspired by Mezzanine's template-lookup approach.
