Sessions and Datasets
=====================

Conceptual Overview
-------------------

In this API, a **Session** represents a logical grouping or “push” of data from an external source
(such as a solver or post-processor) into the ADR system. It captures metadata about when, where,
and how the data was ingested.

A **Dataset** contains the actual simulation or analysis data associated with a Session. This could
include files, tables, images, or other artifacts generated during the simulation.

By associating report items with Sessions and Datasets, the API maintains clear context and
provenance, enabling organized, meaningful reports that trace back to the original data source.

This API provides methods to create, manage, and fetch Sessions and Datasets to support
flexible and efficient report generation workflows.

Key Entities
------------

- **Session**: Stores metadata about the session or logical grouping of data imported into ADR during a single
data push or analysis run, such as date, hostname, platform, and application version.
- **Dataset**: Stores metadata about the dataset or collection of simulation or analysis data, such as files,
formats, and element counts.

Creating Sessions and Datasets
------------------------------

You can create new sessions and datasets using the ``create`` class method, which
saves the object to the database immediately.

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import Session, Dataset

    session = Session.create(application="My Simulation Run", tags="project=abc")
    dataset = Dataset.create(filename="results.cdb", tags="project=abc")

Setting Defaults in ADR
-----------------------

The ADR singleton instance keeps track of default session and dataset objects.
This helps when creating report items without specifying them explicitly.

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import ADR

    adr = ADR.get_instance()
    adr.set_default_session(session)
    adr.set_default_dataset(dataset)

Accessing Current Session and Dataset
-------------------------------------

You can also access the current session and dataset through the ADR instance:

.. code-block:: python

    current_session = adr.session
    current_dataset = adr.dataset

Fetching Existing Sessions and Datasets
---------------------------------------

You can fetch existing sessions or datasets by GUID or filter queries.

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import Session, Dataset

    # Fetch by GUID (unique identifier)
    session = Session.get(guid="4ee905f0-f611-11e6-8901-ae3af682bb6a")
    dataset = Dataset.get(guid="fa473009-deee-34eb-b6b8-8326236ca9a6")

    # Filter sessions by guid or other attributes
    sessions = Session.filter(guid="4ee905f0-f611-11e6-8901-ae3af682bb6a")

Using Sessions and Datasets When Creating Items
-----------------------------------------------

When you create report items, the current default session and dataset are used
unless you specify different ones explicitly.

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import String

    session = Session.get(guid="4ee905f0-f611-11e6-8901-ae3af682bb6a")
    dataset = Dataset.get(guid="fa473009-deee-34eb-b6b8-8326236ca9a6")

    item = adr.create_item(
        String,
        name="summary_text",
        content="Simulation results summary.",
        tags="section=summary",
        session=session,
        dataset=dataset,
    )

Sessions and Datasets Lifecycle Notes
-------------------------------------

- Sessions and datasets must be saved before creating dependent items.
- Changing the default session or dataset affects all subsequent item creations
  that rely on defaults.
- You can delete sessions or datasets if they are no longer needed, but ensure
  associated items are handled appropriately.

Exceptions and Validation
-------------------------

- Creating or modifying sessions and datasets will raise errors if required fields
  are missing or invalid.
- Fetching non-existent sessions or datasets by GUID raises a ``DoesNotExist`` error.
- Multiple objects returned for a single fetch raises a ``MultipleObjectsReturned`` error.

Summary
-------

Sessions and Datasets provide the structural context for your report items and
allow you to organize simulation data meaningfully.

Next, learn about the different kinds of report items you can create in the
:doc:`items` guide.
