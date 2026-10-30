Serverless ADR API Reference
============================

This section documents the public API exposed by
``ansys.dynamicreporting.core.serverless``.
Only classes explicitly exported through ``__all__`` are shown.

The serverless API is designed for programmatic report generation without
running a long-lived ADR server. It provides:

* A single entry point (:class:`~ansys.dynamicreporting.core.serverless.adr.ADR`)
  that manages setup, database/media locations, and rendering.
* A small, well-defined set of item types (tables, trees, HTML, images, scenes,
  files, animations, and strings) that represent report content.
* Layout and generator templates that assemble items into interactive HTML
  reports or PPTX slide decks.

.. note::
   The list is intentionally explicit to avoid exposing internal classes
   and to keep the API reference stable across releases.


Core Entry Point
----------------

The core entry point wraps all serverless functionality behind a single object.
You typically:

1. Instantiate :class:`ansys.dynamicreporting.core.serverless.adr.ADR`,
2. Call :meth:`ADR.setup` to configure database and storage,
3. Create and query items and templates, and
4. Render HTML or PPTX outputs.

The :class:`~ansys.dynamicreporting.core.serverless.base.ObjectSet` helper
provides a lightweight ORM-style interface for querying collections of models,
while :class:`~ansys.dynamicreporting.core.serverless.item.Session` and
:class:`~ansys.dynamicreporting.core.serverless.item.Dataset` help group and
organize items logically.

.. autosummary::
   :toctree: _autosummary/
   :nosignatures:

   ansys.dynamicreporting.core.serverless.adr.ADR
   ansys.dynamicreporting.core.serverless.base.ObjectSet
   ansys.dynamicreporting.core.serverless.item.Session
   ansys.dynamicreporting.core.serverless.item.Dataset


Item Model API
--------------

Item classes represent the atomic content units stored in the serverless ADR
database. They are created and managed through the :class:`ADR` instance and
persisted in the configured SQLite database.

Typical usage is:

* Create items from raw data (NumPy arrays, pandas DataFrames, file paths,
  image buffers, etc.).
* Attach metadata, tags, and visualization options.
* Reference items from templates to build complete reports.

All item types share a common base
(:class:`ansys.dynamicreporting.core.serverless.item.Item`), but specialize in
how they store and render data (for example, tables vs. trees vs. images).

.. autosummary::
   :toctree: _autosummary/
   :nosignatures:

   ansys.dynamicreporting.core.serverless.item.Item
   ansys.dynamicreporting.core.serverless.item.String
   ansys.dynamicreporting.core.serverless.item.HTML
   ansys.dynamicreporting.core.serverless.item.Table
   ansys.dynamicreporting.core.serverless.item.Tree
   ansys.dynamicreporting.core.serverless.item.File
   ansys.dynamicreporting.core.serverless.item.Image
   ansys.dynamicreporting.core.serverless.item.Animation
   ansys.dynamicreporting.core.serverless.item.Scene


Layout Template API
-------------------

Layout templates control how items are arranged and rendered in a report.
They define the “frame” of the report (tabs, panels, carousels, sliders,
headers/footers, PPTX slide layouts, and so on) without hard-coding any
particular dataset.

In a typical workflow you:

1. Define a :class:`Template` hierarchy using one or more layout classes,
2. Bind item filters and parameters to the template, and
3. Ask :class:`ADR` to render the template to HTML, PDF, or PPTX.

These classes focus on *presentation* and navigation rather than on data
transformation.

.. autosummary::
   :toctree: _autosummary/
   :nosignatures:

   ansys.dynamicreporting.core.serverless.template.Template
   ansys.dynamicreporting.core.serverless.template.BasicLayout
   ansys.dynamicreporting.core.serverless.template.PanelLayout
   ansys.dynamicreporting.core.serverless.template.BoxLayout
   ansys.dynamicreporting.core.serverless.template.TabLayout
   ansys.dynamicreporting.core.serverless.template.CarouselLayout
   ansys.dynamicreporting.core.serverless.template.SliderLayout
   ansys.dynamicreporting.core.serverless.template.FooterLayout
   ansys.dynamicreporting.core.serverless.template.HeaderLayout
   ansys.dynamicreporting.core.serverless.template.IteratorLayout
   ansys.dynamicreporting.core.serverless.template.TagPropertyLayout
   ansys.dynamicreporting.core.serverless.template.TOCLayout
   ansys.dynamicreporting.core.serverless.template.ReportLinkLayout
   ansys.dynamicreporting.core.serverless.template.PPTXLayout
   ansys.dynamicreporting.core.serverless.template.PPTXSlideLayout
   ansys.dynamicreporting.core.serverless.template.DataFilterLayout
   ansys.dynamicreporting.core.serverless.template.UserDefinedLayout


Generator Template API
----------------------

Generator templates encapsulate reusable data-processing patterns. Instead of
laying out items directly, they derive new items or sub-templates from existing
data: table merges, reductions, sorting and filtering, tree operations, SQL
queries, or cross-item comparisons.

You typically plug these classes into a larger :class:`Template` tree to:

* Transform one or more :class:`Item` instances into a derived view,
* Encapsulate complex business logic in a single node, and
* Keep layouts declarative while still supporting advanced processing.

.. autosummary::
   :toctree: _autosummary/
   :nosignatures:

   ansys.dynamicreporting.core.serverless.template.TableMergeGenerator
   ansys.dynamicreporting.core.serverless.template.TableReduceGenerator
   ansys.dynamicreporting.core.serverless.template.TableMergeRCFilterGenerator
   ansys.dynamicreporting.core.serverless.template.TableMergeValueFilterGenerator
   ansys.dynamicreporting.core.serverless.template.TableMapGenerator
   ansys.dynamicreporting.core.serverless.template.TableSortFilterGenerator
   ansys.dynamicreporting.core.serverless.template.TreeMergeGenerator
   ansys.dynamicreporting.core.serverless.template.SQLQueryGenerator
   ansys.dynamicreporting.core.serverless.template.ItemsComparisonGenerator
   ansys.dynamicreporting.core.serverless.template.StatisticalGenerator
   ansys.dynamicreporting.core.serverless.template.IteratorGenerator
