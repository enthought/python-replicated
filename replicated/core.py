#  Copyright (c) 2016 by Enthought, Inc.
#  All rights reserved.
import enum
import json

import ruamel.yaml

from attr import attributes, attr
from requests.utils import default_user_agent as requests_user_agent
import requests
import six

from . import __version__
from .exceptions import ReplicatedError


def default_user_agent(base=None):
    """Create the default User-Agent string for the python-replicated
    client.

    Parameters
    ----------
    base : str
        The User-Agent string to extend.  The default is the
        ``python-requests`` User-Agent.

    """
    if base is None:
        base = requests_user_agent()
    return 'python-replicated/{0} {1}'.format(__version__, base)


class NewReleaseSource(enum.Enum):
    """The source of configuration for a new release.

    """

    #: Create a new empty release.
    none = None

    #: Create a new release as a copy of the latest release.
    latest = 'latest'


@attributes
class App(object):
    """A Replicated-based application.

    """

    #: The application ID.
    id = attr(repr=False)

    #: The name of the application
    name = attr()

    # The slug of the application
    slug = attr(repr=False)

    # The application's channels
    channels = attr()

    # The API URL of the application
    url = attr(repr=False, hash=False, cmp=False)

    #: INTERNAL: The requests Session used when making requests on the
    #: application.
    _session = attr(cmp=False, repr=False, hash=False, init=False)

    @classmethod
    def from_json(cls, app_channels_json, session=None):
        """Create a new :class:`~App` instance from JSON returned by the
        Replicated API.

        Parameters
        ----------
        app_channels_json : dict
            The parsed JSON response of the Replicated API.  This must
            contain an ``App`` element and a ``Channels`` element.
        session : requests.Session
            The requests Session this :class:`~App` will use when
            making requests.

        """
        app_json = app_channels_json['App']
        id = app_json['Id']
        name = app_json['Name']
        slug = app_json['Slug']
        url = ReplicatedVendorAPI.base_url + '/app/{0}'.format(id)
        instance = cls(
            id=id,
            name=name,
            slug=slug,
            url=url,
            channels=(),
        )

        channels = tuple(
            Channel.from_json(ch, app=instance, session=session)
            for ch in app_channels_json['Channels'])
        instance.channels = channels
        instance._session = session

        return instance

    @property
    def releases(self):
        """Query the application releases.

        This is an iterable that will retrieve the specified subset of
        :class:`~Release` objects.

        To retrieve the full list of releases, use the full-slice
        notation::

            >>> app.releases[:]

        or::

            >>> list(app.releases)

        To retrieve a subset of releases, slice the iterable as usual::

            >>> app.releases[2:4]

        """
        return ReleasesSlice(self, self._session)

    @property
    def licenses(self):
        """List the licenses associated with the application.

        """
        url = self.url + '/licenses'
        response = self._session.get(url)
        if response.status_code != 200:
            raise ReplicatedError(response.text)
        response_json = response.json()
        channels = {ch.id: ch for ch in self.channels}
        return [
            License.from_json(
                item, app=self, session=self._session,
                channel=channels[item['ChannelId']])
            for item in response_json
        ]

    def create_release(self, source=NewReleaseSource.latest):
        """Create a new :class:`~Release`.

        By default (when ``source`` is
        :class:`~NewReleaseSource.latest`) this will create a new
        release with configuration based on the latest release. This
        is the same behaviour as the Replicated Vendor web interface..

        If ``source`` is :attr:`~NewReleaseSource.none`, then the new
        release will have an empty configuration..

        If ``source`` is an instance of :class:`~Release`, then that
        release will be used as the source of the configuration.

        Parameters
        ----------
        source : NewReleaseSource : Release
            The source of configuration for the new release.

        """
        if not isinstance(source, (NewReleaseSource, Release)):
            raise ValueError(
                'Expected a NewReleaseSource or Release, '
                'got {0}: {1!r}'.format(
                    type(source), source))
        url = self.url + '/release'
        data = {}
        if source == NewReleaseSource.latest:
            data['source'] = source.value
        elif isinstance(source, Release):
            data['source'] = 'copy'
            data['sourcedata'] = source.sequence
        response = self._session.post(
            url,
            data=json.dumps(data),
            headers={'Content-Type': 'application/json'},
        )
        if response.status_code != 201:
            raise ReplicatedError(response.text)
        response_json = response.json()

        new_release, = self.releases[:1]
        assert new_release.sequence == response_json['Sequence']
        return new_release

    def create_channel(self, name):
        """Create a new channel.

        Parameters
        ----------
        name : str
            The name of the channel to create.

        """
        try:
            next(ch for ch in self.channels if ch.name == name)
        except StopIteration:
            pass
        else:
            raise RuntimeError('Channel {} already exists'.format(name))

        url = self.url + '/channel'
        data = {'name': name}
        response = self._session.post(
            url,
            data=json.dumps(data),
            headers={'Content-Type': 'application/json'},
        )
        if response.status_code != 200:
            raise ReplicatedError(response.text)
        response_json = response.json()
        self.channels = channels = tuple(
            Channel.from_json(ch, app=self, session=self._session)
            for ch in response_json)

        try:
            return next(ch for ch in channels if ch.name == name)
        except StopIteration:
            raise ValueError('Channel {} not created'.format(name))


@attributes
class Channel(object):
    """A distribution channel for an :class:`~App`.

    """

    #: The channel ID.
    id = attr(repr=False)

    #: The name of the channel
    name = attr()

    #: The position of the channel in the channels list.
    position = attr(repr=False)

    #: The sequence number of the current release available through
    #: the channel.
    release_sequence = attr(repr=False)

    #: The version number of the current release available through
    #: the channel.
    release_label = attr(repr=False)

    #: The release notes of the current release available through
    #: the channel.
    release_notes = attr(repr=False)

    #: The app that owns this channel.
    app = attr(repr=False)

    #: INTERNAL: The requests Session used when making requests on the
    #: channel.
    _session = attr(cmp=False, repr=False, hash=False, init=False)

    @classmethod
    def from_json(cls, channel_json, app, session=None):
        """Create a new :class:`~Channel` instance from JSON returned by the
        Replicated API.

        Parameters
        ----------
        channel_json : dict
            The parsed JSON response from the Replicated API.
        app : App
            The :class:`~App` that owns this :class:`~Channel`.
        session : requests.Session
            The requests Session this :class:`~Channel` will use when
            making requests.

        """
        instance = cls(
            id=channel_json['Id'],
            name=channel_json['Name'],
            position=channel_json['Position'],
            release_sequence=channel_json['ReleaseSequence'],
            release_label=channel_json['ReleaseLabel'],
            release_notes=channel_json['ReleaseNotes'],
            app=app,
        )
        instance._session = session
        return instance

    @property
    def url(self):
        """The URL for the channel.

        """
        return self.app.url + '/channel/{0}'.format(self.id)

    def create_license(self, assignee, update_policy=None):
        """

        """
        licenses = self.app.licenses
        try:
            next(l for l in licenses
                 if l.assignee == assignee and l.channel == self)
        except StopIteration:
            pass
        else:
            raise ValueError(
                'License already exists for {} and channel {}'.format(
                    assignee, self))

        if update_policy is None:
            update_policy = License.UpdatePolicy.manual
        url = ReplicatedVendorAPI.base_url + '/license'
        data = {
            'app_id': self.app.id,
            'channel_id': self.id,
            'update_policy': update_policy.value,
            'require_activation': False,
            'assignee': assignee,
            'expiration_policy': 'ignore',
        }
        response = self._session.post(
            url, data=json.dumps(data),
            headers={'Content-Type': 'application/json'})
        if response.status_code != 201:
            raise ReplicatedError(response.text)
        return License.from_json(
            response.json(), app=self.app, channel=self, session=self._session)


@attributes
class Release(object):
    """A release of an application.

    """

    #: The application represented by this release.
    app = attr(repr=False)

    #: The sequence number of the release.
    sequence = attr()

    #: The version number of the release.
    version = attr()

    #: Is the release still editable?
    editable = attr(repr=False)

    #: The create time of the release.
    created_at = attr(repr=False)

    #: The time at which the release was last edited.
    edited_at = attr(repr=False)

    #: Which channels the release is currently available through.
    active_channels = attr(repr=False)

    #: INTERNAL: The requests Session used when making requests on the
    #: release.
    _session = attr(cmp=False, repr=False, hash=False, init=False)

    #: INTERNAL: a caching optimization for the release configuration.
    _config = attr(default=None, cmp=False, repr=False, hash=False)

    @classmethod
    def from_json(cls, release_json, app, session=None):
        """Create a new :class:`~Release` from JSON returned by the Replicated
        API.

        Parameters
        ----------
        release_json : dict
            The parsed JSON response from the Replicated API.
        app : App
            The :class:`~App` that owns this :class:`~Release`.
        session : requests.Session
            The requests Session this :class:`~Release` will use when
            making requests.

        """
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
        """The URL for the release.

        """
        return self.app.url + '/{0}'.format(self.sequence)

    @property
    def config(self):
        """The release configuration YAML.

        """
        if self._config is None:
            self.refresh()
        return self._config

    @config.setter
    def config(self, new_yaml):
        """Update the release configuration YAML.

        """
        if not isinstance(new_yaml, six.text_type):
            raise ValueError('Expected unicode text')
        self._config = None
        url = self.url + '/raw'
        yaml_data = ruamel.yaml.load(new_yaml)
        version = yaml_data.get('version', '')
        response = self._session.put(
            url,
            data=new_yaml,
            headers={'Content-Type': 'application/yaml'},
        )
        if response.status_code != 200:
            raise ReplicatedError(response.text)
        self.version = version
        self.refresh()

    def refresh(self):
        """Refresh the mutable attributes of the release after a configuration
        change.

        """
        url = self.url + '/properties'
        response = self._session.get(url)
        if response.status_code != 200:
            raise ReplicatedError(response.text)
        response_json = response.json()
        self._config = response_json['Config']
        self.created_at = response_json['CreatedAt']
        self.edited_at = response_json['EditedAt']

    def archive(self):
        """Archive the release.

        """
        url = self.url + '/archive'
        response = self._session.post(url)
        if response.status_code != 204:
            raise ReplicatedError(response.text)

    def promote(self, channels, required=True, release_notes=None, label=None):
        """Promote the release to one or more channels.

        Parameters
        ----------
        channels : list
            The channels to which to promote the release.
        required : bool
            ``True`` (default) if the release will be a required
            upgrade for customers.
        release_notes : str
            The release notes for the release. If this is omitted,
            then the release notes specified in the release
            configuration will be used.
        label : str
            The release label (version) for the release. If this is
            omitted, then the version specified in the release
            configuration will be used.

        """
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
        if response.status_code != 204:
            raise ReplicatedError(response.text)


class ReleasesSlice(object):
    """A helper object to query a sequence of releases from the Replicated
    API.

    See :attr:`replicated.core.App.releases`

    """

    def __init__(self, app, session):
        """Create a :class:`~ReleasesSlice`.

        Parameters
        ----------
        app : App
            The application to query for releases.
        session : requests.Session
            The requests Session to use for querying the Replicated API.

        """
        self.app = app
        self._session = session

    def __getitem__(self, key):
        """Fetch a sequence of releases.

        Parameters
        ----------
        key : slice
            The sequence of releases to fetch.  This must be a
            :class:`~slice` with ``step`` unset or ``1``.  If ``stop``
            is ``None``, then whole set of :class:`~Release` is
            fetched.

        """
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
        if response.status_code != 200:
            raise ReplicatedError(response.text)
        releases_json = response.json()

        if key.stop is not None:
            releases_json = releases_json['releases']

        return [
            Release.from_json(item, self.app, self._session)
            for item in releases_json
        ]

    def __iter__(self):
        """Fetch all releases and iterate over them.

        """
        return iter(self[:])


@attributes
class License(object):
    id = attr(repr=False)
    app = attr(repr=False)
    channel = attr(repr=False)
    assignee = attr()
    update_policy = attr(repr=False)
    archived = attr(repr=False)
    grant_date = attr(repr=False)
    expire_date = attr(repr=False)
    expiration_policy = attr(repr=False)
    revokation_date = attr(repr=False)
    anonymous = attr(repr=False)
    field_values = attr(repr=False)
    billing = attr(repr=False)
    require_activation = attr(repr=False)
    activation_email = attr(repr=False)
    last_sync = attr(repr=False)
    inactive_instance_count = attr(repr=False)
    active_instance_count = attr(repr=False)
    untracked_instance_count = attr(repr=False)
    is_instance_tracked = attr(repr=False)
    _session = attr(cmp=False, repr=False, hash=False, init=False)

    class UpdatePolicy(enum.Enum):
        manual = 'manual'
        automatic = 'automatic'
        none = "none"

    @classmethod
    def from_json(cls, license_json, app, channel, session):
        """

        """
        assert license_json['AppId'] == app.id
        assert license_json['ChannelId'] == channel.id
        instance = cls(
            id=license_json['Id'],
            app=app,
            channel=channel,
            assignee=license_json['Assignee'],
            update_policy=cls.UpdatePolicy[license_json['UpdatePolicy']],
            archived=license_json['Archived'],
            grant_date=license_json['GrantDate'],
            expire_date=license_json['ExpireDate'],
            expiration_policy=license_json['ExpirationPolicy'],
            revokation_date=license_json['RevokationDate'],
            anonymous=license_json['Anonymous'],
            field_values=license_json['FieldValues'],
            billing=license_json['Billing'],
            require_activation=license_json['RequireActivation'],
            activation_email=license_json['ActivationEmail'],
            last_sync=license_json['LastSync'],
            inactive_instance_count=license_json['InactiveInstanceCount'],
            active_instance_count=license_json['ActiveInstanceCount'],
            untracked_instance_count=license_json['UntrackedInstanceCount'],
            is_instance_tracked=license_json['IsInstanceTracked'],
        )
        instance._session = session
        return instance

    @property
    def value(self):
        """The license key value.

        """
        url = ReplicatedVendorAPI.base_url + '/licensekey/{}'.format(self.id)
        response = self._session.get(url)
        if response.status_code != 200:
            raise ReplicatedError(response.text)
        return response.content.decode()


class ReplicatedVendorAPI(object):
    """The entry-point into the Replicated Vendor API.

    """

    #: The base URL of all Vendor API calls.
    base_url = 'https://api.replicated.com/vendor/v1'

    def __init__(self, token):
        """Create a :class:`~ReplicatedVendorAPI` instance.

        Parameters
        ----------
        token : str
            The Replicated API token used for authentication.

        """
        self.session = requests.Session()
        self.session.headers['User-Agent'] = default_user_agent()
        self.session.headers['Authorization'] = token

    def get_apps(self):
        """Get a list of all :class:`replicated.core.App` instances.

        """
        url = self.base_url + '/apps'
        response = self.session.get(url)
        if response.status_code != 200:
            raise ReplicatedError(response.text)
        apps_json = response.json()

        return [App.from_json(item, session=self.session)
                for item in apps_json]
