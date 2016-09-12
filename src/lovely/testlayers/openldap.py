##############################################################################
#
# Copyright 2016 Andreas Motl
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
##############################################################################

"""
``lovely.testlayers.openldap``

Test layer for OpenLDAP:

- The ``OpenLDAPLayer`` starts and stops a single OpenLDAP instance.
"""
import os
import sys
import types
import shlex
import logging
import subprocess
from copy import deepcopy
from collections import OrderedDict
from lovely.testlayers.util import asbool
from lovely.testlayers.layer import WorkspaceLayer
from lovely.testlayers.server import ServerLayer

# Setup logging
console = logging.StreamHandler()
console.setFormatter(
    logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s'))
logger = logging.getLogger(__name__)
logger.addHandler(console)
logger.setLevel(logging.INFO)


class OpenLDAPConfigurationMixin(object):
    """
    Class providing utility functions driving the configuration
    setting mungling as a mixin for ``OpenLDAPLayer``.
    """

    # Candidate directories for looking for LDAP schema files
    schema_dir_candidates = [

        # Debian Linux
        '/etc/ldap/schema',

        # CentOS Linux
        '/etc/openldap/schema',

        # Mac OS X, Macports
        '/opt/local/etc/openldap/schema'
    ]

    # The settings to be written to ``slapd.conf``, in proper order.
    setting_keys = [
        'moduleload',
        'include',
        'pidfile',
        'argsfile',
        'database',
        'suffix',
        'rootdn',
        'rootpw',
        'directory',
        'index',
    ]

    # -------------------
    # slapd configuration
    # -------------------

    def compute_settings(self):
        """
        Compute settings for configuration file ``slapd.conf``.
        Uses some reasonable defaults and merges in obtained
        settings from ``self.conf_settings``.
        Outputs its efforts to ``self.settings``.
        """

        defaults = {
            'moduleload': 'back_bdb.la',
            'database': 'bdb',
            'directory': self.var_path,
            'pidfile': os.path.join(self.run_path, 'slapd.pid'),
            'argsfile': os.path.join(self.run_path, 'slapd.args'),
            'index':  'objectClass eq',
            'suffix': '"dc=test,dc=example,dc=com"',
            'rootdn': '"cn=admin,dc=test,dc=example,dc=com"',
            'rootpw': 'secret',
            }
        settings = defaults.copy()
        settings.update(self.conf_settings)

        self.settings = settings

    def write_config(self):
        """
        Write configuration file ``slapd.conf``.
        Optionally use preseed file from ``self.conf_blueprint``
        and add more settings from ``self.settings`` computed above.
        """

        blueprint = ''
        if self.conf_blueprint and os.path.isfile(self.conf_blueprint):
            blueprint = file(self.conf_blueprint).read()

        payload = self.make_config()

        # Debugging
        #print >>sys.stderr, 'payload:\n', payload

        with file(self.slapd_conf, 'w') as f:
            if blueprint:
                f.write(blueprint)
                f.write('\n')
            f.write(payload)

    def make_config(self):
        """
        Serialize ``self.settings`` to appropriate ``slapd.conf`` configuration file.
        Order matters.
        """
        entries = []

        settings = deepcopy(self.settings)

        # Add configuration settings in specific order
        for key in self.setting_keys:
            if key in settings:
                value = settings[key]
                entries.append(self.serialize_setting(key, value))
                del settings[key]

        # Add remaining configuration settings at bottom
        for key, value in settings.iteritems():
            entries.append(self.serialize_setting(key, value))

        payload = '\n'.join(entries)

        return payload

    def serialize_setting(self, key, value):
        """
        Serialize a single configuration setting parameter pair into appropriate format for ``slapd.conf``.
        """
        if isinstance(value, types.StringTypes):
            entry = '{key:<12}{value}'.format(key=key, value=value)
        elif isinstance(value, types.ListType):
            lines = []
            for value in value:
                line = self.serialize_setting(key, value)
                lines.append(line)
            entry = '\n'.join(lines)
        else:
            raise TypeError('Unable to serialize setting value of type {type}'.format(type=type(value)))
        return entry


    # --------------
    # Schema helpers
    # --------------

    def add_schema(self, schemafile):
        """
        Add schemafile as a "include" configuration setting,
        to ``self.settings`` if not already included.
        """
        if not self.schema_included(schemafile):
            schemapath = self.find_schema(schemafile)
            if schemapath:
                self.include_schema(schemapath)

    def include_schema(self, schemapath):
        """
        Append full path to schemafile to settings stage data.
        """
        self.conf_settings['include'].append(schemapath)

    def schema_included(self, schemafile):
        """
        Whether a schemafile is already present in settings stage data.
        """
        for include_entry in self.conf_settings['include']:
            if schemafile in include_entry:
                return True
        return False

    def find_schema(self, schemafile):
        """
        Find schemafile by searching in listed candidate paths.
        """
        for schema_dir in self.schema_dir_candidates:
            schema_path = os.path.join(schema_dir, schemafile)
            if os.path.exists(schema_path):
                return schema_path


class OpenLDAPLayerClientMixin(object):
    """
    Some methods for convenient access to LDAP client tools.
    ``ldapadd`` is obligatory for provisioning LDAP servers
    with a DIT to run software tests against.
    """

    # ------------
    # Client tools
    # ------------

    def ldapadd(self, ldif_file):

        # TODO: Currently, ``ldapadd`` can only be executed if it's on the search $PATH.

        #self.compute_settings()

        command = 'ldapadd -H {uri} -D {rootdn} -w {rootpw} -f {ldif_file} -c'.format(uri=self.uri, ldif_file=ldif_file, **self.settings)
        cmd = shlex.split(command)
        subprocess.CalledProcessError.__str__ = lambda self: "Command '%s' returned non-zero exit status %d. Output was:\n%s" % (self.cmd, self.returncode, self.output)
        try:
            subprocess.check_output(cmd, stderr=subprocess.STDOUT)

        except subprocess.CalledProcessError as ex:
            # Ignore "ldap_add: Already exists (68)"
            if ex.returncode != 68:
                raise


class OpenLDAPLayer(WorkspaceLayer, ServerLayer, OpenLDAPConfigurationMixin, OpenLDAPLayerClientMixin):
    """
    Encapsulates controlling a single OpenLDAP instance.
    """

    __bases__ = ()

    daemon_candidates = [

        # Linux
        '/usr/sbin/slapd',

        # Mac OS X, Macports
        '/opt/local/libexec/slapd',
    ]

    def __init__(self, name, slapd_bin=None,
                 host=None, port=None, tls=False,
                 conf_blueprint=None, conf_settings=None,
                 cleanup=True, extra_options=None):
        """
        Settings for ``OpenLDAPLayer``

        :name: (required)
            The first and only positional argument is the layer name.

        :slapd_bin:
            The path to ``slapd``, defaults to finding the executable
            by honoring $PATH and self.daemon_candidates.

        :host:
            The hostname to be used for computing the LDAP URI, which in turn gets used
            by ``ldapadd`` for provisioning the OpenLDAP DIT from appropriate LDIF files.
            Defaults to ``localhost``.

        :port:
            On which port OpenLDAP should listen, defaults to ``389``.

        :tls:
            Controls LDAP URI schema: ldap:// vs. ldaps://
            Defaults to ``False``.

        :conf_blueprint:
            Path to initial configuration file to use as a preseed for generating
            the appropriate slapd.conf. Optional.

        :conf_settings:
            Dictionary containing configuration settings to be propagated into ``slapd.conf``.
            When empty, reasonable defaults will apply (see ``OpenLDAPConfigurationMixin.compute_settings``)::

                'suffix': '"dc=test,dc=example,dc=org"',
                'rootdn': '"cn=admin,dc=test,dc=example,dc=org"',
                'rootpw': 'secret',

        :cleanup:
            Whether to erase the workspace directory on setup and teardown.
            Defaults to ``True``.

        :extra_options:
            Additional command line options to be passed to the daemon executable,
            defaults to empty dictionary. Currently unused.

            ATTENTION: CURRENTLY NOT WORKING WITH OpenLDAP. There are no extra_options.

        """

        # Essential attributes
        self.__name__ = name
        self.__classname__ = self.__class__.__name__

        # Setup workspace
        self.directories = ('etc', 'log', 'run', 'var')
        self.cleanup = asbool(cleanup) or False
        self.workspace_setup()

        # Propagate/compute parameters
        self.slapd_bin = slapd_bin or self.find_daemon('slapd')
        self.slapd_conf = os.path.join(self.etc_path, 'slapd.conf')
        self.stdout_file = os.path.join(self.log_path, 'stdout.log')
        self.stderr_file = os.path.join(self.log_path, 'stderr.log')
        self.conf_blueprint = conf_blueprint
        self.conf_settings = conf_settings or {}
        self.extra_options = extra_options or {}

        self.conf_settings.setdefault('include', [])

        self.host = host or 'localhost'
        self.port = port or 389
        self.tls  = asbool(tls) or False

        uri_schema = 'ldap'
        if self.tls: uri_schema = 'ldaps'
        self.uri = '{schema}://{host}:{port}'.format(schema=uri_schema, **self.__dict__)

        logger.info(u'Initializing server layer "{__name__}" ({__classname__}) ' \
                    u'on port={port}, workingdir={workingdir}'.format(**self.__dict__))

        self.setup_server()

    def setUp(self):
        """
        Setup the layer after computing the configuration
        settings and writing them to an appropriate ``slapd.conf``.
        """
        self.compute_settings()
        self.write_config()
        self.start()

    def setup_server(self):
        """
        Start the ``slapd`` daemon and capture its STDOUT and STDERR channels.
        """
        ServerLayer.__init__(self, self.__name__, stdout=self.stdout_file, stderr=self.stderr_file)

        # Compute "self.start_cmd"

        cmd_arguments = OrderedDict()
        cmd_arguments['f'] = self.slapd_conf
        cmd_arguments['h'] = self.uri
        # FIXME: Use debug log level from yet another parameter
        cmd_arguments['d'] = 255
        cmd_arguments_string = self.serialize_arguments(cmd_arguments)

        self.start_cmd = u'{program} {arguments}'.format(program=self.slapd_bin, arguments=cmd_arguments_string).encode('utf-8')
        print >>sys.stderr, 'self.start_cmd:', self.start_cmd
        logger.debug('start_cmd=%s' % self.start_cmd)

        # compute "self.servers"
        self.servers = [
            (self.host, int(self.port)),
        ]

    def start(self):
        """
        Propagates start operation to ``ServerLayer``.
        Beforehand, brutally removes pid- and lock-files
        to be graceful if the last shutdown went wrong.
        """
        #print >>sys.stderr, 'self.settings:', self.settings
        os.path.exists(self.settings['pidfile']) and os.unlink(self.settings['pidfile'])
        os.path.exists(self.settings['argsfile']) and os.unlink(self.settings['argsfile'])
        ServerLayer.start(self)

    def serialize_arguments(self, arguments):
        """
        Helper function to serialize a dictionary of
        commandline arguments into a string.
        """
        argument_list = []
        for key, value in arguments.iteritems():
            if not value:
                continue
            elif value is True:
                argument_item = '-%s' % key
            else:
                argument_item = "-%s '%s'" % (key, value)
            argument_list.append(argument_item)
        return ' '.join(argument_list)

    def tearDown(self):
        """
        Tear down the test layer. Remove the working directory.
        """
        ServerLayer.tearDown(self)
        # TODO:
        # maybe differentiate between cleaning up the working directory
        # on startup versus cleaning it up on teardown
        logger.info('Removing workspace directory "%s"' % self.workingdir)
        self.workspace_cleanup()
