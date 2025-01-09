#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
"""
Standard sphinx config file.
"""

import os
import sys

# WORKAROUND: https://github.com/sphinx-doc/sphinx/issues/9243
import sphinx.builders.html
import sphinx.builders.latex
import sphinx.builders.texinfo
import sphinx.builders.text
import sphinx.ext.autodoc

# This is an elaborate hack to insert write property into _all_
# mock decorators. It is needed for getting @attribute to build
# in mocked out tango.server
# see https://github.com/sphinx-doc/sphinx/issues/6709
from sphinx.ext.autodoc.mock import _MockObject


def call_mock(self, *args, **kw):
    from types import FunctionType, MethodType

    if args and type(args[0]) in [type, FunctionType, MethodType]:
        # Appears to be a decorator, pass through unchanged
        args[0].write = lambda x: x
        return args[0]
    return self


_MockObject.__call__ = call_mock
# hack end

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.insert(0, os.path.abspath("../../src"))


# -- Path set up --------------------------------------------------------------
# pylint: disable=invalid-name
autodoc_mock_imports = [
    "numpy",
    "ska_tango_base",
    "tango",
    "ska_control_model",
    "ska_ser_logging",
    "pysnmp",
    "pyasn1",
]


autodoc_default_options = {
    "members": True,
    "special-members": "__init__",
}


# -- Project information -----------------------------------------------------
release_filename = os.path.join("..", "..", ".release")
with open(release_filename) as fd:
    line = fd.readline()
    release = line.strip().split("=")[1]

author = "MCCS team"
project = "SAT LMC Prototype"
copyright = "2020, SKA MCCS Team"

# -- General configuration ------------------------------------------------
nitpicky = True

nitpick_ignore = [
    # TODO: these all have to be ignored because we are exposing through
    # our public interface, objects from external packages that do not
    # have sphinx-based online docs for us to cross-link to.
    # In many case, we should look at refactoring so that these external
    # dependencies don't leak out through our public interface.
    ("py:exc", "yaml.YAMLError"),
    ("py:class", "ska_tango_base.base.BaseComponentManager"),
    ("py:class", "ska_tango_base.base.CommandTracker"),
    ("py:class", "HealthState"),
]

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
#    "sphinxcontrib.plantuml",
]
autoclass_content = "class"
plantuml_syntax_error_image = True


# Add any paths that contain templates here, relative to this directory.
# templates_path = []

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
source_suffix = [".rst"]
# source_suffix = ['.rst', '.md']

# The master toctree document.
master_doc = "index"


# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = "En-en"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = []

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True

add_module_names = False

# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "ska_ser_sphinx_theme"

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
html_theme_options = {}

html_context = {}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = []

# -- Options for HTMLHelp output ------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = "developerskatelescopeorgdoc"


# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',
    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',
    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',
    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (
        master_doc,
        "developerskatelescopeorg.tex",
        "developer.skatelescope.org Documentation",
        "Marco Bartolini",
        "manual",
    )
]


# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    (
        master_doc,
        "developerskatelescopeorg",
        "developer.skatelescope.org Documentation",
        [author],
        1,
    )
]


# -- Options for Texinfo output ----------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "developerskatelescopeorg",
        "developer.skatelescope.org Documentation",
        author,
        "developerskatelescopeorg",
        "One line description of project.",
        "Miscellaneous",
    )
]

# -- Options for Epub output -------------------------------------------------

# Bibliographic Dublin Core info.
epub_title = project
epub_author = author
epub_publisher = author
epub_copyright = copyright

# The unique identifier of the text. This can be a ISBN number
# or the project homepage.
#
# epub_identifier = ''

# A unique identification for the text.
#
# epub_uid = ''

# A list of files that should not be packed into the epub file.
epub_exclude_files = ["search.html"]


# -- Extension configuration -------------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3.11/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pytango": ("https://pytango.readthedocs.io/en/stable/", None),
    "ska-control-model": (
        "https://developer.skao.int/projects/ska-control-model/en/latest/",
        None,
    ),
    "ska-tango-base": (
        "https://developer.skao.int/projects/ska-tango-base/en/0.19.1/",
        None,
    ),
}
