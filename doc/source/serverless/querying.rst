Querying
========

Serverless ADR provides flexible querying capabilities to retrieve your report data objects,
including **Items**, **Templates**, **Sessions**, and **Datasets**. This lets you find and
filter report content efficiently by attributes, tags, or complex query strings.

Query Methods
-------------

The main query methods are available on each model class:

- ``get(**kwargs)``

  Retrieve a single object matching the given field filters.
  Raises an exception if zero or multiple objects are found.

- ``filter(**kwargs)``

  Return an ``ObjectSet`` containing all objects matching the filters.

- ``find(query: str, **kwargs)``

  Perform an advanced query using the ADR query language syntax.

- ``ADR.query(query_type, *, query="", **kwargs)``

  A static method that allows querying across any of the core object types
  by specifying the type explicitly (`Item`, `Template`, `Session`, or `Dataset`).
  Returns an ``ObjectSet`` of matching objects.

Examples
--------

**Fetch a single Session by GUID:**

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import Session

    session = Session.get(guid="4ee905f0-f611-11e6-8901-ae3af682bb6a")
    print(session.hostname, session.application)

**Filter Items by tag substring:**

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import Item

    session = Session.get(guid="4ee905f0-f611-11e6-8901-ae3af682bb6a")
    items = Item.filter(session=session)
    for item in items:
        print(item.name, item.tags)

**Find Items with a custom ADR query string:**

.. code-block:: python

    query_str = "A|i_tags|cont|project=wing_sim;A|i_name|eq|summary_text;"
    matching_items = Item.find(query=query_str)
    print(f"Found {len(matching_items)} matching items")

**Use the ADR query method to find Sessions with a name:**

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import ADR, Session

    adr = ADR.get_instance()
    sessions = adr.query(Session, query="A|s_name|eq|Test Session;")
    for s in sessions:
        print(s.guid, s.date)

Subclass Queries
----------------

When using subclasses like ``HTML`` or ``BasicLayout``, queries automatically filter by the subclass type.
Explicitly adding type filters (e.g., ``i_type|eq|html``) in query strings is disallowed and will raise an exception.

**Correct usage:**

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import HTML

    html_items = HTML.find(query="A|i_tags|cont|intro;")
    for html in html_items:
        print(html.name)

**Incorrect usage (raises exception):**

.. code-block:: python

    html_items = HTML.find(query="A|i_type|eq|html;")  # Raises ADRException

Understanding ADR Query Strings
-------------------------------

ADR queries use the format:

``Connector|Field|Operation|Value;``

- **Connector**: Connector to chain multiple queries, e.g., ``A`` for 'AND' and ``O`` for 'OR'.
- **Field**: Field name, e.g., ``i_tags`` for item tags.
- **Operation**: Comparison operator, e.g., ``cont`` (contains), ``eq`` (equals).
- **Value**: The value to compare.

Multiple filters are combined with a logical AND.

Example:

``A|i_tags|cont|project=wing_sim;A|i_name|eq|summary_text;``

Matches items tagged ``project=wing_sim`` AND named ``summary_text``.

Querying Sessions and Datasets
------------------------------

Sessions and Datasets support similar querying by their fields.

**Get a Dataset by filename:**

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import Dataset

    dataset = Dataset.get(filename="results.cdb")
    print(dataset.format, dataset.numparts)

**Filter Datasets by format:**

.. code-block:: python

    cdb_datasets = Dataset.filter(format="cdb")
    for ds in cdb_datasets:
        print(ds.filename)

Working with Query Results
--------------------------

- ``get()`` returns a single model instance.
- ``filter()``, ``find()``, and ``ADR.query()`` return an ``ObjectSet`` that behaves like a list and can be cast to a list or iterated over.

You can iterate over results, use ``len()``, or index them:

.. code-block:: python

    for item in items:
        print(item.name, item.tags)

    print(f"Total items: {len(items)}")
    first_item = items[0]

Error Handling
--------------

- ``DoesNotExist``: Raised when ``get()`` finds no match.
- ``MultipleObjectsReturned``: Raised when ``get()`` finds multiple matches.
- ``ADRException``: Raised for invalid queries or disallowed filters.
- ``TypeError``: Raised by ``ADR.query()`` if an invalid model type is passed.

Example:

.. code-block:: python

    try:
        session = Session.get(guid="non-existent-guid")
    except Session.DoesNotExist:
        print("Session not found")
    except Session.MultipleObjectsReturned:
        print("Multiple sessions matched")

Summary
-------

Querying in Serverless ADR allows precise and flexible data retrieval using:

- Field filters for common attributes
- Powerful ADR query language strings
- Subclass-specific automatic type filtering

Use querying to tailor report content dynamically for analysis and generation.

Next Steps
----------

See the :doc:`media_and_static` guide for managing media and static files linked to your reports.
