# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).


## [1.3.0] - August 2019

Updates

### Added

* Threading for docker containers
* CI/CD with travis to test building of containers
* MassDNS
* Certificate usage for all containers
* Minio docker-compose to serve up data locally for easy viewing
* Config files in $HOME/.drrobot!!!

### Removed

* Server for Dr.ROBOT
* Test directory. Most testing involves the network. Will eventually add unit tests again.

### Changed

* File layout
	* Broke up drrobot into multiple pieces: cli.py robot.py config.py
	* Moved robot specific classes into api folder: dockerize.py ansible.py aggregation.py upload.py web_resources.py
* Template files are not longer in same directory as filled in files
* Config and templates are stored in user $HOME/.drrobot directories for convenience
* Users can now use virtualenv or pipenv
* drrobot can now be installed locally for usage as a module

### Fixed

* Aggregation not parsing correctly
* Host/IP resolution error
* Redundant license
* Weird output with multiprocessing
* Logging

## [1.2.0] - August 2019

Updates

### Added

* **Django** docker container to server domain data
* Added dbfile option for specification of personal database
* **Webscreenshot** (Currently phantomjs receives the best results in Docker)
* **Altdns**
* **Slack** configuration. Requires you to set up a channel and make a robot with correct permissions similar to other Plugins.

### Removed

* Removed global domain option for all subparsers
* Removed domain requirement for upload

### Changed

* **SQLlite** refactor
    * Use two tables 1 for list of domains, 1 for all data gather. 
* Threading for reading files. Sometimes this threading would cause unknown hangs. Working on creating a more improved version of the file parsing.
* Minor packages updates for urllib3 and Jinja

### Fixed

* ValueError exception was not caught when building web tools. If you were missing a field  it would crash the program
* Amass Dockerfile
* Changes Knock to output CSV rather than Json
* KeyboardInterrupt when running docker containers caused error message. Now cancels gracefully.
* Slack client was updated. Changed code to reflect new client changes.

## [1.1.0] - Feb 2019 

Current Release

### Added

* Changelog :)

* **Nmap-screenshot** docker container which allows one to use the nmap screenshot NSE script
* **Knockpy** docker container added
* **Eyewitness** docker container added
* **Amass** docker container added 
* ```---verbosity``` flag added as well as some useful log files that should contain any exceptions and debugging information respectively.

### Removed

* ```--domain``` option in favor of required domain. (Can't run tool without domain)

### Changed

* Changed default configuration options
  * ```network_mode``` allows us to pass host network to the docker daemon for ease of use
  * ```DOCKER``` or ```ANSIBLE ``` mode for Scanners and Inspection tools. Change for what mode you would like them to utilize
  * Ansible configuration optoins
    * ```"flags": "-e '$extra' -i configs/ansible_inventory",``` This option allows you to have a **dr_robot** specific ansible inventory.
    * ```variable_user``` option to specify what user Ansible should use to log in 
* Changed folders for docker containers to *docker_buildfiles*
* Tests to utilize Travis CI 

### Fixed

* Updated Eyewitness to use a specific commit hash. ```--headless``` flag was removed in favor of ```--web```
* Added user created and generated files to ```.gitignore```
* Fixed Duplication of IP and Hostnames in the aggregated section 
* Duplicated docker containers showing up. 
* Docker containers running pass **Keyboard Interrupt**

## [1.0.0] - Nov  2018

Initial Release
