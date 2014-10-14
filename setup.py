from distutils.core import setup

setup(
    name='wagtail-commons',
    version='0.0.1',
    author=u'Brett Grace',
    author_email='brett@codigious.com',
    packages=['wagtail_commons', 'wagtail_commons.core'],
    url='http://github.com/bgrace/wagtail-commons',
    license='BSD licence, see LICENCE file',
    description='Utility commands and mixins for Wagtail CMS',
    long_description=open('README').read(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
    ],
    install_requires=[
        'pyyaml >= 3.11',
        'markdown >= 2.4.1',
    ]
)