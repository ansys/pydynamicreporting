Serverless ADR
##############

Serverless ADR is a lightweight, local Python API for building reports using
Ansys Dynamic Reporting (ADR), without requiring a running ADR service or
network connection.

It operates entirely within your Python process, directly writing to and
reading from a local ADR-compatible database (e.g., SQLite or PostgreSQL).
This allows you to generate and render full ADR reports, create items and
templates, and manage media and static assets — all without launching the ADR
backend server.

It is built on the same core schema as the traditional service-based ADR, but
works entirely within your local Python environment.

This system is designed for cases where developers or simulation engineers
want to:

- Create, manage, and render reports locally using Python
- Avoid setting up a centralized ADR service or HTTP connection
- Maintain full fidelity with the ADR schema (items, templates, etc.)
- Output HTML, browser-PDF, and PPTX content with the required media and
  static assets.

Serverless ADR is ideal for:

- Local, file-based workflows (e.g., building offline reports)
- Embedding reports in web or desktop applications
- Use in batch scripts, Python notebooks, or simulations

Key features
============

- **Drop-in compatibility with Ansys installations and the Service API**:
  Uses the same Python environment and static/media assets from your installed
  ADR system.
- **Flexible instantiation**:
  Supports SQLite and PostgreSQL databases, Docker-based environments, in-memory and
  legacy environment-variable configurations.
- **In-memory execution**:
  Runs entirely in your local Python process, with no separate backend or
  daemon needed.
- **Jupyter notebook support**:
  Create, query, and render reports directly in Jupyter notebooks.
- **First-class objects**:
  Sessions, Datasets, Items and Templates are actual Python classes, not remote proxies — giving
  you full introspection, subclassing, and lifecycle control.
- **Comprehensive rendering**:
  Generates full HTML reports and PPTX presentations with media, static
  assets, and custom layouts. ADR 27.1 and later can also produce
  browser-fidelity PDFs.

Explore the docs
================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   quickstart
   overview
   instantiation
   sessions_and_datasets
   items
   templates
   browser_pdf
   querying
   media_and_static
   embedding_reports
   copying_objects
   deleting_objects
   configuration
   logging
   examples
   caveats
