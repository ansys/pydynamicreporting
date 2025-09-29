"""Sphinx documentation configuration file."""

from datetime import datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as metadata_version
import os

from ansys_sphinx_theme import ansys_favicon, get_version_match, pyansys_logo_black
from packaging.version import InvalidVersion, Version
from sphinx_gallery.sorting import FileNameSortKey

project = "ansys-dynamicreporting-core"
try:
    release = metadata_version(project)
except PackageNotFoundError:
    release = "0.0.0"

# Sphinx convention: short 'version' (series), full 'release'
try:
    v = Version(release)
    version = f"{v.major}.{v.minor}"
except InvalidVersion:
    version = release

# Version switcher: keep dev label if present
switcher_version = "dev" if "dev" in release else get_version_match(version)

cname = os.getenv("DOCUMENTATION_CNAME", "dynamicreporting.docs.pyansys.com")
"""The canonical name of the webpage hosting the documentation."""

copyright = f"(c) {datetime.now().year} ANSYS, Inc. All rights reserved"
author = "Ansys Inc."
__ansys_version__ = 261

rst_prolog = f"""
.. _Layout Templates: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_layout_templates.html
.. _Columns: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_layout_columns.html
.. _Panel: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_layout_panel.html
.. _Boxes: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_layout_boxes.html
.. _Tabs: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_layout_tabs.html
.. _Carousel: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_layout_carousel.html
.. _Slider: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_layout_slider.html
.. _Page Footer: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_layout_page_footer.html
.. _Page Header: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_layout_page_header.html
.. _Iterator: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_layout_iterator.html
.. _Tag to Properties: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_layout_tag_properties.html
.. _Table of Contents: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_layout_table_of_contents.html
.. _Link Report: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_layout_linked_report.html
.. _Table Merge: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_generator_table_merge.html
.. _Table Reduction: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_generator_table_reduction.html
.. _Table Row/Column Filter: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_generator_table_row_column_filter.html
.. _Table Value Filter: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_generator_table_value_filter.html
.. _Table Row/Column Sort: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_generator_table_row_column_sort.html
.. _SQL Query: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_generator_sql_query.html
.. _Tree Merge: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_generator_tree_merge.html
.. _Userdefined: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_layout_user_defined_block.html
.. _Generator templates: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_generator_templates.html
.. _Statistical Analysis: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/ad_ug_generator_statistical_analysis.html
.. _Table: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_data_item_table.html
.. _Query Expressions: https://ansyshelp.ansys.com/public/account/secured?returnurl=Views/Secured/corp/v{__ansys_version__}/en/adr_ug/adr_ug_query_expressions.html

"""

# Select desired logo, theme, and declare the html title
html_logo = pyansys_logo_black
html_theme = "ansys_sphinx_theme"
html_short_title = html_title = "PyDynamicReporting documentation |version|"
html_favicon = ansys_favicon

# specify the location of your github repo
html_context = {
    "github_user": "ansys",
    "github_repo": "pydynamicreporting",
    "github_version": "main",
    "doc_path": "doc/source",
}

# specify the location of your github repo
html_theme_options = {
    "switcher": {
        "json_url": f"https://{cname}/versions.json",
        "version_match": switcher_version,
    },
    "github_url": "https://github.com/ansys/pydynamicreporting/",
    "show_prev_next": False,
    "show_breadcrumbs": True,
    "collapse_navigation": True,
    "use_edit_page_button": True,
    "additional_breadcrumbs": [
        ("PyAnsys", "https://docs.pyansys.com/"),
    ],
}

# Sphinx extensions
extensions = [
    # "sphinx.ext.napoleon",  # Use this if you want to use Google style docstrings
    "numpydoc",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.coverage",
    "sphinx.ext.doctest",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "sphinx_gallery.gen_gallery",
]

autoapi_options = [
    "members",
    "undoc-members",
    "private-members",
    "special-members",
    "show-inheritance",
    "show-module-summary",
    "imported-members",
]

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    # kept here as an example
    # "scipy": ("https://docs.scipy.org/doc/scipy/reference", None),
    # "numpy": ("https://numpy.org/devdocs", None),
    # "matplotlib": ("https://matplotlib.org/stable", None),
    # "pandas": ("https://pandas.pydata.org/pandas-docs/stable", None),
    # "pyvista": ("https://docs.pyvista.org/", None),
}

# numpydoc configuration
numpydoc_show_class_members = False
numpydoc_xref_param_type = True

# Consider enabling numpydoc validation. See:
# https://numpydoc.readthedocs.io/en/latest/validation.html#
numpydoc_validate = True
numpydoc_validation_checks = {
    "GL06",  # Found unknown section
    "GL07",  # Sections are in the wrong order.
    # "GL08",  # The object does not have a docstring
    "GL09",  # Deprecation warning should precede extended summary
    "GL10",  # reST directives {directives} must be followed by two colons
    # "SS01",  # No summary found
    "SS02",  # Summary does not start with a capital letter
    # "SS03", # Summary does not end with a period
    "SS04",  # Summary contains heading whitespaces
    # "SS05", # Summary must start with infinitive verb, not third person
    "RT02",  # The first line of the Returns section should contain only the
    # type, unless multiple values are being returned"
}

# -- Sphinx Gallery Options
examples_source = os.path.join(os.path.dirname(__file__), "examples_source")
sls_examples_source = os.path.join(os.path.dirname(__file__), "serverless", "examples")

sphinx_gallery_conf = {
    # convert rst to md for ipynb
    "pypandoc": False,
    # path to your examples scripts
    "examples_dirs": [
        examples_source,
    ],
    # path where to save gallery generated examples
    "gallery_dirs": [
        "examples",
    ],
    # Pattern to search for example files
    "filename_pattern": r"\.py",
    # Remove the "Download all examples" button from the top level gallery
    "download_all_examples": False,
    # Sort gallery example by file name instead of number of lines (default)
    "within_subsection_order": FileNameSortKey,
    # directory where function granular galleries are stored
    "backreferences_dir": None,
    # the initial notebook cell
    "first_notebook_cell": ("# ``pydynamicreporting`` example Notebook\n" "#\n"),
    "plot_gallery": False,
}

# static path
html_static_path = ["_static"]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
source_suffix = ".rst"

# The master toctree document.
master_doc = "index"
