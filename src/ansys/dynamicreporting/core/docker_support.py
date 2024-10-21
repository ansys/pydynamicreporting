"""
Docker Support module.

The Docker Support module provides PyDnamicReporting with the ability to start
and stop the Ansys Dynamic Reporting Docker container as well as routines for
copying files between the host file system and the container's file system.

Examples:
    ::
        import ansys.dynamicreporting.core as adr
        d = adr.docker_support.DockerLauncher()
        d.pull()
        d.start()
        d.stop()
"""

import os
import random
import re
import string
from typing import Optional

from .constants import DOCKER_DEV_REPO_URL, DOCKER_REPO_URL


class DockerLauncher:
    """
    Creates a instance for interacting with a Nexus Docker container.

    The newly constructed instance doesn't do much itself. The significant
    functionally happens via object methods.

    Parameters
    ----------
    data_directory : str
        Directory to make into the container at ``/data``.
    docker_image_name : str, optional
        Name of the Docker image to use. The default is ``None``.
    use_dev : bool, optional
        Whether to use the latest ``ensight_dev`` Docker image. The
        default is ``False``. This parameter is overridden if a value
        is specified for the ``docker_image_name`` parameter.

    Examples:
        ::

            import ansys.dynamicreporting.core as adr
            d = adr.docker_support.DockerLauncher()
            d.pull()
            d.start(data_directory="D:\\data")
            d.stop()
    """

    def __init__(self, docker_image_name: Optional[str] = None, use_dev: bool = False) -> None:
        # the Docker container name
        self._container_name = None

        # the Ansys / EnSight version we found in the container
        # to be reassigned later
        self._ansys_version = None
        # CEI_HOME; to be reassigned later
        self._cei_home = None
        # nexus directory under CEI_HOME; to be reassigned later
        self._nexus_directory = None

        # reassigned by start()
        self._host_directory = None
        self._db_directory = None

        self._nexus_is_running = False
        self._delete_db_on_stop = False

        # get the optional user specified image name
        self._image_name = DOCKER_REPO_URL
        if use_dev:
            self._image_name = DOCKER_DEV_REPO_URL
        if docker_image_name:
            self._image_name = docker_image_name

        # Load up Docker from the user's environment
        try:
            import docker

            self._docker_client: docker.client.DockerClient = docker.from_env()
        except Exception:  # pragma: no cover
            raise RuntimeError("Can't initialize Docker")

    def pull(self) -> None:
        """
        Pulls the Docker image.

        Returns
        -------
        None

        Raises
        ------
        RuntimeError:
           If Docker couldn't pull the image.
        """
        try:
            self._docker_client.images.pull(self._image_name)
        except Exception:
            raise RuntimeError(f"Can't pull Docker image: {self._image_name}")

    def start(self, host_directory: str, db_directory: str, port: int) -> None:
        """
        Start the Docker container for Ansys Dynamic Reporting using a local image.

        The container runs in detached mode with ``/bin/bash`` as the entry point.
        This allows other tasks to be executed within the container.

        Parameters
        ----------
        host_directory : str
            Directory to map into the container as needed for copy methods.
        db_directory : str
            Directory for the Ansys Dynamic Reporting database.
        port: TCP port number for Ansys Dynamic Reporting.

        Returns
        -------
        None

        Raises
        ------
        ValueError:
            Bad argument.
        RuntimeError:
            Variety of error conditions.
        """

        if not host_directory:  # pragma: no cover
            raise ValueError("host_directory cannot be None.")
        if not db_directory:  # pragma: no cover
            raise ValueError("host_directory cannot be None.")

        self._host_directory = host_directory
        self._db_directory = db_directory
        self._port = port

        # Environment to pass into the container
        container_env = {
            "ANSYSLMD_LICENSE_FILE": os.environ["ANSYSLMD_LICENSE_FILE"],
        }

        # Ports to map between the host and the container
        ports_to_map = {str(self._port) + "/tcp": str(self._port)}

        # The data directory to map into the container
        data_volume = {
            self._host_directory: {"bind": "/host_directory", "mode": "rw"},
            self._db_directory: {"bind": "/db_directory", "mode": "rw"},
        }

        # get a unique name for the container to run
        existing_names = [x.name for x in self._docker_client.from_env().containers.list()]
        container_name = "nexus"
        while container_name in existing_names:
            container_name += random.choice(string.ascii_letters)
            if len(container_name) > 500:
                raise RuntimeError("Can't determine a unique Docker container name.")
        self._container_name = container_name

        # Start the container in detached mode and override
        # the default entrypoint so multiple commands can be
        # run within the container.
        #
        # we run "/bin/bash" as container user "ensight" in lieu of
        # the default entrypoint command "ensight" which is in the
        # container's path for user "ensight".

        try:
            self._container = self._docker_client.containers.run(
                self._image_name,
                entrypoint="/bin/bash",
                volumes=data_volume,
                environment=container_env,
                ports=ports_to_map,
                name=self._container_name,
                tty=True,
                detach=True,
            )
        except Exception as e:  # pragma: no cover
            raise RuntimeError("Can't run Docker container: " + self._image_name + "\n\n" + str(e))

        # Build up the command to run and send it to the container
        # as a detached command.
        #
        # Since we desire shell wildcard expansion, a modified PATH for user
        # "ensight", etc., we need to run as the primary command a shell (bash)
        # along with the argument "--login" so that ~ensight/.bashrc is sourced.
        # Unfortunately, we then need to use "-c" to mark the end of bash
        # arguments and the start of the command bash should run -- what we really
        # want to run.  This must be a string and not a list of stuff.  That means
        # we have to handle quoting.  Ugh.  Ultimately, it would be better to run
        # enshell instead of bash and then we can connect to it and do whatever we
        # want.

        # Get the path to /ansys_inc/vNNN/CEI/bin/nexus_launcher so we compute
        # CEI Home for our use here.  And, from this, get the Ansys version
        # number.

        cmd = ["bash", "--login", "-c", "ls /Nexus/CEI/nexus*/bin/nexus_launcher"]
        ret = self._container.exec_run(cmd)
        if ret[0] != 0:  # pragma: no cover
            self.stop()
            raise RuntimeError(
                "Can't find /Nexus/CEI/nexus*/bin/nexus_launcher in the Docker container.\n"
                + str(ret[1].decode("utf-8"))
            )
        p = ret[1].decode("utf-8").strip()
        i = p.find("CEI/")
        if i < 0:  # pragma: no cover
            self.stop()
            raise RuntimeError(
                "Can't find CEI/ in the Docker container.\n" + str(ret[1].decode("utf-8"))
            )
        self._cei_home = p[0 : i + 3]
        m = re.search(r"/nexus(\d\d\d)/", p)
        if not m:
            self.stop()
            raise RuntimeError(
                "Can't find version from cei_home in the Docker container.\n"
                + str(ret[1].decode("utf-8"))
            )
        self._ansys_version = m.group(1)
        # print("CEI_HOME =", self._cei_home)
        # print("Ansys Version =", self._ansys_version)
        self._nexus_directory = self._cei_home + "/nexus" + self._ansys_version

    def container_name(self) -> str:
        """
        Get the Docker container name.

        Returns
        =======
        str
            Name of the container or ``None`` if a container was not found.
        """
        return self._container_name

    def ansys_version(self) -> str:
        """
        Get the three-digit Ansys version from the Docker container.

        Returns
        -------
        str
            Three-digit Ansys version or ``None`` if this string was
            not found or the container was not started.
        """
        return self._ansys_version

    def cei_home(self) -> str:
        """
        Get the location of the ``CEI_HOME`` directory within the Docker container.

        Returns
        -------
        str
            Location of the ``CEI_HOME`` directory.
        """
        return self._cei_home

    def nexus_directory(self) -> str:
        """
        Get the location of the ``nexusNNN`` directory within the Docker container.

        Returns
        -------
        str
            Location of the ``nexusNNN`` directory.
        """
        return self._nexus_directory

    def run_in_container(self, cmd_line: str) -> str:
        """
        Run a command in the Docker container.

        Parameters
        ----------
        cmdLine: str
            Command to run in the Docker container.

        Returns
        -------
        str
            Output from the command.

        Raises
        ------
        RuntimeError
        """

        cmd = ["bash", "--login", "-c", cmd_line]
        # print("Running in the container: " + cmd_line)
        ret = self._container.exec_run(cmd)
        if ret[0] != 0:
            raise RuntimeError(
                "Can't run command within the container: "
                + cmd_line
                + "\n"
                + str(ret[1].decode("utf-8"))
            )
        return str(ret[1].decode("utf-8"))

    def ls_directory(
        self,
        directory: str,
    ) -> str:
        """
        Run the `'/bin/ls'` command on a directory in the Docker container.

        Parameters
        ----------
        directory: str
           Directory in the container to run the command on.

        Returns
        -------
        str
           Output from the command.

        Raises
        ------
        RuntimeError
        """

        ls_cmd = "/bin/ls " + directory
        return self.run_in_container(ls_cmd)

    def copy_from_cei_home_to_host_directory(
        self,
        src: str,
        do_recursive: bool = False,
    ) -> str:
        """
        Run the `'/bin/cp'` command in the Docker container on a source item.

        This command copies the source item locally to the ``host_directory``.

        Parameters
        ----------
        src: str
            Item (file or directory) within the container under the ``/Nexus/CEI/``
            directory.
        do_recursive: bool, optional
           Whether to use the `'/bin/cp -r'` command. The default is ``False``.

        Returns
        -------
        str
            Output from the command.

        Raises
        ------
        RuntimeError
        """

        cp_cmd = "/bin/cp "
        if do_recursive:
            cp_cmd += "-r "
        cp_cmd += self._cei_home + "/" + src
        cp_cmd += " "
        cp_cmd += "/host_directory/"
        return self.run_in_container(cp_cmd)

    def create_nexus_db(self) -> str:
        """
        Run the ``nexus_launcher create --db_directory <dir>`` in the Docker container.

        This command runs on the previously specified database directory.

        Returns
        -------
        str
            Output from the command.

        Raises
        ------
        RuntimeError
        """
        nexus_cmd = self._cei_home + "/bin/nexus_launcher create --db_directory /db_directory/ "
        return self.run_in_container(nexus_cmd)

    def launch_nexus_server(
        self,
        username: str,
        password: str,
        allow_iframe_embedding: bool,
    ) -> str:
        """
        Run the ``nexus_launcher start ...`` command in the Docker container.

        This command runs on the previously specified database directory.

        Parameters
        ----------
        username : str
            Username.
        password : str
            Password
        allow_iframe_embedding : bool
            Whether iframes must be allowed.

        Returns
        -------
        str
            Output from the command.

        Raises
        ------
        RuntimeError
        """
        nexus_cmd = self._cei_home + "/bin/nexus_launcher start"
        nexus_cmd += " --db_directory /db_directory"
        nexus_cmd += " --server_port "
        nexus_cmd += str(self._port)
        if allow_iframe_embedding:
            nexus_cmd += " --allow_iframe_embedding true"
        # nexus_cmd += " --username "
        # nexus_cmd += username
        # nexus_cmd += " --password "
        # nexus_cmd += password
        nexus_cmd += " &"
        ret = self.run_in_container(nexus_cmd)
        self._nexus_is_running = True
        return ret

    def stop(self) -> None:
        """Release any additional resources allocated during launching."""
        try:
            if self._nexus_is_running:
                self._nexus_is_running = False
                stop_cmd = self._cei_home + "/bin/nexus_launcher stop "
                stop_cmd += " --db_directory /db_directory"
                self.run_in_container(stop_cmd)
        except Exception as e:
            raise RuntimeWarning(
                f"Problem stopping and cleaning up Nexus service\n"
                f"in the Docker container.\n{str(e)}"
            )

        try:
            self._container.stop()
        except Exception as e:
            raise RuntimeWarning(f"Problem stopping the Docker container.\n{str(e)}")

        try:
            self._container.remove()
        except Exception as e:
            raise RuntimeWarning(f"Problem removing the Docker container.\n{str(e)}")

        self._container = None
