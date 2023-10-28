# -*- coding: utf-8 -*-
#
# aiida-wannier90 documentation build configuration file, created by
# sphinx-quickstart on Fri Oct 10 02:14:52 2014.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.
import pathlib
import time

from aiida.manage.configuration import load_documentation_profile

load_documentation_profile()
# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

# -- Project information -----------------------------------------------------

project = 'aiida-quantumespresso'
copyright = f"""2014-{time.localtime().tm_year}, ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE (Theory and Simulation of
Materials (THEOS) and National Centre for Computational Design and Discovery of Novel Materials (NCCR MARVEL)),
Switzerland. All rights reserved"""

# -- General configuration ------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.mathjax',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
    'sphinx_copybutton',
    'sphinx_click.ext',
    'sphinx_design',
    'myst_parser',
    'aiida.sphinxext',
    'autoapi.extension',
]

# Setting the intersphinx mapping to other readthedocs
intersphinx_mapping = {
    'python': ('https://docs.python.org/3.8', None),
    'aiida': ('https://aiida.readthedocs.io/projects/aiida-core/en/latest/', None),
    'aiida_pseudo': ('http://aiida-pseudo.readthedocs.io/en/latest/', None),
}

# Settings for the `autoapi.extenstion` automatically generating API docs
filepath_docs = pathlib.Path(__file__).parent.parent
filepath_src = filepath_docs.parent / 'src'
autoapi_type = 'python'
autoapi_dirs = [filepath_src]
autoapi_ignore = [filepath_src / 'aiida_quantumespresso' / '*cli*']
autoapi_root = str(filepath_docs / 'source' / 'reference' / 'api' / 'auto')
autoapi_keep_files = True
autoapi_add_toctree_entry = False

# Settings for the `sphinx_copybutton` extension
copybutton_selector = 'div:not(.no-copy)>div.highlight pre'
copybutton_prompt_text = r'>>> |\.\.\. |(?:\(.*\) )?\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: '
copybutton_prompt_is_regexp = True

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = 'en'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['**.ipynb_checkpoints', 'reference/api/auto/aiida_quantumespresso/index.rst']

# -- MyST options

myst_enable_extensions = [
    'deflist',
    'colon_fence',
    'substitution',
    'attrs_inline',
    'substitution'
]

myst_substitutions = {
    'aiida_logo': '<img src="../_static/logo_aiida.svg" alt="aiida" class="aiida-logo">',
    'create_magnetic_configuration': \
        '{func}`~aiida_quantumespresso.calculations.functions.create_magnetic_configuration.create_magnetic_configuration`',
    'get_builder_from_protocol': \
        '{meth}`~aiida_quantumespresso.workflows.pw.base.PwBaseWorkChain.get_builder_from_protocol`',
    'get_magnetic_configuration': \
        '{meth}`~aiida_quantumespresso.tools.calculations.pw.PwCalculationTools.get_magnetic_configuration`',
    'nspin': '[`nspin`](https://www.quantum-espresso.org/Doc/INPUT_PW.html#idm412)',
    'PwBaseWorkChain': '{class}`~aiida_quantumespresso.workflows.pw.base.PwBaseWorkChain`',
    'PwCalculation': '{class}`~aiida_quantumespresso.calculations.pw.PwCalculation`',
    'SpinType': '{class}`~aiida_quantumespresso.common.types.SpinType`',
    'starting_magnetization': '[`starting_magnetization`](https://www.quantum-espresso.org/Doc/INPUT_PW.html#idm299)',
    'StructureData': '{class}`~aiida.orm.StructureData',
}

# -- Options for HTML output ----------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.

html_theme = 'sphinx_book_theme'
html_theme_options = {
    'repository_url': 'https://github.com/aiidateam/aiida-quantumespresso',
    'github_url': 'https://github.com/aiidateam/aiida-quantumespresso',
    'twitter_url': 'https://twitter.com/aiidateam',
    'use_edit_page_button': True,
    'navigation_with_keys': False,
    'logo': {
        'text': 'AiiDA Quantum ESPRESSO',
        'image_light': '_static/logo_aiida_quantumespresso-light.png',
        'image_dark': '_static/logo_aiida_quantumespresso-dark.png',
    }
}
html_static_path = ['_static']
html_context = {
    'github_user': 'aiidateam',
    'github_repo': 'aiida-quantumespresso',
    'github_version': 'main',
    'doc_path': 'docs/source',
    'default_mode': 'light',
}
html_sidebars = {
    '**': ['navbar-logo.html', 'navbar-icon-links.html', 'search-field.html', 'sbt-sidebar-nav.html']
}

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
html_static_path = ['_static']
html_css_files = ['aiida-custom.css', 'aiida-qe-custom.css']

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
html_use_opensearch = 'http://aiida-quantumespresso.readthedocs.io'

# Language to be used for generating the HTML full-text search index.
# Sphinx supports the following languages:
#   'da', 'de', 'en', 'es', 'fi', 'fr', 'hu', 'it', 'ja'
#   'nl', 'no', 'pt', 'ro', 'ru', 'sv', 'tr'
html_search_language = 'en'

# Output file base name for HTML help builder.
htmlhelp_basename = 'aiida-quantumespressodoc'

# ------------------------------------------------------------------------------

# Warnings to ignore when using the -n (nitpicky) option
# We should ignore any python built-in exception, for instance
nitpicky = True

nitpick_ignore_regex = [
    (r'py:.*', r'pydantic.*'),
    (r'py:.*', r'con.*'),
    (r'.*', r'Literal.*'),
    (r'.*', r'Tuple.*'),
]
nitpick_ignore = [
    ('py:class', 'AttributeDict'),
    ('py:class', 'ExitCode'),
    ('py:class', 'StructureData'),
    ('py:class', 'PseudoPotentialFamily'),
    ('py:exc', 'ArithmeticError'),
    ('py:exc', 'AssertionError'),
    ('py:exc', 'AttributeError'),
    ('py:exc', 'BaseException'),
    ('py:exc', 'BufferError'),
    ('py:exc', 'DeprecationWarning'),
    ('py:exc', 'EOFError'),
    ('py:exc', 'EnvironmentError'),
    ('py:exc', 'Exception'),
    ('py:exc', 'FloatingPointError'),
    ('py:exc', 'FutureWarning'),
    ('py:exc', 'GeneratorExit'),
    ('py:exc', 'IOError'),
    ('py:exc', 'ImportError'),
    ('py:exc', 'ImportWarning'),
    ('py:exc', 'IndentationError'),
    ('py:exc', 'IndexError'),
    ('py:exc', 'KeyError'),
    ('py:exc', 'KeyboardInterrupt'),
    ('py:exc', 'LookupError'),
    ('py:exc', 'MemoryError'),
    ('py:exc', 'NameError'),
    ('py:exc', 'NotImplementedError'),
    ('py:exc', 'OSError'),
    ('py:exc', 'OverflowError'),
    ('py:exc', 'PendingDeprecationWarning'),
    ('py:exc', 'ReferenceError'),
    ('py:exc', 'RuntimeError'),
    ('py:exc', 'RuntimeWarning'),
    ('py:exc', 'StandardError'),
    ('py:exc', 'StopIteration'),
    ('py:exc', 'SyntaxError'),
    ('py:exc', 'SyntaxWarning'),
    ('py:exc', 'SystemError'),
    ('py:exc', 'SystemExit'),
    ('py:exc', 'TabError'),
    ('py:exc', 'TypeError'),
    ('py:exc', 'UnboundLocalError'),
    ('py:exc', 'UnicodeDecodeError'),
    ('py:exc', 'UnicodeEncodeError'),
    ('py:exc', 'UnicodeError'),
    ('py:exc', 'UnicodeTranslateError'),
    ('py:exc', 'UnicodeWarning'),
    ('py:exc', 'UserWarning'),
    ('py:exc', 'VMSError'),
    ('py:exc', 'ValueError'),
    ('py:exc', 'Warning'),
    ('py:exc', 'WindowsError'),
    ('py:exc', 'ZeroDivisionError'),
    ('py:obj', 'str'),
    ('py:obj', 'list'),
    ('py:obj', 'tuple'),
    ('py:obj', 'int'),
    ('py:obj', 'float'),
    ('py:obj', 'bool'),
    ('py:obj', 'Mapping'),
    ('py:obj', 'qe_tools.parsers.CpInputFile'),
    ('py:obj', 'qe_tools.parsers.PwInputFile'),
]
