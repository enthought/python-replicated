import os
import subprocess
import sys

from setuptools import setup, find_packages

MAJOR = 0
MINOR = 1
MICRO = 0

IS_RELEASED = False

VERSION = '%d.%d.%d' % (MAJOR, MINOR, MICRO)


# Return the git revision as a string
def git_version():
    def _minimal_ext_cmd(cmd):
        # construct minimal environment
        env = {}
        for k in ['SYSTEMROOT', 'PATH']:
            v = os.environ.get(k)
            if v is not None:
                env[k] = v
        # LANGUAGE is used on win32
        env['LANGUAGE'] = 'C'
        env['LANG'] = 'C'
        env['LC_ALL'] = 'C'
        out = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, env=env,
        ).communicate()[0]
        return out

    try:
        out = _minimal_ext_cmd(['git', 'rev-parse', 'HEAD'])
        git_revision = out.strip().decode('ascii')
    except OSError:
        git_revision = "Unknown"

    try:
        out = _minimal_ext_cmd(['git', 'rev-list', '--count', 'HEAD'])
        git_count = out.strip().decode('ascii')
    except OSError:
        git_count = '0'

    return git_revision, git_count


def write_version_py(filename='replicated/_version.py'):
    template = """\
# THIS FILE IS GENERATED FROM PYTHON_REPLICATED SETUP.PY
version = '{version}'
full_version = '{full_version}'
git_revision = '{git_revision}'
is_released = {is_released}

if not is_released:
    version = full_version
"""
    # Adding the git rev number needs to be done inside
    # write_version_py(), otherwise the import of replicated._version messes
    # up the build under Python 3.
    fullversion = VERSION
    if os.path.exists('.git'):
        git_rev, dev_num = git_version()
    elif os.path.exists('replicated/_version.py'):
        # must be a source distribution, use existing version file
        try:
            from replicated._version import git_revision as git_rev
            from replicated._version import full_version as full_v
        except ImportError:
            raise ImportError("Unable to import git_revision. Try removing "
                              "replicated/_version.py and the build directory "
                              "before building.")
        import re
        match = re.match(r'.*?\.dev(?P<dev_num>\d+)$', full_v)
        if match is None:
            dev_num = '0'
        else:
            dev_num = match.group('dev_num')
    else:
        git_rev = "Unknown"
        dev_num = '0'

    if not IS_RELEASED:
        fullversion += '.dev{0}'.format(dev_num)

    with open(filename, "wt") as fp:
        fp.write(template.format(version=VERSION,
                                 full_version=fullversion,
                                 git_revision=git_rev,
                                 is_released=IS_RELEASED))

    return fullversion


if __name__ == "__main__":
    install_requires = [
        'six',
        'attrs >= 15.0.0',
        'requests >= 2.3.0',
        'ruamel.yaml == 0.12.6',
    ]
    py2_requires = install_requires + [
        'enum34 >= 1.1.0',
    ]
    __version__ = write_version_py()
    if sys.version_info < (3, 0):
        install_requires += py2_requires

    setup(
        name="python-replicated",
        version=__version__,
        packages=list(find_packages()),
        author="Enthought Ltd",
        author_email="info@enthought.com",
        install_requires=install_requires,
        extras_require={
            ':python_version=="2.7"': py2_requires,
            ':python_version=="3.2"': install_requires,
            ':python_version=="3.3"': install_requires,
        },
    )
