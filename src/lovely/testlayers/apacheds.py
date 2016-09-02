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
``lovely.testlayers.apacheds``

Test layer for ApacheDS:

- The ``ApacheDSLayer`` starts and stops a single ApacheDS instance.
"""
import os
import sys
import logging
from lovely.testlayers.util import asbool
from lovely.testlayers.layer import WorkspaceLayer
from lovely.testlayers.server import ServerLayer
from lovely.testlayers.openldap import OpenLDAPLayerClientMixin

# Setup logging
console = logging.StreamHandler()
console.setFormatter(
    logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s'))
logger = logging.getLogger(__name__)
logger.addHandler(console)
logger.setLevel(logging.INFO)


class ApacheDSLayer(WorkspaceLayer, ServerLayer, OpenLDAPLayerClientMixin):
    """
    Encapsulates controlling a single ApacheDS instance.
    """

    __bases__ = ()

    daemon_candidates = [

        # Debian Linux (DEB)
        '/opt/apacheds-*/bin/wrapper',

        # Fedora Linux (RPM)
        '/opt/apacheds-*/bin/wrapper',

        # Mac OS X, Macports
        '/usr/local/apacheds-*/bin/wrapper',

        ]

    configuration_candidates = [

        # Debian Linux (DEB)
        '/opt/apacheds-*/conf/wrapper.conf',

        # Fedora Linux (RPM)
        '/opt/apacheds-*/conf/wrapper.conf',

        # Mac OS X, Macports
        '/usr/local/apacheds-*/conf/wrapper.conf',

        ]

    def __init__(self, name, apacheds_bin=None, apacheds_conf=None,
                 host=None, port=None, tls=False,
                 conf_settings=None,
                 cleanup=True, extra_options=None):
        """
        Settings for ``ApacheDSLayer``

        :name: (required)
            The first and only positional argument is the layer name.

        :apacheds_bin:
            The path to ApacheDS' ``wrapper`` executable, defaults to
            finding the executable from ``self.daemon_candidates``.

        :apacheds_conf:
            The path to ApacheDS' ``wrapper.conf`` configuration file, defaults to
            finding the file by honoring $PATH and ``self.configuration_candidates``.

        :host:
            The hostname to be used for computing the LDAP URI, which in turn gets used
            by ``ldapadd`` for provisioning the ApacheDS DIT from appropriate LDIF files.
            Defaults to ``localhost``.

        :port:
            On which port ApacheDS should listen, defaults to ``10389``.

            ATTENTION: CURRENTLY NOT WORKING WITH ApacheDS. IT IS FIXED ON 10389.

        :tls:
            Controls LDAP URI schema: ldap:// vs. ldaps://
            Defaults to ``False``.

        :conf_settings:
            Dictionary containing configuration settings to be propagated into ``cn=config``.

            ATTENTION: CURRENTLY NOT WORKING WITH ApacheDS. SUFFIX AND ROOTDN/ROOTPW ARE FIXED.

        :cleanup:
            Whether to erase the workspace directory on setup and teardown.
            Defaults to ``True``.

        :extra_options:
            Additional command line options to be passed to the daemon executable,
            defaults to empty dictionary. Currently unused.

            ATTENTION: CURRENTLY NOT WORKING WITH ApacheDS. There are no extra_options.

        """

        # Essential attributes
        self.__name__ = name
        self.__classname__ = self.__class__.__name__

        # Setup workspace
        self.directories = ('cache', 'conf', 'log', 'partitions', 'run', 'syncrepl-data')
        self.cleanup = asbool(cleanup) or False
        self.workspace_setup()

        # Propagate/compute parameters
        self.apacheds_bin = apacheds_bin or self.find_daemon('wrapper')
        self.apacheds_conf = apacheds_conf or self.find_configuration()
        self.stdout_file = os.path.join(self.log_path, 'stdout.log')
        self.stderr_file = os.path.join(self.log_path, 'stderr.log')
        self.conf_settings = conf_settings or {}
        self.extra_options = extra_options or {}

        self.host = host or 'localhost'
        self.port = port or 10389
        self.tls  = asbool(tls) or False

        uri_schema = 'ldap'
        if self.tls: uri_schema = 'ldaps'
        self.uri = '{schema}://{host}:{port}'.format(schema=uri_schema, **self.__dict__)

        logger.info(u'Initializing server layer "{__name__}" ({__classname__}) ' \
                    u'on port={port}, workingdir={workingdir}'.format(**self.__dict__))

        self.setup_server()

    def compute_settings(self):
        """
        Compute settings for configuration file ``slapd.conf``.
        Uses some reasonable defaults and merges in obtained
        settings from ``self.conf_settings``.
        Outputs its efforts to ``self.settings``.
        """

        defaults = {
            'rootdn': 'uid=admin,ou=system',
            'rootpw': 'secret',
            }
        settings = defaults.copy()
        settings.update(self.conf_settings)

        self.settings = settings

    def setUp(self):
        """
        Setup the layer after computing the configuration
        settings and writing them to an appropriate ``slapd.conf``.
        """
        self.compute_settings()
        #self.write_config()
        self.start()

    def setup_server(self):
        """
        Start the ApacheDS daemon and capture its STDOUT and STDERR channels.

        export INSTANCE_DIRECTORY=`pwd`/instances/default
        /usr/local/apacheds-2.0.0-M23/bin/wrapper --console /usr/local/apacheds-2.0.0-M23/conf/wrapper.conf wrapper.debug=true

        """
        ServerLayer.__init__(self, self.__name__, stdout=self.stdout_file, stderr=self.stderr_file)

        # Compute "self.start_cmd"
        os.environ['INSTANCE_DIRECTORY'] = self.workingdir

        # FIXME: *Optionally* use wrapper.debug=true
        cmd_arguments_string = u'--console "{configfile}" wrapper.debug=true'.format(configfile=self.apacheds_conf)
        self.start_cmd = u'{program} {arguments}'.format(program=self.apacheds_bin, arguments=cmd_arguments_string)
        print >>sys.stderr, 'self.start_cmd:', self.start_cmd
        logger.debug('start_cmd=%s' % self.start_cmd)

        # compute "self.servers"
        self.servers = [
            (self.host, int(self.port)),
        ]

    def stop(self):

        # Apply special forces
        self.process.terminate()

        self.process.wait()

        if self.stdout and not self.stdout.closed:
            self.stdout.close()
        if self.stderr and not self.stderr.closed:
            self.stderr.close()

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
