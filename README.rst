===========
bumpversion
===========

Version-bump your software with a single command!

A small command line tool to simplify releasing software by updating all
version strings in your source code by the correct increment:

- version formats are highly configurable
- just handles text files, so it's not specific to any programming language


Usage
=====

Currently there is only one way to use it: you need .bumpversion.cfg and setup.py files. The setup.py file won't be
changed, but .bumpversion.cfg will be.
Actually the rule is next:
- compare version in setup.py with version in .bumpversion.cfg if minor/major are the same - update the patch from
.bumpversion.cfg and setup.py. If minor or major are different - use the version from setup.py and update only
.bumpversion.cfg

::

    bumpversion [options] part


``part`` (required)
  The part of the version to increase, only patch now are supported


Configuration
+++++++++++++

Put into .bumpversion.cfg information about the current version.

Example ``.bumpversion.cfg``::

  [bumpversion]
  current_version = 0.2.9

Options
=======

Most of the configuration values above can also be given as an option.
Additionally, the following options are available:

``--dry-run, -n``
  Don't touch any files, just pretend. Best used with ``--verbose``.

``--verbose``
  Print useful information to stderr

``-h, --help``
  Print help and exit

