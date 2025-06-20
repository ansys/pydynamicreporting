Overview
========

Serverless ADR is a lightweight, local Python API for building and rendering reports
using Ansys Dynamic Reporting (ADR) without requiring a running ADR backend or network connection.

Key Benefits
------------

- Runs entirely within your Python process — no external server needed.
- Supports both SQLite and PostgreSQL databases.
- Uses the same core schema as the traditional ADR service.
- Enables offline report generation with full fidelity (items, templates, layouts).
- Suitable for local workflows, batch processing, and embedding in Python applications.
- Fully backwards compatible with the service-based ADR API.

Core Concepts
-------------

- **ADR Instance**: Singleton object managing database connections and report lifecycle.
- **Sessions and Datasets**: Organize your report data and metadata.
- **Items**: Report components such as HTML, tables, images, animations, and more.
- **Templates**: Define report structure and layout using various built-in and custom classes.
- **Static and Media Files**: Handle CSS, JavaScript, images, and other assets required for rendering.

Built on Django ORM
-------------------

Serverless ADR uses Django’s ORM for database interaction and schema management.
Unlike traditional ADR, it does not require a running web server but leverages
Django’s powerful database and templating features locally.

Use Cases
---------

- Generating offline simulation reports.
- Integration into batch workflows and automated pipelines.
- Template design and testing before deployment.
- Embedding ADR reporting capabilities inside Python applications.

For setup details and advanced configuration, see the :doc:`instantiation` guide.
