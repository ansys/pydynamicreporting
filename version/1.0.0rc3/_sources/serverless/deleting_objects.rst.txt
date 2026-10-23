Deleting Objects
================

Serverless ADR provides robust APIs for deleting report-related objects, including **Items**, **Templates**, **Sessions**, and **Datasets**. These operations allow you to remove outdated or unnecessary data from your reporting system efficiently.

Deletion Methods
----------------

1. **Deleting Individual Objects**

Every model instance exposes a `.delete()` method that permanently removes that object from the database.

Example:

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import Item

    item = Item.get(name="intro_text")
    item.delete()

2. **Delete Multiple Objects via Query**

Query sets (``ObjectSet``) returned by ``filter()``, ``find()``, or ADR’s ``query()`` method support a bulk ``.delete()`` method that deletes all objects in the set.

.. code-block:: python

   items_to_delete = adr.query(Item, query="A|i_tags|cont|old_project;")
   count_deleted = items_to_delete.delete()
   print(f"Deleted {count_deleted} items.")

Example Usage Patterns
----------------------

**Deleting a Single Session:**

.. code-block:: python

    session = Session.get(guid="4ee905f0-f611-11e6-8901-ae3af682bb6a")
    session.delete()

**Deleting Multiple Datasets by Tag:**

.. code-block:: python

    old_datasets = Dataset.filter(tags__contains="deprecated")
    deleted_count = old_datasets.delete()
    print(f"Deleted {deleted_count} datasets.")


**Deleting Sessions by Tag**

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import Session

    old_sessions = Session.filter(tags__contains="deprecated")
    count = old_sessions.delete()
    print(f"Deleted {count} sessions.")

**Deleting Datasets with Specific Filename Patterns**

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import Dataset

    datasets_to_remove = Dataset.filter(filename="test_data")
    deleted = datasets_to_remove.delete()
    print(f"Deleted {deleted} datasets.")

**Deleting Templates by Name**

.. code-block:: python

    from ansys.dynamicreporting.core.serverless import Template

    templates = Template.filter(name="Old Layout")
    deleted = templates.delete()
    print(f"Deleted {deleted} templates.")

Important Notes and Caveats
---------------------------

- **Automatic Cascading:**
  Deleting a **Template** automatically deletes its child templates but not the associated Items.
  Similarly, deleting a **Session** or **Dataset** will delete dependent Items.

- **Permanent Action:**
  Deletions are irreversible through the API. Always ensure that critical data is backed up before deletion.

- **Permissions:**
  Ensure you have proper database access permissions to perform deletion operations.

- **Query Precision:**
  Use precise query filters to prevent accidental mass deletions.

Error Handling
--------------

- **DoesNotExist Exception:**
  Raised when `.delete()` is called on an object that no longer exists in the database.

- **Database Integrity Errors:**
  If database constraints prevent deletion (e.g., foreign key constraints), exceptions will be raised. Handle these to avoid partial deletions.

- **Invalid Query Filters:**
  Malformed or unsupported query filters will raise an `ADRException` during query or delete calls.

Best Practices
--------------

- **Preview Objects Before Deletion:**
  Always iterate over query results or inspect objects before deleting to confirm correctness.

- **Backup Important Data:**
  Before bulk deletes, create database backups or export data.

- **Use Soft Deletes If Needed:**
  If deletion safety is a concern, consider implementing a "soft delete" flag in your application logic.

- **Clean-Up Orphaned Data:**
  After deletion, ensure no orphaned references remain that could cause errors.
