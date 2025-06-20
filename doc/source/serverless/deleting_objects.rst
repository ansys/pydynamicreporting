Deleting Objects
================

Serverless ADR allows you to delete report objects such as **Items**, **Templates**, **Sessions**, and **Datasets** either individually or in bulk via query results. Proper deletion helps maintain a clean database and remove obsolete or unwanted report data.

Methods for Deletion
-------------------

1. **Delete Individual Objects**

   Each object instance supports a ``.delete()`` method to remove itself from the database.

   .. code-block:: python

       item = Item.get(name="obsolete_item")
       item.delete()

2. **Delete Multiple Objects via Query**

   Query sets (``ObjectSet``) returned by ``filter()``, ``find()``, or ADR’s ``query()`` method support a bulk ``.delete()`` method that deletes all objects in the set.

   .. code-block:: python

       items_to_delete = adr.query(Item, query="A|i_tags|cont|old_project;")
       count_deleted = items_to_delete.delete()
       print(f"Deleted {count_deleted} items.")

Usage Examples
--------------

**Deleting a Single Session:**

.. code-block:: python

    session = Session.get(guid="4ee905f0-f611-11e6-8901-ae3af682bb6a")
    session.delete()

**Deleting Multiple Datasets by Tag:**

.. code-block:: python

    old_datasets = Dataset.filter(tags__icontains="deprecated")
    deleted_count = old_datasets.delete()
    print(f"Deleted {deleted_count} datasets.")

**Deleting All Templates with a Specific Name:**

.. code-block:: python

    templates = Template.filter(name="Old Report Template")
    deleted_count = templates.delete()
    print(f"Deleted {deleted_count} templates.")

Important Considerations
------------------------

- Deleting a Template does not automatically delete its child Templates or associated Items. Handle dependent objects accordingly to avoid orphaned data.
- Similarly, deleting Sessions or Datasets does not cascade to associated Items; manually delete dependent Items if needed.
- Deletion operations are permanent and cannot be undone. Ensure backups or exports are made if data recovery is required.
- You may need appropriate database permissions to perform deletions.
- Use precise query filters to avoid unintended data loss.

Error Handling
--------------

- Attempting to delete non-existent objects will raise a ``DoesNotExist`` error.
- Database-level integrity errors may occur if cascading constraints exist; handle exceptions accordingly.

Best Practices
--------------

- Perform queries with care and review the list of objects to delete before calling ``.delete()``.
- Consider backing up data before bulk deletion.
- When deleting Templates, consider recursively deleting or archiving child Templates and related Items.
- Use transaction management to ensure atomicity for bulk deletes in complex workflows.

Summary
-------

Deletion APIs in Serverless ADR provide flexible, efficient removal of report-related objects to keep your reporting system clean and relevant.

Next Steps
----------

Explore the :doc:`copying_objects` guide to learn how to safely duplicate report content across databases.
