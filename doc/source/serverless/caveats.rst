Caveats
=======

Multiprocessing / Multithreading Usage
--------------------------------------

When using Serverless ADR in applications that involve multiple processes or threads,
Serverless ADR modifies the Python process environment and dynamically loads
required modules from the Ansys installation during setup. Because of this design,
proper initialization and lifecycle management are critical when using Serverless ADR
in applications involving multiple processes or threads.

Process-Level Initialization
----------------------------

- The ``ADR.setup()`` method configures Serverless ADR for the **entire process**.
- When your application uses multiprocessing (e.g., the ``multiprocessing`` module,
  Gunicorn workers, or other process-based concurrency), **each process must call**
  ``ADR.setup()`` before accessing Serverless ADR features.
- If ``setup()`` is not called in a new process, ADR APIs will fail or behave
  unpredictably due to missing environment configuration.

Example: Multiprocessing with Serverless ADR

.. code-block:: python

    import multiprocessing
    from ansys.dynamicreporting.core.serverless import ADR


    def worker_task():
        adr = ADR.get_instance()
        if not adr.is_setup:
            adr.setup()
        # Proceed with Serverless ADR API calls here


    if __name__ == "__main__":
        adr = ADR(ansys_installation="/path/to/ansys", db_directory="/path/to/db")
        adr.setup()

        # Spawn new processes
        processes = []
        for _ in range(4):
            p = multiprocessing.Process(target=worker_task)
            p.start()
            processes.append(p)

        for p in processes:
            p.join()

Thread-Level Behavior
---------------------

- Serverless ADR configuration applies process-wide and is shared by all threads.
- It is unnecessary and discouraged to call ``ADR.setup()`` multiple times within the
  same process.
- Ensure the main thread calls ``ADR.setup()`` **before spawning any threads** that
  will use Serverless ADR.
- Calling ``setup()`` concurrently or repeatedly from multiple threads can cause
  race conditions or inconsistent environment state.

Example: Threading with Serverless ADR

.. code-block:: python

    import threading
    from ansys.dynamicreporting.core.serverless import ADR


    def thread_task():
        adr = ADR.get_instance()
        # ADR is already setup in main thread, so just use it directly
        # Make ADR API calls here


    if __name__ == "__main__":
        adr = ADR(ansys_installation="/path/to/ansys", db_directory="/path/to/db")
        adr.setup()  # Call once in main thread before starting other threads

        threads = []
        for _ in range(4):
            t = threading.Thread(target=thread_task)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

Using Subprocesses for Multiple Configurations
----------------------------------------------

Problem
~~~~~~~

``ADR.setup()`` configures Serverless ADR at the **process level** and some components
cache configuration (paths, URLs, etc.) when first loaded. After a process is set up,
attempting to **reconfigure** that same process to different ``db_directory``,
``media_directory``, or ``static_directory`` values can lead to conflicts or
unpredictable behavior.

Why a subprocess fixes it
~~~~~~~~~~~~~~~~~~~~~~~~~

Each subprocess has its **own** interpreter and process-wide state. Running ADR in a
subprocess lets you start with a **fresh configuration**, do the work, and exit—no
state leaks between runs. This is the simplest, most reliable way to use different
directories within one overall application.

Minimal example
~~~~~~~~~~~~~~~

Child script (fresh ADR per run):

.. code-block:: python

    # run_task.py
    import os
    from ansys.dynamicreporting.core.serverless import ADR, String

    if __name__ == "__main__":
        adr = ADR(
            ansys_installation=os.environ.get("ANSYS_INSTALLATION", "/path/to/ansys"),
            db_directory=os.environ.get("ADR_DB_DIR", "/tmp/adr_db"),
            media_directory=os.environ.get("ADR_MEDIA_DIR", "/tmp/adr_media"),
            static_directory=os.environ.get("ADR_STATIC_DIR", "/tmp/adr_static"),
        )
        adr.setup()
        # Example work: create an item or render/export a report
        adr.create_item(String, name="intro", content="It's alive!", tags="example=1")
        print("OK")

Parent process (run different configs safely):

.. code-block:: python

    import os
    import subprocess
    import sys

    # Config A
    env_a = os.environ.copy()
    env_a.update({
        "ADR_DB_DIR": "/srv/tenantA/db",
        "ADR_MEDIA_DIR": "/srv/tenantA/media",
        "ADR_STATIC_DIR": "/srv/tenantA/static",
        "ANSYS_INSTALLATION": "/opt/ansys/v252",
    })
    subprocess.run([sys.executable, "run_task.py"], check=True, env=env_a)

    # Config B (same parent process, isolated child)
    env_b = os.environ.copy()
    env_b.update({
        "ADR_DB_DIR": "/srv/tenantB/db",
        "ADR_MEDIA_DIR": "/srv/tenantB/media",
        "ADR_STATIC_DIR": "/srv/tenantB/static",
        "ANSYS_INSTALLATION": "/opt/ansys/v252",
    })
    subprocess.run([sys.executable, "run_task.py"], check=True, env=env_b)

Guidelines
~~~~~~~~~~

- Treat ``ADR.setup()`` as **one-time per process**.
- To use different database/media/static directories in the same application, **spawn a subprocess** per configuration.
- Keep child scripts small: set directories, call ``setup()``, do the work, exit.
- On Windows, ensure subprocess entry points are guarded with ``if __name__ == "__main__":``.

Serverless ADR Usage Within Django Apps
---------------------------------------

- Serverless ADR internally configures Django settings and environment variables at the
  process level during ``ADR.setup()``.
- Because Django settings are designed to be configured once per process, **attempting
  to initialize Serverless ADR inside an existing Django application causes conflicts.**
- Specifically, setting up Serverless ADR tries to configure Django a second time, which
  is unsupported and results in errors or unpredictable behavior.
- This means **embedding or using Serverless ADR as a Django app within another Django
  project is not currently supported and strongly discouraged.**
- If you require integration, consider separating Serverless ADR usage into a dedicated
  process or microservice to avoid Django settings conflicts.

Summary and Best Practices
--------------------------

- Always call ``ADR.setup()`` once at the application startup or entry point.
- In multiprocessing scenarios, call ``setup()`` separately in each spawned process.
- Avoid calling ``setup()`` multiple times or concurrently within the same process.
- Share the ADR instance across threads within a process after setup completes.
- Avoid embedding Serverless ADR within other Django apps due to Django configuration conflicts.
- If unsure whether setup is needed, check ``adr.is_setup`` before calling.

By following these guidelines, you ensure stable and consistent Serverless ADR usage
in complex multi-threaded or multi-process environments without risking Django conflicts.
