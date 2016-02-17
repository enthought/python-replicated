from datetime import datetime

import click
import ruamel.yaml

from replicated.core import ReplicatedVendorAPI, NewReleaseSource


def convert_release_yaml(raw_yaml, image_tag, version):
    release_yaml = ruamel.yaml.load(
        raw_yaml, ruamel.yaml.RoundTripLoader)

    name = release_yaml['name']
    release_yaml['name'] = '{} (Integration Testing)'.format(name)
    release_yaml['version'] = version
    release_yaml['release_notes'] = 'Integration Testing {}'.format(version)

    for cmd in release_yaml['admin_commands']:
        cmd['image']['version'] = image_tag

    for component in release_yaml['components']:
        for container in component['containers']:
            container['version'] = image_tag

    return ruamel.yaml.dump(
        release_yaml, Dumper=ruamel.yaml.RoundTripDumper)


def read_release_yaml(release_file, image_tag, version):
    with open(release_file, 'r') as fh:
        raw_yaml = fh.read()

    converted_yaml = convert_release_yaml(raw_yaml, image_tag, version)

    return converted_yaml


def new_release(app, channel, new_release_config):
    print('Creating new release')
    release = app.create_release(source=NewReleaseSource.none)
    release.config = new_release_config
    release.promote(channels=(channel,), required=False)
    return release


@click.command()
@click.argument('token', help='A Replicated Vendor API Token')
@click.argument(
    'app_name', help='The name of the Replicated application to manage')
@click.argument(
    'channel_name', help=('The name of the channel to which a release should '
                          'be promoted.'))
@click.argument(
    'release_file', help=('Path to a replicated YAML configuration file used '
                          'to configure the new release'))
@click.argument(
    'license_file', help=('Path to which the Replicated license file will be '
                          'written'))
@click.option(
    '--image-tag', default='dev',
    help=('Replace all image versions with this tag to allow local image '
          'builds'))
@click.option(
    '--new-version', default=None,
    help=('Change the application release version.  The default is to use the '
          'date and time at which the release was created.'))
def main(token, app_name, channel_name, release_file, license_file, image_tag,
         new_version):
    new_version = new_version or datetime.utcnow().strftime(
        '%Y-%m-%dT%H:%M:%S')

    new_release_config = read_release_yaml(
        release_file, image_tag, new_version)

    api = ReplicatedVendorAPI(token)
    try:
        app = next(item for item in api.get_apps() if item.name == app_name)
    except StopIteration:
        raise RuntimeError('App {} not found'.format(app_name))

    try:
        channel = next(item for item in app.channels
                       if item.name == channel_name)
    except StopIteration:
        channel = app.create_channel(channel_name)

    try:
        existing_release = next(
            rel for rel in app.releases
            if rel.sequence == channel.release_sequence)
    except StopIteration:
        print('No existing release found')
        new_release(app, channel, new_release_config)
    else:
        expected_yaml = ruamel.yaml.load(new_release_config)
        existing_yaml = ruamel.yaml.load(existing_release.config)

        # Don't compare the version, which changes with time
        expected_yaml.pop('version')
        expected_yaml.pop('release_notes')
        existing_yaml.pop('version')
        existing_yaml.pop('release_notes')
        if expected_yaml != existing_yaml:
            print('Existing release does not match expected config')
            new_release(app, channel, new_release_config)
            existing_release.archive()
        else:
            print('Existing release matches expected config; not making '
                  'changes')

    licenses = app.licenses
    try:
        license = next(license for license in licenses
                       if license.assignee == channel_name
                       and license.channel == channel)
    except StopIteration:
        print('License not found ... generating')
        license = channel.create_license(channel_name)

    license_key = license.value
    with open(license_file, 'w') as fh:
        print('Writing license key to {}'.format(license_file))
        fh.write(license_key)


if __name__ == '__main__':
    main()
