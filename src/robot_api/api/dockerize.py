# -*- coding: utf8 -*-
""" Docker wrapper

Build docker images and containers using templates for Dr.ROBOT

Attributes:
    _docker_options (dict): docker options for template provided from config.json
    _default_config_path (str): location of template file
    _active_config_path (str): location of active Dockerfile
    verbose (bool): More output Yes/No
    container (docker.Container): container object when running
    status (str): If running or not
    name (str): name of docker image
"""
from os.path import isfile
from string import Template
import logging
import time
import json
import multiprocessing
from tqdm import tqdm
import docker
from docker.errors import APIError, BuildError, ContainerError, ImageNotFound, NotFound

LOG = logging.getLogger(__name__)


class Docker:
    def __init__(self, **kwargs):
        """Constructor

        Args:
            **kwargs:
                docker_options : (Dict) of arguments to build docker with (name, descriptions, output)
                active_config_path: (String) filepath of config to use for "active" configuration
                default_config_path: (String) filepath of config to use as default template.
                output_dir: (String) output directory to mount on docker

        Returns:

        """
        self._docker_options = kwargs.get('docker_options', None)

        self._default_config_path = kwargs.get('default_config_path', None)
        self._active_config_path = kwargs.get('active_config_path', None)
        self.name = self._docker_options['name']
        self.network_mode = self._docker_options.get('network_mode', 'host')

        self.verbose = kwargs.get('verbose', False)
        self.client = docker.from_env()
        self.image = None
        self.container = None
        self.status = None
        self.error = False
        self.done_building = False

        self.OUTPUT_DIR = kwargs.get('output_dir', None)

    def _print(self, msg):
        if self.verbose:
            print("[D] " + msg)
        LOG.debug(msg)

    def kill(self):
        """Kills container

        Tries to kill container.

        """
        try:
            self.container.kill()
        except docker.errors.APIError:
            self._print(
                "Error when trying to send kill signal to docker container.")
            LOG.exception("Killing container")

    def _init_config(self):
        """Creates active configuration from template

        Raises:
            OSError
        """
        if isfile(self._default_config_path):
            LOG.info("Creating Dockerfile for %s", self._docker_options['name'])
        elif not isfile(self._default_config_path):
            raise OSError(
                'Default configuration file is not found, please fix')

        self._print(f"Making config with args:{json.dumps(self._docker_options, indent=4)}")

        with open(self._default_config_path, 'r') as cfg:
            t = Template(cfg.read())
        with open(self._active_config_path, 'w') as out:
            out.write(t.safe_substitute({k: v if
                                         v else '\'\''
                                         for k, v
                                         in self._docker_options.items()
                                         }))

    def build(self):
        """
        Generates docker image from active_config

        Args:

        Returns:

        """
        try:
            self._init_config()
            self._print(f"""Built with options:
                            -f {self._active_config_path}
                            -t {self._docker_options['docker_name']}:{self._docker_options['docker_name']}
                            --rm
                            --network {self.network_mode}
                        """)
            with open(self._active_config_path, 'rb') as _file:
                self.image = self.client.images.build(fileobj=_file,
                                                 tag=f"{self._docker_options['docker_name']}:{self._docker_options['docker_name']}",
                                                 rm=True,
                                                 network_mode=self.network_mode,
                                                 use_config_proxy=True)

            self.done_building = True
        except BuildError as error:
            print(f"[!] Build Error {self.name}. Check logs")
            LOG.exception("[!] BuildError: %s", self.name)
            self.error = True
            if "net/http" in str(error):
                print("[!] This could be a proxy issue, see " +
                      "https://docs.docker.com/config/daemon/systemd/#httphttps-proxy for help")
        except APIError:
            print(f"[!] APIError: {self.name}")
            LOG.exception("[!] APIError: %s", self.name)
            self.error = True
        except KeyError:
            print(f"[!] KeyError Output or Docker Name " +
                  "is not defined!!: {scanner.name}")
            LOG.exception("[!] KeyError Output or Docker Name " +
                          "is not defined!!: %s", self.name)
            self.error = True
        except OSError:
            LOG.exception("[!] Output directory could not be created, " +
                          "please verify permissions")
            self.error = True

    def run(self):
        """
        Builds and runs docker container.

        Args:

        Returns:

        """

        try:
            volumes = self._docker_options.get("volumes", None)
            if volumes is None:
                volumes = {
                    self.OUTPUT_DIR: {
                        'bind': self._docker_options['output'],
                        'mode': 'rw'
                    }
                }
            self.container = self.client.containers.run(
                image=f"{self._docker_options['docker_name']}:{self._docker_options['docker_name']}",
                # dns=[self._docker_options.get('dns')] if self._docker_options.get('dns', None) else None, # REMOVED in latest due to issues :/
                auto_remove=True,
                tty=True,
                detach=True,
                network_mode=self.network_mode,
                command=self._docker_options.get(
                    'command',
                    None),
                ports=self._docker_options.get(
                    'ports',
                        None),
                volumes=volumes)

            self.status = self.container.status

            self._print(f"mount point specified here: {volumes}")

        except ImageNotFound:
            self.error = True
            print(f"[!] ImageNotFound: {self.name}")
            LOG.exception("[!] ImageNotFound: %s", self.name)
        except ContainerError:
            self.error = True
            print(f"[!] Container Error: {self.name}")
            LOG.exception("[!] Container Error: %s", self.name)
        except APIError:
            self.error = True
            print(f"[!] APIError: {self.name}")
            LOG.exception("[!] APIError: %s", self.name)
        except KeyError:
            self.error = True
            print(f"[!] KeyError Output or Docker Name " +
                  "is not defined!!: {scanner.name}")
            LOG.exception("[!] KeyError Output or Docker Name " +
                          "is not defined!!: %s", self.name)
        except OSError:
            self.error = True
            LOG.exception("[!] Output directory could not be created, " +
                          "please verify permissions")

    def monitor_build(self):
        """Monitor build status of docker

        """
        multiprocessing.Process(target=self.build(), daemon=True)
        with tqdm() as pbar:
            pbar.set_description(f"[#] Docker image {self.name}, building...")
            while self.image is None and not self.error and not self.done_building:
                time.sleep(2)
                pbar.update(1)

    def update_status(self):
        """
        Thread watcher to update status of container

        Args:

        Returns:

        """
        if self.error:
            return
        try:
            with tqdm() as pbar:
                pbar.set_description(
                    f"[#] Docker container {self.name}, running...")
                while True:
                    self.container.reload()
                    time.sleep(2)
                    self.status = self.container.status
                    pbar.update(1)

        except NotFound:
            self._print(f"[*] Docker container {self._docker_options['docker_name']} exited")
            self.status = 'exited'
        except AttributeError:
            LOG.exception("AttributeError in update_status. Check logs")
        except KeyboardInterrupt:
            LOG.exception("KeyboardInterrupt in update_status. Check logs")
            self.kill()
