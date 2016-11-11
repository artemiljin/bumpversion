# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

import subprocess
from functools import partial
from os import environ

import pytest

import bumpversion
from bumpversion import main, DESCRIPTION

SUBPROCESS_ENV = dict(
    list(environ.items()) + [(b'HGENCODING', b'utf-8')]
)

call = partial(subprocess.call, env=SUBPROCESS_ENV)
check_call = partial(subprocess.check_call, env=SUBPROCESS_ENV)
check_output = partial(subprocess.check_output, env=SUBPROCESS_ENV)


@pytest.fixture(params=['.bumpversion.cfg'])
def configfile(request):
    return request.param


try:
    bumpversion.RawConfigParser(empty_lines_in_values=False)
    using_old_configparser = False
except TypeError:
    using_old_configparser = True

xfail_if_old_configparser = pytest.mark.xfail(
    using_old_configparser,
    reason="configparser doesn't support empty_lines_in_values"
)


def _mock_calls_to_string(called_mock):
    return ["{}|{}|{}".format(
        name,
        args[0] if len(args) > 0  else args,
        repr(kwargs) if len(kwargs) > 0 else ""
    ) for name, args, kwargs in called_mock.mock_calls]


EXPECTED_OPTIONS = """
[-h]
[--verbose]
[--list]
[--allow-dirty]
[--parse REGEX]
[--serialize FORMAT]
[--search SEARCH]
[--replace REPLACE]
[--current-version VERSION]
[--dry-run]
--new-version VERSION
part
[file [file ...]]
""".strip().splitlines()

EXPECTED_USAGE = ("""

%s

positional arguments:
  part                  Part of the version to be bumped.
  file                  Files to change (default: [])

optional arguments:
  -h, --help            show this help message and exit
  --verbose             Print verbose logging to stderr (default: 0)
  --list                List machine readable information (default: False)
  --allow-dirty         Don't abort if working directory is dirty (default:
                        False)
  --parse REGEX         Regex parsing the version string (default:
                        (?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+))
  --serialize FORMAT    How to format what is parsed back to a version
                        (default: ['{major}.{minor}.{patch}'])
  --search SEARCH       Template for complete string to search (default:
                        {current_version})
  --replace REPLACE     Template for complete string to replace (default:
                        {new_version})
  --current-version VERSION
                        Version that needs to be updated (default: None)
  --dry-run, -n         Don't write any files, just pretend. (default: False)
  --new-version VERSION
                        New version that should be in the files (default:
                        None)
""" % DESCRIPTION).lstrip()


def test_usage_string(tmpdir, capsys):
    tmpdir.chdir()
    tmpdir.join('.bumpversion.cfg').write("""[bumpversion]
current_version: 0.10.2
new_version: 0.10.3
files: setup.py""")
    tmpdir.join('setup.py').write("""setup(
    name='bumpversion',
    version='0.5.4-dev',
    url='https://github.com/peritus/bumpversion',
    author='Filip Noetzel',
)
""")

    with pytest.raises(SystemExit):
        main(['--help'])

    out, err = capsys.readouterr()
    assert err == ""
    for option_line in EXPECTED_OPTIONS:
        assert option_line in out, "Usage string is missing {}".format(option_line)
    assert 'bumpversion:' in out
