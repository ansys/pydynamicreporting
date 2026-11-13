
ADR as a Local Docker Image (Linux Template)
--------------------------------------------

This template shows how to package an existing, licensed ADR installation in a
local Linux Docker image. PyDynamicReporting does not provide a public ADR
image.

Before using the template:

* Install and license ADR.
* Install Docker and ensure that the Docker daemon is available.
* Copy the ADR installation directory into the Docker build context as
  ``ADR/``. Current images place this directory at ``/Nexus/ADR``.

PyDynamicReporting also recognizes the legacy ``/Nexus/CEI`` layout, but it
looks for ``/Nexus/ADR`` first.

Dockerfile
^^^^^^^^^^

Save the following content as ``Dockerfile`` in the directory that contains the
``ADR/`` installation directory:

.. code::

    # stage 1
    FROM buildpack-deps as temp

    RUN mkdir /Nexus
    WORKDIR /Nexus
    COPY ADR /Nexus/ADR

    # stage 2
    FROM buildpack-deps

    ENV PYTHONUNBUFFERED="1"

    RUN apt-get update
    # Install pre-requisite packages.
    RUN apt-get install -y wget apt-transport-https libgl1 fontconfig && apt-get clean

    RUN apt-get update && apt-get install -y \
        libx11-xcb1 \
        libxcb1 \
        libxcb-glx0 \
        libxcb-keysyms1 \
        libxcb-image0 \
        libxcb-shm0 \
        libxcb-icccm4 \
        libxcb-sync1 \
        libxcb-xfixes0 \
        libxcb-shape0 \
        libxcb-randr0 \
        libxcb-render-util0 \
        libxcb-xinerama0 \
        libxcb-util1 \
        libxcb-xkb1

    # Set up the default group.
    RUN addgroup nobody && adduser nobody nobody

    RUN mkdir /Nexus
    COPY --from=temp /Nexus /Nexus
    # Create a database directory.
    RUN mkdir -p /Nexus/DatabaseDir

Build image
^^^^^^^^^^^
Build the image from the directory containing ``Dockerfile`` and ``ADR/``.
Replace ``your-adr-image`` with a local image name:

.. code::

   docker build -t your-adr-image:latest -f Dockerfile .

Run image
^^^^^^^^^
To inspect the image independently of PyDynamicReporting:

.. code::

    docker run --rm -it your-adr-image:latest

Use the local image with ``Service``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Provide the image explicitly and set ``ansys_installation="docker"``. The data
and database directories must be writable host directories. Use an empty
database directory when creating a database.

.. code:: python

    import ansys.dynamicreporting.core as adr

    adr_service = adr.Service(
        ansys_installation="docker",
        docker_image="your-adr-image:latest",
        data_directory="/tmp/adr-work",
        db_directory="/tmp/adr-database",
    )

When the container starts, PyDynamicReporting reads the product version from
the discovered launcher. It emits a compatibility warning if that version is
outside the supported ``26.*`` and ``27.*`` annual product lines.
