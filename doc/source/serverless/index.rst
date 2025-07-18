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
- Output HTML content and media assets for web and desktop apps.

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
- **First-class objects**:
  Sessions, Datasets, Items and Templates are actual Python classes, not remote proxies — giving
  you full introspection, subclassing, and lifecycle control.
- **Comprehensive rendering**:
  Generates full HTML reports — just like the service-based API — with full
  support for media, static assets, and custom layouts.

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
   querying
   media_and_static
   embedding_reports
   copying_objects
   deleting_objects
   configuration
   examples
   troubleshooting
   caveats
   faq
