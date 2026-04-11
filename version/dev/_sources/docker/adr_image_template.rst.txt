
ADR as a Local Docker Image (Linux Template)
--------------------------------------------
Below, you will find instructions on how ADR can be run via Docker using the provided Docker image template.

**Prerequisite**: Before using this template, Ansys software must be installed and licensed on your local machine.
Additionally, Docker must be installed and accessible on the system.

Dockerfile
^^^^^^^^^^

This command requires a working CEI installation and must be run from the same directory in which the CEI/ folder exists.

.. code::

    # stage 1
    FROM buildpack-deps as temp

    RUN mkdir /Nexus
    WORKDIR /Nexus
    COPY CEI /Nexus/CEI

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

    # Set up default group
    RUN addgroup nobody && adduser nobody nobody

    RUN mkdir /Nexus
    COPY --from=temp /Nexus /Nexus
    # the database
    RUN mkdir -p /Nexus/DatabaseDir

Build image
^^^^^^^^^^^
Please note that the Dockerfile must be saved beforehand.
Once saved, you can build the Docker image by running the below build command from the directory containing the Dockerfile.

.. code::

   docker build -t adr-local -f Dockerfile .

Run image
^^^^^^^^^
If Ansys software is already installed and licensed on your local machine:

.. code::

    docker run adr-local

Local ADR Docker image to be used via adr_service.py
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

    import ansys.dynamicreporting.core as adr
    adr_service = adr.Service(docker_image="adr-local:latest")