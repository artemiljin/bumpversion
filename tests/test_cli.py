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
[--parse REGEX]
[--serialize FORMAT]
[--search SEARCH]
[--replace REPLACE]
[--dry-run]
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
  --parse REGEX         Regex parsing the version string (default:
                        (?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+))
  --serialize FORMAT    How to format what is parsed back to a version
                        (default: ['{major}.{minor}.{patch}'])
  --search SEARCH       Template for complete string to search (default:
                        {current_version})
  --replace REPLACE     Template for complete string to replace (default:
                        {new_version})
  --dry-run, -n         Don't write any files, just pretend. (default: False)
""" % DESCRIPTION).lstrip()


def test_usage_string(tmpdir, capsys):
    tmpdir.chdir()
    tmpdir.join('.bumpversion.cfg').write("""[bumpversion]
current_version: 0.10.2
files: setup.py""")
    tmpdir.join('setup.py').write("""setup(
    name='bumpversion',
    version='0.10.2',
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


def test_missing_config_py(tmpdir):
    tmpdir.chdir()
    with pytest.raises(SystemExit):
        main([])


def test_missing_bumpversion_cfg(tmpdir):
    tmpdir.chdir()
    tmpdir.join('setup.py').write("""setup(
    name='bumpversion',
    version='0.10.2',
    url='https://github.com/peritus/bumpversion',
    author='Filip Noetzel',
)
""")
    with pytest.raises(SystemExit):
        main([])


def test_use_dev_version(tmpdir):
    tmpdir.chdir()
    tmpdir.join('.bumpversion.cfg').write("""[bumpversion]
current_version: 0.10.4
files: setup.py""")
    tmpdir.join('setup.py').write("""setup(
    name='bumpversion',
    version='0.11.3',
    url='https://github.com/peritus/bumpversion',
    author='Filip Noetzel',
)
""")
    main(['patch'])
    assert '0.11.3' in tmpdir.join(".bumpversion.cfg").read()
    assert '0.11.3' in tmpdir.join("setup.py").read()


def test_update_same_config_version(tmpdir):
    tmpdir.chdir()
    tmpdir.join('.bumpversion.cfg').write("""[bumpversion]
current_version: 0.0.1
files: setup.py""")
    tmpdir.join('setup.py').write("""setup(
    name='bumpversion',
    version='0.0.1',
    url='https://github.com/peritus/bumpversion',
    author='Filip Noetzel',
)
""")
    main(['patch'])
    assert '0.0.2' in tmpdir.join(".bumpversion.cfg").read()
    assert '0.0.2' in tmpdir.join("setup.py").read()


def test_update_new_config_version(tmpdir):
    tmpdir.chdir()
    tmpdir.join('.bumpversion.cfg').write("""[bumpversion]
current_version: 0.11.4
files: setup.py""")
    tmpdir.join('setup.py').write("""setup(
    name='bumpversion',
    version='0.11.3',
    url='https://github.com/peritus/bumpversion',
    author='Filip Noetzel',
)
""")
    main(['patch'])
    assert '0.11.5' in tmpdir.join(".bumpversion.cfg").read()
    assert '0.11.5' in tmpdir.join("setup.py").read()
