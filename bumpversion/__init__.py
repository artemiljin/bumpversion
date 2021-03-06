# -*- coding: utf-8 -*-

from __future__ import unicode_literals

try:
    from configparser import RawConfigParser, NoOptionError
except ImportError:
    from ConfigParser import RawConfigParser, NoOptionError

try:
    from StringIO import StringIO
except:
    from io import StringIO

import argparse
import os
import re
import sre_constants
import warnings
import io
from string import Formatter
from datetime import datetime
from difflib import unified_diff

import sys
import codecs

from bumpversion.version_part import VersionPart, NumericVersionPartConfiguration, ConfiguredVersionPartConfiguration

if sys.version_info[0] == 2:
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout)

__VERSION__ = '0.5.4-dev'

DESCRIPTION = 'bumpversion: v{} (using Python v{})'.format(
    __VERSION__,
    sys.version.split("\n")[0].split(" ")[0],
)

import logging

logger = logging.getLogger("bumpversion.logger")
logger_list = logging.getLogger("bumpversion.list")

from argparse import _AppendAction


class DiscardDefaultIfSpecifiedAppendAction(_AppendAction):
    '''
    Fixes bug http://bugs.python.org/issue16399 for 'append' action
    '''

    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(self, "_discarded_default", None) is None:
            setattr(namespace, self.dest, [])
            self._discarded_default = True

        super(DiscardDefaultIfSpecifiedAppendAction, self).__call__(
            parser, namespace, values, option_string=None)


time_context = {
    'now': datetime.now(),
    'utcnow': datetime.utcnow(),
}


def prefixed_environ():
    return dict((("${}".format(key), value) for key, value in os.environ.items()))


class ConfiguredFile(object):
    def __init__(self, path, versionconfig):
        self.path = path
        self._versionconfig = versionconfig

    def find(self, part='patch'):
        """
        Attempt to find Version according to the pattern from version config file.
        :return: Version object, Version object with nulled patch or None, None if not found
        """
        with io.open(self.path, 'rb') as f:
            for line in f.readlines():
                match = self._versionconfig.parse_regex.search(line.decode('utf-8').rstrip("\n"))
                if match:
                    _parsed = {}
                    _parsed_zero_patch = {}
                    for key, value in match.groupdict().items():
                        if key == part:
                            _parsed_zero_patch[key] = VersionPart('0', self._versionconfig.part_configs.get(key))
                        else:
                            _parsed_zero_patch[key] = VersionPart(value, self._versionconfig.part_configs.get(key))
                        _parsed[key] = VersionPart(value, self._versionconfig.part_configs.get(key))
                    return Version(_parsed, str(_parsed)), Version(_parsed_zero_patch, str(_parsed_zero_patch))
        return None, None

    def should_contain_version(self, version, context):
        """
        ?????
        :param version:
        :param context:
        :return:
        """

        context['current_version'] = self._versionconfig.serialize(version, context)

        serialized_version = self._versionconfig.search.format(**context)

        if self.contains(serialized_version):
            return

        msg = "Did not find '{}' or '{}' in file {}".format(version.original, serialized_version, self.path)

        if version.original:
            assert self.contains(version.original), msg
            return

        assert False, msg

    def contains(self, search):
        with io.open(self.path, 'rb') as f:
            search_lines = search.splitlines()
            lookbehind = []

            for lineno, line in enumerate(f.readlines()):
                lookbehind.append(line.decode('utf-8').rstrip("\n"))

                if len(lookbehind) > len(search_lines):
                    lookbehind = lookbehind[1:]

                if (search_lines[0] in lookbehind[0] and
                            search_lines[-1] in lookbehind[-1] and
                            search_lines[1:-1] == lookbehind[1:-1]):
                    logger.info("Found '{}' in {} at line {}: {}".format(
                        search, self.path, lineno - (len(lookbehind) - 1), line.decode('utf-8').rstrip()))
                    return True
        return False

    def replace(self, current_version, new_version, context, dry_run):

        with io.open(self.path, 'rb') as f:
            file_content_before = f.read().decode('utf-8')

        context['current_version'] = self._versionconfig.serialize(current_version, context)
        context['new_version'] = self._versionconfig.serialize(new_version, context)

        search_for = self._versionconfig.search.format(**context)
        replace_with = self._versionconfig.replace.format(**context)

        file_content_after = file_content_before.replace(
            search_for, replace_with
        )

        if file_content_before == file_content_after:
            # TODO expose this to be configurable
            file_content_after = file_content_before.replace(
                current_version.original,
                replace_with,
            )

        if file_content_before != file_content_after:
            logger.info("{} file {}:".format(
                "Would change" if dry_run else "Changing",
                self.path,
            ))
            logger.info("\n".join(list(unified_diff(
                file_content_before.splitlines(),
                file_content_after.splitlines(),
                lineterm="",
                fromfile="a/" + self.path,
                tofile="b/" + self.path
            ))))
        else:
            logger.info("{} file {}".format(
                "Would not change" if dry_run else "Not changing",
                self.path,
            ))

        if not dry_run:
            with io.open(self.path, 'wb') as f:
                f.write(file_content_after.encode('utf-8'))

    def __str__(self):
        return self.path

    def __repr__(self):
        return '<bumpversion.ConfiguredFile:{}>'.format(self.path)


class IncompleteVersionRepresenationException(Exception):
    def __init__(self, message):
        self.message = message


class MissingValueForSerializationException(Exception):
    def __init__(self, message):
        self.message = message


class WorkingDirectoryIsDirtyException(Exception):
    def __init__(self, message):
        self.message = message


def keyvaluestring(d):
    return ", ".join("{}={}".format(k, v) for k, v in sorted(d.items()))


class Version(object):
    def __init__(self, values, original=None):
        self._values = dict(values)
        self.original = original

    def __getitem__(self, key):
        return self._values[key]

    def __len__(self):
        return len(self._values)

    def __iter__(self):
        return iter(self._values)

    def __repr__(self):
        return '<bumpversion.Version:{}>'.format(keyvaluestring(self._values))

    def compare(self, order, version_to_compare):
        """
        Compare two Version objects according to the orders
        :param order: order to compare
        :param version_to_compare: Version object to compare
        :return: dictionary of part: boolean
        """
        result = {}
        for label in order:
            if label not in self._values:
                continue
            else:
                if label not in version_to_compare._values:
                    result[label] = True
                else:
                    result[label] = (self._values[label].value == version_to_compare._values[label].value)
        return result

    def bump(self, part_name, order):
        bumped = False

        new_values = {}

        for label in order:
            if not label in self._values:
                continue
            elif label == part_name:
                new_values[label] = self._values[label].bump()
                bumped = True
            elif bumped:
                new_values[label] = self._values[label].null()
            else:
                new_values[label] = self._values[label].copy()

        new_version = Version(new_values)

        return new_version


class VersionConfig(object):
    """
    Holds a complete representation of a version string
    """

    def __init__(self, parse, serialize, search, replace, part_configs=None):

        try:
            self.parse_regex = re.compile(parse, re.VERBOSE)
        except sre_constants.error as e:
            logger.error("--parse '{}' is not a valid regex".format(parse))
            raise e

        self.serialize_formats = serialize

        if not part_configs:
            part_configs = {}

        self.part_configs = part_configs
        self.search = search
        self.replace = replace

    def _labels_for_format(self, serialize_format):
        return (
            label
            for _, label, _, _ in Formatter().parse(serialize_format)
            if label
        )

    def order(self):
        # currently, order depends on the first given serialization format
        # this seems like a good idea because this should be the most complete format
        return self._labels_for_format(self.serialize_formats[0])

    def parse(self, version_string):

        regexp_one_line = "".join([l.split("#")[0].strip() for l in self.parse_regex.pattern.splitlines()])

        logger.info("Parsing version '{}' using regexp '{}'".format(version_string, regexp_one_line))

        match = self.parse_regex.search(version_string)

        _parsed = {}
        if not match:
            logger.warn("Evaluating 'parse' option: '{}' does not parse current version '{}'".format(
                self.parse_regex.pattern, version_string))
            return

        for key, value in match.groupdict().items():
            _parsed[key] = VersionPart(value, self.part_configs.get(key))

        v = Version(_parsed, version_string)

        logger.info("Parsed the following values: %s" % keyvaluestring(v._values))

        return v

    def _serialize(self, version, serialize_format, context, raise_if_incomplete=False):
        """
        Attempts to serialize a version with the given serialization format.

        Raises MissingValueForSerializationException if not serializable
        """
        values = context.copy()
        for k in version:
            values[k] = version[k]

        # TODO dump complete context on debug level

        try:
            # test whether all parts required in the format have values
            serialized = serialize_format.format(**values)

        except KeyError as e:
            missing_key = getattr(e,
                                  'message',  # Python 2
                                  e.args[0]  # Python 3
                                  )
            raise MissingValueForSerializationException(
                "Did not find key {} in {} when serializing version number".format(
                    repr(missing_key), repr(version)))

        keys_needing_representation = set()
        found_required = False

        for k in self.order():
            v = values[k]

            if not isinstance(v, VersionPart):
                # values coming from environment variables don't need
                # representation
                continue

            if not v.is_optional():
                found_required = True
                keys_needing_representation.add(k)
            elif not found_required:
                keys_needing_representation.add(k)

        required_by_format = set(self._labels_for_format(serialize_format))

        # try whether all parsed keys are represented
        if raise_if_incomplete:
            if not (keys_needing_representation <= required_by_format):
                raise IncompleteVersionRepresenationException(
                    "Could not represent '{}' in format '{}'".format(
                        "', '".join(keys_needing_representation ^ required_by_format),
                        serialize_format,
                    ))

        return serialized

    def _choose_serialize_format(self, version, context):

        chosen = None

        # logger.info("Available serialization formats: '{}'".format("', '".join(self.serialize_formats)))

        for serialize_format in self.serialize_formats:
            try:
                self._serialize(version, serialize_format, context, raise_if_incomplete=True)
                chosen = serialize_format
                # logger.info("Found '{}' to be a usable serialization format".format(chosen))
            except IncompleteVersionRepresenationException as e:
                # logger.info(e.message)
                if not chosen:
                    chosen = serialize_format
            except MissingValueForSerializationException as e:
                logger.info(e.message)
                raise e

        if not chosen:
            raise KeyError("Did not find suitable serialization format")

        # logger.info("Selected serialization format '{}'".format(chosen))

        return chosen

    def serialize(self, version, context):
        serialized = self._serialize(version, self._choose_serialize_format(version, context), context)
        return serialized


OPTIONAL_ARGUMENTS_THAT_TAKE_VALUES = [
    '--parse',
    '--serialize',
    '--search',
    '--replace',
    '-m'
]


def ver_file_check(version_files):
    """
    Check if any version file exists
    :param version_files:
    :return: name of first file exist or None
    """
    for ver_file in version_files:
        if os.path.exists(ver_file):
            return ver_file
    return None


def split_args_in_optional_and_positional(args):
    # manually parsing positional arguments because stupid argparse can't mix
    # positional and optional arguments

    positions = []
    for i, arg in enumerate(args):

        previous = None

        if i > 0:
            previous = args[i - 1]

        if ((not arg.startswith('-')) and
                (previous not in OPTIONAL_ARGUMENTS_THAT_TAKE_VALUES)):
            positions.append(i)

    positionals = [arg for i, arg in enumerate(args) if i in positions]
    args = [arg for i, arg in enumerate(args) if i not in positions]

    return (positionals, args)


def main(original_args=None):
    positionals, args = split_args_in_optional_and_positional(
        sys.argv[1:] if original_args is None else original_args
    )

    if len(positionals[1:]) > 2:
        warnings.warn(
            "Giving multiple files on the command line will be deprecated, please use [bumpversion:file:...] in a config file.",
            PendingDeprecationWarning)

    parser1 = argparse.ArgumentParser(add_help=False)

    parser1.add_argument(
        '--verbose', action='count', default=0,
        help='Print verbose logging to stderr', required=False)

    parser1.add_argument(
        '--list', action='store_true', default=False,
        help='List machine readable information', required=False)

    known_args, remaining_argv = parser1.parse_known_args(args)

    logformatter = logging.Formatter('%(message)s')

    if len(logger.handlers) == 0:
        ch = logging.StreamHandler(sys.stderr)
        ch.setFormatter(logformatter)
        logger.addHandler(ch)

    if len(logger_list.handlers) == 0:
        ch2 = logging.StreamHandler(sys.stdout)
        ch2.setFormatter(logformatter)
        logger_list.addHandler(ch2)

    if known_args.list:
        logger_list.setLevel(1)

    log_level = {
        0: logging.WARNING,
        1: logging.INFO,
        2: logging.DEBUG,
    }.get(known_args.verbose, logging.DEBUG)

    logger.setLevel(log_level)

    logger.debug("Starting {}".format(DESCRIPTION))

    defaults = {}
    vcs_info = {}

    config = RawConfigParser('')

    # don't transform keys to lowercase (which would be the default)
    config.optionxform = lambda option: option

    config.add_section('bumpversion')

    # We need setup.py to get the major, minor versions
    ver_sources = ['setup.py', 'plugin.json', 'VERSION']
    ver_source = ver_file_check(ver_sources)
    if ver_source is None:
        message = "Could not read any of {} file".format(str(ver_sources))
        logger.error(message)
        sys.exit(2)
    # We don't work with other configuration files except .bumpversion.cfg
    config_file = '.bumpversion.cfg'
    if not os.path.exists(config_file):
        message = "Could not read {} file".format(config_file)
        logger.error(message)
        sys.exit(2)

    part_configs = {}

    files = []

    logger.info("Reading config file {}:".format(config_file))
    logger.info(io.open(config_file, 'rt', encoding='utf-8').read())

    config.readfp(io.open(config_file, 'rt', encoding='utf-8'))

    log_config = StringIO()
    config.write(log_config)

    if 'files' in dict(config.items("bumpversion")):
        warnings.warn(
            "'files =' configuration is will be deprecated, please use [bumpversion:file:...]",
            PendingDeprecationWarning
        )

    defaults.update(dict(config.items("bumpversion")))

    for listvaluename in ("serialize",):
        try:
            value = config.get("bumpversion", listvaluename)
            defaults[listvaluename] = list(filter(None, (x.strip() for x in value.splitlines())))
        except NoOptionError:
            pass  # no default value then ;)

    for boolvaluename in "dry_run":
        try:
            defaults[boolvaluename] = config.getboolean("bumpversion", boolvaluename)
        except NoOptionError:
            pass  # no default value then ;)

    for section_name in config.sections():

        section_name_match = re.compile("^bumpversion:(file|part):(.+)").match(section_name)

        if not section_name_match:
            continue

        section_prefix, section_value = section_name_match.groups()

        section_config = dict(config.items(section_name))

        if section_prefix == "part":

            ThisVersionPartConfiguration = NumericVersionPartConfiguration

            if 'values' in section_config:
                section_config['values'] = list(
                    filter(None, (x.strip() for x in section_config['values'].splitlines())))
                ThisVersionPartConfiguration = ConfiguredVersionPartConfiguration

            part_configs[section_value] = ThisVersionPartConfiguration(**section_config)

        elif section_prefix == "file":

            filename = section_value

            if 'serialize' in section_config:
                section_config['serialize'] = list(
                    filter(None, (x.strip() for x in section_config['serialize'].splitlines())))

            section_config['part_configs'] = part_configs

            if not 'parse' in section_config:
                section_config['parse'] = defaults.get("parse", '(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)')

            if not 'serialize' in section_config:
                section_config['serialize'] = defaults.get('serialize', [str('{major}.{minor}.{patch}')])

            if not 'search' in section_config:
                section_config['search'] = defaults.get("search", '{current_version}')

            if not 'replace' in section_config:
                section_config['replace'] = defaults.get("replace", '{new_version}')

            files.append(ConfiguredFile(filename, VersionConfig(**section_config)))

    parser2 = argparse.ArgumentParser(prog='bumpversion', add_help=False, parents=[parser1])
    parser2.set_defaults(**defaults)

    parser2.add_argument('--parse', metavar='REGEX',
                         help='Regex parsing the version string',
                         default=defaults.get("parse", '(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)'))
    parser2.add_argument('--serialize', metavar='FORMAT',
                         action=DiscardDefaultIfSpecifiedAppendAction,
                         help='How to format what is parsed back to a version',
                         default=defaults.get("serialize", [str('{major}.{minor}.{patch}')]))
    parser2.add_argument('--search', metavar='SEARCH',
                         help='Template for complete string to search',
                         default=defaults.get("search", '{current_version}'))
    parser2.add_argument('--replace', metavar='REPLACE',
                         help='Template for complete string to replace',
                         default=defaults.get("replace", '{new_version}'))

    known_args, remaining_argv = parser2.parse_known_args(args)

    defaults.update(vars(known_args))

    assert type(known_args.serialize) == list

    context = dict(list(time_context.items()) + list(prefixed_environ().items()) + list(vcs_info.items()))

    try:
        vc = VersionConfig(
            parse=known_args.parse,
            serialize=known_args.serialize,
            search=known_args.search,
            replace=known_args.replace,
            part_configs=part_configs,
        )
    except sre_constants.error as e:
        sys.exit(1)

    current_version = vc.parse(known_args.current_version) if known_args.current_version else None
    leave_config_ver = True
    new_version = None
    if len(positionals) > 0:
        setup_version, zero_patch_setup_version = ConfiguredFile(ver_source, vc).find(positionals[0])
        compare = setup_version.compare(vc.order(), current_version)
        for part in compare:
            if part == positionals[0]:
                continue
            else:
                leave_config_ver = leave_config_ver and compare[part]

        try:
            if leave_config_ver and current_version:
                logger.info("Attempting to increment part '{}'".format(positionals[0]))
                new_version = current_version.bump(positionals[0], vc.order())
                logger.info("Values are now: " + keyvaluestring(new_version._values))
                defaults['new_version'] = vc.serialize(new_version, context)
            elif not leave_config_ver:
                logger.info("Using Version from {}".format(ver_source))
                defaults['new_version'] = vc.serialize(zero_patch_setup_version, context)
                new_version = zero_patch_setup_version
                logger.info("Values are now: " + keyvaluestring(setup_version._values))
        except MissingValueForSerializationException as e:
            logger.info("Opportunistic finding of new_version failed: " + e.message)
        except IncompleteVersionRepresenationException as e:
            logger.info("Opportunistic finding of new_version failed: " + e.message)
        except KeyError as e:
            logger.info("Opportunistic finding of new_version failed")
    parser3 = argparse.ArgumentParser(
        prog='bumpversion',
        description=DESCRIPTION,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        conflict_handler='resolve',
        parents=[parser2],
    )

    parser3.set_defaults(**defaults)

    parser3.add_argument('--dry-run', '-n', action='store_true',
                         default=False, help="Don't write any files, just pretend.")

    file_names = []
    if 'files' in defaults:
        assert defaults['files'] != None
        file_names = defaults['files'].split(' ')

    parser3.add_argument('part', help='Part of the version to be bumped.')
    parser3.add_argument('files', metavar='file', nargs='*', help='Files to change', default=file_names)
    args = parser3.parse_args(remaining_argv + positionals)

    if args.dry_run:
        logger.info("Dry run active, won't touch any files.")

    # make sure files exist and contain version string
    # if leave_config_ver and new_version:
    logger.info("Update info in {}".format(ver_source))
    ConfiguredFile(ver_source, vc).replace(setup_version, new_version, context, args.dry_run)
    config.set('bumpversion', 'new_version', args.new_version)

    for key, value in config.items('bumpversion'):
        logger_list.info("{}={}".format(key, value))

    config.remove_option('bumpversion', 'new_version')

    config.set('bumpversion', 'current_version', args.new_version)

    new_config = StringIO()

    try:
        write_to_config_file = not args.dry_run

        logger.info("{} to config file {}:".format(
            "Would write" if not write_to_config_file else "Writing",
            config_file,
        ))

        config.write(new_config)
        logger.info(new_config.getvalue())

        if write_to_config_file:
            with io.open(config_file, 'wb') as f:
                f.write(new_config.getvalue().encode('utf-8'))

    except UnicodeEncodeError:
        warnings.warn(
            "Unable to write UTF-8 to config file, because of an old configparser version. "
            "Update with `pip install --upgrade configparser`."
        )
