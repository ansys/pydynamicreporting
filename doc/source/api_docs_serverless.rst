Serverless ADR API Reference
============================

This section documents the public API exposed by
``ansys.dynamicreporting.core.serverless``.
Only classes explicitly exported through ``__all__`` are shown.

.. note::
   The list is intentionally explicit to avoid exposing internal classes
   and to keep the API reference stable across releases.

Core Entry Point
----------------

.. autosummary::
   :toctree: _autosummary/
   :nosignatures:

   ansys.dynamicreporting.core.serverless.adr.ADR
   ansys.dynamicreporting.core.serverless.base.ObjectSet
   ansys.dynamicreporting.core.serverless.item.Session
   ansys.dynamicreporting.core.serverless.item.Dataset


Item Model API
--------------

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
