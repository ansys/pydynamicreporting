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
