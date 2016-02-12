from attr import attributes, attr
from requests.utils import default_user_agent as requests_user_agent
import requests


__version__ = '0.0.1'


def default_user_agent(base=None):
    if base is None:
        base = requests_user_agent()
    return 'python-replicated/{0} {1}'.format(__version__, base)


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
