# -*- coding: UTF-8 -*-
#
# Copyright (C) 2013 by Alex Brandt <alex.brandt@rackspace.com>
#
# pycore is freely distributable under the terms of an MIT-style license.
# See COPYING or http://www.opensource.org/licenses/mit-license.php.

import os
import sys
import argparse
import copy
import logging

try:
    import ConfigParser as configparser
except ImportError:
    import configparser

from margarine import information

logger = logging.getLogger(__name__)

CONFIGURATION_DIRECTORY = os.path.join(os.path.sep, "etc", "margarine")
CONFIGURATION_FILE = os.path.join(CONFIGURATION_DIRECTORY, "margarine.conf")

def extract_defaults(parameters, prefix = "", keep = lambda _: _):
    """Extract the default values for the passed parameters.

    This function will pull the default values from the parameters provided and
    associate them with their names.  Obviously, the returned dict maps the
    parameter's name to its default value(s).

    Arguments
    ---------

    :``parameters``: The parameter definitions (list of dicts) with the form
                     shown in the Examples_ section of Parameters.__init__.
    :``keep``:       The function used to filter the resulting dictionary.
                     Used primarily to filter in only the values we might be
                     interested in (i.e. only: "configuration", &c).

    """

    return dict([ (prefix + item["options"][0][2:], (item["default"], item.get("only"))) for item in filter(keep, parameters) if "default" in item ])

class Parameters(object):
    """Provide a dict-like interface to the parameters added.

    The parameters can be parsed from configuration files, command line
    arguments, and environment variables.

    For the following ``parameters`` passed to the constructor, the resulting
    parsed options are shown:

    :``parameters``:
    
      ::
      
        [
          {
            "group":   "default",
            "options": [ "--example", "-e" ],
            "default": "foo",
            "help":    "The help message!",
            }
          ]

    :command line: --example=foo or --default.example=foo
    :configuration file:

      ::

        [default]
        example = foo

    :environment: APPNAME_DEFAULT_EXAMPLE=foo

    All of the above parameters result in a value in parameters at the key,
    default.example, with a value of "foo".

    """

    __shared_state = {}
                     
    def __init__(self, name = "default", file_path = None, parameters = ()):
        """Add the given section (name) to any existing parameters.

        Construct a Parameters_ container type (dict-like) by using the passed
        ``file_path`` and ``parameters`` to create a hierarchical search for
        configuration items.

        The passed arguments and configuration files will be added to the
        search space of the parameters object.

        Arguments
        ---------

        :``name``:       The identifying name for the group of parameters on
                         the command line or a section in a configuration file.
                         The name does not need to be unique (multiple
                         invocations of the same name will be merged) but NAME
                         cannot contain a dot (.).
        :``file_path``:  The path to the configuration file this particular set
                         of Parameters_ should refer to when resolving
                         parameters.  If this is ``None``, we will simply skip
                         the configuration resolution completely.
        :``parameters``: The parameter definitions (list of dicts) with the
                         form shown in the Examples_ section below.  These
                         parameters dictate the defaults if nothing comes from
                         the command line or from the configuration file.

        Examples
        --------

        Example ``parameters`` input::

            [
                {
                    "options": [ "--example", "-e" ],
                    "default": "foo",
                    "help":    "The help message!",
                    }
                ]

        >>> import tempfile
        >>> temp = tempfile.NamedTemporaryFile()
        >>> Parameters("example", temp.name, [{"options": [ "--example", "-e" ], "default": "foo"}])
        <Parameters[example]: '/tmp/name'>

        """

        self.__dict__ = self.__shared_state
        
        assert(not getattr(self, "parsed", False))

        if not hasattr(self, "defaults"):
            self.defaults = {}

        prefix = ""
        if name != "default":
            prefix = name + "."

        self.defaults.update(extract_defaults(parameters, prefix = prefix))

        for parameter in parameters:
            parameter.setdefault("group", name)

        if hasattr(self, "parameters"):
            self.parameters += parameters 
        else:
            self.parameters = []

        self._add_argument_parameters(name, parameters)

        if not hasattr(self, "_configuration_files"):
            self._configuration_files = {}

        if file_path not in self._configuration_files:
            self.parse(components = { "file" }, file_path = file_path)

        self.parse(components = { "environment" })

    def reinitialize(self, file_path = None):
        """Load the configuration file(s) from disk.

        If a file path is set in this object, we will use it to load a
        configuration parser that we can retrieve keys with.  Otherwise, we
        ignore the configuration file completely.

        """

        if file_path is not None:
            self._configuration_files[file_path] = self._create_configuration_parser(file_path)
        else:
            for file_path in self._configuration_files.keys():
                self.reinitialize(file_path)

    def parse(self, components = { "cli", "file", "environment" }, only_known = False, file_path = None):
        """Parse the specified components' arguments.

        This makes the specified components' parameters available in the
        dictionary.  The only compononent required to be parsed is "cli" but
        calling this before any accesses is generally a good idea.

        Arguments
        ---------

        :``components``: The components to include in this parse of the
                         parameters.
        :``only_known``: Specifies that the command line parser should only 
                         parse the currenly known arguments and not all of the 
                         possible arguments (stalling errors due to improper 
                         usage until later).
        :``file_path``:  The specific configuration file to re-read in this
                         parse action.

        """

        if "cli" in components:
            if only_known:
                self.argument_parser.parse_known_args()
            else:
                self.parsed = True
                self.argument_parser.parse_args()

        if "file" in components:
            self.reinitialize(file_path)

        # Environment doesn't need to be pre-parsed.

    def _create_configuration_parser(self, file_path):
        """Create a fully initialized configuration parser with the parameters.

        All of the function parameters besides ``parameters`` and ``file_path``
        will be directly passed to ConfigParser.SafeConfigParser.  The returned
        value from this function is the properly prepared SafeConfigParser that
        has already been initialized and loaded.

        Arguments
        ---------

        :``file_path``:  The path to the configuration file to load.
        :``parameters``: The parameter definitions (list of dicts) with the
                         form shown in the Examples_ section of
                         Parameters.__init__.

        .. note::
            All other parameters are passed directly to
            ConfigParser.SafeConfigParser.

        """
        
        self._configuration_files[file_path] = configparser.SafeConfigParser()
        self._configuration_files[file_path].read(file_path)

    def _add_argument_parameters(self, name, parameters):
        """Add arguments to the argument parser.

        .. note::
            If the parser hasn't been created, the first call to this method
            will create it.
        
        All of the function parameters besides ``parameters`` will be directly
        passed to argparse.ArgumentParser.  The returned value from this function
        is the properly prepared ArgumentParser but the parser has not been run.

        Arguments
        ---------

        :``parameters``: The parameter definitions (list of dicts) with the form
                         shown in the Examples_ section of Parameters.__init__.

        .. note::
            All other arguments are passed directly to argparse.ArgumentParser.

        """

        if not hasattr(self, "argument_parser"):
            self.argument_parser = argparse.ArgumentParser()

            version = \
                    "%(prog)s-{i.VERSION}\n" \
                    "\n" \
                    "Copyright {i.COPY_YEAR} by {i.AUTHOR} <{i.AUTHOR_EMAIL}> and " \
                    "contributors.  This is free software; see the source for " \
                    "copying conditions.  There is NO warranty; not even for " \
                    "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE."

            self.argument_parser.add_argument("--version", action = "version",
                    version = version.format(i = information))

        parameters = copy.deepcopy(parameters)
        parameters = [ { "args": parameter.pop("options"), "kwargs": parameter } for parameter in parameters if parameter.get("only") in [ "arguments", None ] ] # pylint: disable=C0301

        for options in parameters:
            parser = self.argument_parser

            if name != "default":
                if not hasattr(self, "group_parsers"):
                    self.group_parsers = {}

                if len(options["args"]) > 1:
                    logger.warn("Ignored short option, %s, for %s", options["args"][1], options["args"][0])

                del options["args"][1:]
                options["args"][0].replace("--", "--" + name + "-")

                parser = self.group_parsers.get(name, self.argument_parser.add_argument_group(name))

            del options["kwargs"]["group"]

            parser.add_argument(*options["args"], **options["kwargs"])

    def __len__(self):
        return len(self.parameters)

    def __getitem__(self, key):
        if key not in self:
            raise KeyError(key)

        if not self.parsed:
            logger.warn("Parameters not parsed…parsing now.")
            self.parse()

        logger.info("Searching for key: %s", key)

        value = None

        default = None 
        if key in self.defaults:
            default = self.defaults[key]
        logger.debug("default: %s", default)

        value = os.environ.get("{0}_{1}_{2}".format(sys.argv[0].upper(), *[ _.upper() for _ in key.split(".", 1) ]), default)

        logger.debug("value: %s", value)

        for configuration_file in self._configuration_files:
            try:
                configuration_value = configuration_file.get(*key.split(".", 1))
                if configuration_value != default:
                    value = configuration_value
                    break
            except (configparser.NoOptionError, configparser.NoSectionError):
                pass

        logger.debug("value: %s", value)

        argument_key = "-".join(key.split(".", 1))
        if hasattr(self.argument_parser, argument_key):
            argument_value = getattr(self.arguments, argument_key)
            if argument_value != default:
                value = argument_value

        logger.debug("value: %s", value)

        return value 

    def __contains__(self, key):
        return key in self.iterkeys()

    def __iter__(self):
        return self.iterkeys()

    def copy(self):
        # TODO Think of a way to remove the re-read of files …
        return Paramaters(self.name, self.file_path, self.parameters)

    def get(self, key, default = None):
        if key in self:
            return self[key]
        return default

    def has_key(self, key):
        return key in self

    def items(self):
        return list(self.iteritems())

    def iteritems(self):
        for key in self.iterkeys():
            yield (key, self[key])

    def iterkeys(self):
        for item in self.parameters:
            value = item["options"][0][2:]

            if item["group"] != "default":
                value = item["group"] + value

            yield value

    def itervalues(self):
        for key in self.iterkeys():
            yield self[key]

    def keys(self):
        return list(self.iterkeys())

    def values(self):
        return list(self.itervalues())

# General Parameters for all applications:

Parameters(parameters = [
    { # --configuration=FILE, -f=FILE; FILE ← CONFIGURATION_FILE
        "options": [ "--configuration", "-f" ],
        "default": CONFIGURATION_FILE,
        "help": \
                "Configuration file to use to configure %(prog) as a whole.",
        },
    ])

Parameters("logging", parameters = [
    { # --logging-configuration=FILE; FILE ← CONFIGURATION_DIRECTORY/logging.conf
        "options": [ "--configuration" ],
        "default": os.path.join(CONFIGURATION_DIRECTORY, "logging.conf"),
        "help": \
                "The configuration file containing the logging " \
                "mechanism used by %(prog)s.  Default: %(default)s.",
        },
    ])

