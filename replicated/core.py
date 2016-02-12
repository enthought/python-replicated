#  Copyright (c) 2015 by Enthought, Inc.
#  All rights reserved.
import enum
import json
import yaml

from attr import attributes, attr
from requests.utils import default_user_agent as requests_user_agent
import requests
import six

from ._version import version as __version__


def default_user_agent(base=None):
    if base is None:
        base = requests_user_agent()
    return 'python-replicated/{0} {1}'.format(__version__, base)


class NewReleaseSource(enum.Enum):
    none = None
    latest = 'latest'
    copy = 'copy'


@attributes
class App(object):
    id = attr(repr=False)
    name = attr()
    slug = attr(repr=False)
    channels = attr()
    url = attr(repr=False, hash=False, cmp=False)
    _session = attr(cmp=False, repr=False, hash=False, init=False)

    @classmethod
    def from_json(cls, app_json, channels=(), session=None):
        id = app_json['Id']
        name = app_json['Name']
        slug = app_json['Slug']
        url = ReplicatedAPI.base_url + '/app/{0}'.format(id)
        instance = cls(
            id=id,
            name=name,
            slug=slug,
            url=url,
            channels=channels,
        )
        instance._session = session
        return instance

    @property
    def releases(self):
        return ReleasesSlice(self, self._session)

    def create_release(self, source=NewReleaseSource.none, copy=None):
        url = self.url + '/release'
        data = {}
        if source != NewReleaseSource.none:
            data['source'] = source.value
            if source == NewReleaseSource.copy:
                if copy is None:
                    raise ValueError(
                        'Copy specified but no source release provided')
                data['sourcedata'] = copy.sequence
        response = self._session.post(
            url,
            data=json.dumps(data),
            headers={'Content-Type': 'application/json'},
        )
        response.raise_for_status()
        response_json = response.json()

        new_release, = self.releases[:1]
        assert new_release.sequence == response_json['Sequence']
        return new_release


@attributes
class Channel(object):
    id = attr(repr=False)
    name = attr()
    position = attr(repr=False)
    release_sequence = attr(repr=False)
    release_label = attr(repr=False)
    release_notes = attr(repr=False)
    app = attr(repr=False)
    _session = attr(cmp=False, repr=False, hash=False, init=False)

    @classmethod
    def from_json(cls, channel, app, session=None):
        id = channel['Id']
        name = channel['Name']
        position = channel['Position']
        release_sequence = channel['ReleaseSequence']
        release_label = channel['ReleaseLabel']
        release_notes = channel['ReleaseNotes']
        instance = cls(
            id=id,
            name=name,
            position=position,
            release_sequence=release_sequence,
            release_label=release_label,
            release_notes=release_notes,
            app=app,
        )
        instance._session = session
        return instance

    @property
    def url(self):
        return self.app.url + '/channel/{0}'.format(id)


@attributes
class Release(object):
    app = attr(repr=False)
    sequence = attr()
    version = attr()
    editable = attr(repr=False)
    created_at = attr(repr=False)
    edited_at = attr(repr=False)
    active_channels = attr(repr=False)
    _session = attr(cmp=False, repr=False, hash=False, init=False)
    _config = attr(default=None, cmp=False, repr=False, hash=False)

    @classmethod
    def from_json(cls, release_json, app, session=None):
        app_id = release_json['AppId']
        assert app_id == app.id
        active_channel_ids = set(
            c['Id'] for c in release_json['ActiveChannels'])
        active_channels = [
            c for c in app.channels if c.id in active_channel_ids
        ]
        instance = cls(
            app=app,
            sequence=release_json['Sequence'],
            version=release_json['Version'],
            editable=release_json['Editable'],
            created_at=release_json['CreatedAt'],
            edited_at=release_json['EditedAt'],
            active_channels=active_channels,
        )
        instance._session = session
        return instance

    @property
    def url(self):
        return self.app.url + '/{0}'.format(self.sequence)

    @property
    def config(self):
        if self._config is None:
            self.refresh()
        return self._config

    @config.setter
    def config(self, new_yaml):
        if not isinstance(new_yaml, six.text_type):
            raise ValueError('Expected unicode text')
        self._config = None
        url = self.url + '/raw'
        yaml_data = yaml.load(new_yaml)
        version = yaml_data.get('version', '')
        response = self._session.put(
            url,
            data=new_yaml,
            headers={'Content-Type': 'application/yaml'},
        )
        response.raise_for_status()
        self.version = version
        self.refresh()

    def refresh(self):
        url = self.url + '/properties'
        response = self._session.get(url)
        response.raise_for_status()
        response_json = response.json()
        self._config = response_json['Config']
        self.created_at = response_json['CreatedAt']
        self.edited_at = response_json['EditedAt']

    def archive(self):
        url = self.url + '/archive'
        response = self._session.post(url)
        response.raise_for_status()

    def promote(self, channels, required=True, release_notes=None, label=None):
        url = self.url + '/promote'
        if len(channels) == 0:
            raise ValueError('Expected at least one channel')
        data = {
            'channels': [channel.id for channel in channels],
            'required': required,
        }
        if release_notes is not None:
            data['release_notes'] = release_notes
        if label is not None:
            data['label'] = label

        response = self._session.post(
            url,
            data=json.dumps(data),
            headers={'Content-Type': 'application/json'},
        )
        response.raise_for_status()


class ReleasesSlice(object):

    def __init__(self, app, session):
        self.app = app
        self._session = session

    def __getitem__(self, key):
        if not isinstance(key, slice):
            raise TypeError('Expected a slice')

        if key.step not in (None, 1):
            raise ValueError('Step size is not supported')
        if key.stop is None:
            suffix = '/releases'
        else:
            suffix = '/releases/paged?start={start}&count={stop}'.format(
                start=key.start or 0, stop=key.stop)

        url = self.app.url + suffix
        response = self._session.get(url)
        response.raise_for_status()
        releases_json = response.json()

        if key.stop is not None:
            releases_json = releases_json['releases']

        return [
            Release.from_json(item, self.app, self._session)
            for item in releases_json
        ]

    def __iter__(self):
        return iter(self[:])


class ReplicatedAPI(object):

    base_url = 'https://api.replicated.com/vendor/v1'

    def __init__(self, token):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = default_user_agent()
        self.session.headers['Authorization'] = token

    def get_apps(self):
        url = self.base_url + '/apps'
        response = self.session.get(url)
        response.raise_for_status()
        apps_json = response.json()

        apps = []
        for item in apps_json:
            app = App.from_json(item['App'], session=self.session)
            channels = tuple(
                Channel.from_json(ch, app=app, session=self.session)
                for ch in item['Channels'])
            app.channels = channels
            apps.append(app)
        return apps
