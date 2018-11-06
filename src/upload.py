from mattermostdriver import Driver, exceptions
from abc import ABC, abstractmethod
import logging
import datetime
from os import walk, stat
from os.path import exists, abspath, dirname, isdir, splitext
from . import join_abs

class Forum(ABC):
    def __init__(self, **kwargs):
        """
        ABC class
        Args:
            **kwargs:
                api_key : (String) [Optional] api key for service
                username: (String) [Optional] username for service
                password: (String) [Optional] password for service
                url     : (String) [Optional] url for service
                domain  : (String) [Optional] domain for service

        """
        self.api_key = kwargs.get('api_key', None)
        self.username = kwargs.get('username', None)
        self.password = kwargs.get('password', None)
        self.url = kwargs.get('url', None)
        self.domain = kwargs.get('domain', None)

    @abstractmethod
    def upload(self, **kwargs):
        """
        Abstractmethod to be used in order to keep instantiation and execution simple in calling function
        Args:
            **kwargs: Any extra values needed for execution.

        Returns:

        """
        pass

class Mattermost(Forum):
    def __init__(self, **kwargs):
        """
        Initialize Mattermost class which extends Chat ABC
        Args:
            **kwargs: args to pass to Chat ABC
            team_channel : (String) required for posting to channel
            channel_name : (String) required for posting to channel
        """
        super().__init__(**kwargs)
        self.inst = Driver({
            'url' : self.url,
            'verify' : False,
            'token' : self.api_key,
            'username' : self.username,
            'port' : kwargs.get('port', 8065)
            })
        self.output_dir = kwargs.get("output_dir")
        self.team_name = kwargs.get("team_name", None)
        self.channel_name = kwargs.get("channel_name", None)
        self.filepath = kwargs.get("filepath", None)

    def _upload_files(self, file_location, channel_id):
        file_ids = []
        for root, dirs, files in walk(file_location):
            for filename in files:
                #TODO add optional parameters for adjusting size. Implement file splitting
                print(f"[...] Uploading {filename}")
                if stat(join_abs(root, filename)).st_size / 1024 ** 2 > 49:
                    print(f"[!]\tFile {filename} is to big, ignoring for now")
                    continue
                else:
                    file_ids += [self.inst.files.upload_file(channel_id=channel_id,
                        files={'files': (filename, open(join_abs(root, filename), 'rb'))}
                        )['file_infos'][0]['id']]
                    if len(file_ids) >= 5:
                        self.inst.posts.create_post(options={
                            'channel_id': channel_id,
                            'message': f"Recon Data {datetime.datetime.now()}",
                            'file_ids': file_ids
                            })
                        file_ids = []
        if len(file_ids) > 0:
            self.inst.posts.create_post(options={
                'channel_id': channel_id,
                'message': f"Recon Data {datetime.datetime.now()}",
                'file_ids': file_ids
                })
    
    def upload(self, **kwargs):
        """

        Args:
            **kwargs:
                filepath: (String) optional filepath to check for files to upload
        Returns:

        """
        print("[*] doing post message")
        try:
            self.inst.login()

            team_id = self.inst.teams.get_team_by_name(self.team_name)['id']
            channel_id = self.inst.channels.get_channel_by_name(channel_name=self.channel_name, team_id=team_id)['id']
        except exceptions.NoAccessTokenProvided as er:
            print(f"[!] NoAccessTokenProvided {er}")
            logging.error(er)
        except exceptions.InvalidOrMissingParameters as er:
            print(f"[!] InvalidOrMissingParameters {er}")
            logging.error(er)

        file_location = self.output_dir

        try:
            if self.filepath and exists(abspath(self.filepath)):
                file_location = abspath(self.filepath)

            self._upload_files(file_location, channel_id)

        except exceptions.ContentTooLarge as er:
            print(f"[!] ContentTooLarge {er}")
            logging.error(er)
        except exceptions.ResourceNotFound as er:
            print(f"[!] ResourceNotFound {er}")
            logging.error(er)
        except OSError as er:
            print(f"[!] File not found {er}")
            logging.error(er)
