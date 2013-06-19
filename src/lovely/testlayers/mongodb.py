##############################################################################
#
# Copyright 2011,2013 Andreas Motl
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
``lovely.testlayers.mongodb``

Various flavors of test layers for MongoDB:

- The ``MongoLayer`` starts and stops a single MongoDB instance.
- The ``MongoMasterSlaveLayer`` starts and stops multiple MongoDB
  instances and configures a master-slave connection between them.
- The ``MongoReplicaSetLayer`` starts and stops multiple MongoDB
  instances and configures a replica set between them.
- The ``MongoShardingLayer`` starts and stops multiple MongoDB instances as
  well as a ``mongos`` instance and configures sharding between them. [TODO]
"""

import os
import time
import shutil
import logging
from layer import WorkDirectoryLayer, CascadedLayer
from server import ServerLayer


# setup logging
class NonDuplicateLogFilter(logging.Filter):

    def __init__(self):
        self.last_message = None

    def filter(self, record):
        outcome = self.last_message != record.msg
        self.last_message = record.msg
        return outcome


console = logging.StreamHandler()
console.setFormatter(
    logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s'))
logger = logging.getLogger(__name__)
logger.addHandler(console)
logger.addFilter(NonDuplicateLogFilter())
logger.setLevel(logging.INFO)


class MongoLayer(WorkDirectoryLayer, ServerLayer):
    """
    Encapsulates controlling a single MongoDB instance.
    """

    __bases__ = ()

    def __init__(self, name, mongod_bin = None,
                    hostname = 'localhost', storage_port = 37017,
                    cleanup = True, extra_options = None):
        """
        Settings for ``MongoLayer``

        :name: (required)
            The first and only positional argument is the layer name

        :mongod_bin:
            The path to ``mongod``, defaults to ``mongod``

        :hostname:
            The hostname to be used for:
                - adding MongoDB nodes to the cluster
                - connecting to a MongoDB node from Python
            Defaults to ``localhost``

        :storage_port:
            On which port MongoDB should listen, defaults to ``37017``
            which is the MongoDB standard port + 1000

        :cleanup:
            Whether to erase the workspace directory on initialization,
            defaults to ``True``

        :extra_options:
            Additional command line options to be passed to ``mongod``,
            defaults to empty dictionary
        """
        self.__name__ = name
        self.mongod_bin = mongod_bin
        self.hostname = hostname
        self.storage_port = storage_port
        self.console_port = storage_port + 1000
        self.directories = ('var', 'run', 'log')
        self.cleanup = cleanup
        self.extra_options = extra_options or {}

        self.setup_workdirectory()
        logger.info('Initializing MongoLayer on port=%s, workingdir=%s' %
            (self.storage_port, self.workingdir))
        self.setup_server()

    def setup_workdirectory(self):
        self.wdNameSpecific = False
        self.setUpWD()
        self.workingdir = self.wdPath(self.__name__)
        # TODO:
        # maybe differentiate between cleaning up the working directory
        # on startup versus cleaning it up on teardown
        self._workspace_cleanup()
        self._workspace_create()

    def setup_server(self):
        ServerLayer.__init__(self, self.__name__)
        self.log_file = os.path.join(self.log, 'mongodb.log')
        self.pid_file = os.path.join(self.run, 'mongodb.pid')
        self.lock_file = os.path.join(self.var, 'mongod.lock')
        self.mongod_bin = self.mongod_bin or 'mongod'

        # compute mongod arguments
        self.default_options = {
            'port': self.storage_port,
            'dbpath': self.var,
            'pidfilepath': self.pid_file,
            'logpath': self.log_file,
            'rest': True,
            'noprealloc': True,
            'smallfiles': True,
        }
        all_options = {}
        all_options.update(self.default_options)
        all_options.update(self.extra_options)

        # compute "self.start_cmd"
        arguments_string = self._serialize_arguments(all_options)
        self.start_cmd = '{0} {1}'.format(self.mongod_bin, arguments_string)
        logger.debug('start_cmd=%s' % self.start_cmd)

        # compute "self.servers"
        self.servers = [
            (self.hostname, self.storage_port),
            (self.hostname, self.console_port),
        ]

    def start(self):
        """
        Propagates start operation to ``ServerLayer``.
        Beforehand, brutally removes pid- and lock-files
        to be graceful if the last shutdown went wrong.
        """
        os.path.exists(self.pid_file) and os.unlink(self.pid_file)
        os.path.exists(self.lock_file) and os.unlink(self.lock_file)
        ServerLayer.start(self)

    def stop_acme(self):
        """
        TODO: maybe use "admin.command('shutdown')"
        instead of just killing the server process?
        """
        pass

    def _workspace_cleanup(self, force=False):
        """
        Removes the MongoDB "home" aka. workspace directory.
        """
        if self.cleanup or force:
            logger.info('Removing workspace directory "%s"' % self.workingdir)
            os.path.exists(self.workingdir) and shutil.rmtree(self.workingdir)

    def _workspace_create(self):
        """
        Creates the MongoDB "home" aka. workspace directory
        and desired subdirectories.
        """
        os.path.exists(self.workingdir) or os.mkdir(self.workingdir)
        for subdir_name in self.directories:
            subdir = self.wdPath(self.__name__, subdir_name)
            if not os.path.exists(subdir):
                os.mkdir(subdir)
            setattr(self, subdir_name, subdir)

    def _serialize_arguments(self, arguments):
        """
        Helper function to serialize a dictionary of
        commandline arguments into a string.
        """
        argument_list = []
        for key, value in arguments.iteritems():
            if not value:
                continue
            elif value is True:
                argument_item = '--%s' % key
            else:
                argument_item = '--%s="%s"' % (key, value)
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
        self._workspace_cleanup()


class MongoMultiNodeLayer(CascadedLayer):

    def __init__(self, name,
            mongod_bin = None,
            hostname = 'localhost', storage_port_base = None,
            count = 0, cleanup = True):
        """
        Base class.

        Configure multiple ``MongoLayer`` into this ``CascadedLayer``.

        :name: (required)
            The first and only positional argument is the layer name

        :mongod_bin:
            The path to ``mongod``, defaults to ``mongod``

        :hostname:
            The hostname to be used for:
                - adding MongoDB nodes to the cluster
                - connecting to a MongoDB node from Python
            Defaults to ``localhost``

        :storage_port_base:
            At which port to start. Will start multiple instances on
            consecutive ports, starting with this value

        :count:
            How many MongoDB nodes to start

        :cleanup:
            Whether to erase the workspace directory on initialization,
            defaults to ``True``
        """
        self.name = name
        self.mongod_bin = mongod_bin
        self.hostname = hostname
        self.storage_port_base = storage_port_base
        self.count = count
        self.cleanup = cleanup
        self.layers = []

        logger.info('Initializing %s with layer_options=%s' %
            (self.__class__.__name__, list(self.layer_options)))
        self.create_layers()
        CascadedLayer.__init__(self, name, *self.layers)

    @property
    def layer_options(self):
        """
        Generator which computes and emits informational
        (layer_name, storage_port) tuples for each MongoDB node.
        """
        for i in range(self.count):
            layer_name = '%s.%s' % (self.name, i + 1)
            storage_port = self.storage_port_base + i
            yield layer_name, storage_port

    @property
    def storage_ports(self):
        """
        Returns list of configured storage ports.
        """
        return [storage_port for _, storage_port in self.layer_options]

    def get_opcounters(self):
        """
        doctest convenience function to retrieve ``opcounters`` from
        ``serverStatus`` for each configured node, aggregate the results
        and compute some custom counters on them.
        The purpose is to prove that the ``write`` operations are dispatched
        to the ``PRIMARY``, while the ``read`` operations are dispatched to
        the ``SECONDARIES``.
        """
        from pymongo import Connection
        stats = {
            'custom': {},
            'hosts': {},
        }
        for port in self.storage_ports:
            host = '{0}:{1}'.format(self.hostname, port)
            mongo_conn = Connection(host, safe = True)
            status = mongo_conn.admin.command('serverStatus')
            mongo_conn.disconnect()

            # get all opcounters
            info = status.get('opcounters')

            # whether the current host is a PRIMARY or a SECONDARY
            ismaster = status.get('repl', {}).get('ismaster', False)

            # record all opcounter data by host
            stats['hosts'][host] = info

            # record custom counters:
            # - how many inserts are done on the PRIMARY
            # - how many queries are routed to all SECONDARIES
            stats['custom'].setdefault('primary.insert', 0)
            stats['custom'].setdefault('secondary.query', 0)
            if ismaster:
                stats['custom']['primary.insert'] += info['insert']
            else:
                stats['custom']['secondary.query'] += info['query']

        return stats


class MongoMasterSlaveLayer(MongoMultiNodeLayer):

    def __init__(self, name,
            mongod_bin = None,
            hostname = 'localhost', storage_port_base = 37020,
            count = 3, cleanup = True):
        """
        Make a ``MongoMasterSlaveLayer`` from a ``MongoMultiNodeLayer``

        :name: (required)
            The first and only positional argument is the layer name.

        :mongod_bin:
            The path to ``mongod``, defaults to ``mongod``

        :hostname:
            The hostname to be used for:
                - adding MongoDB nodes to the cluster
                - connecting to a MongoDB node from Python
            Defaults to ``localhost``

        :storage_port_base:
            At which port to start. Will start multiple instances on
            consecutive ports, starting with this value.
            Defaults to ``37020``

        :count:
            How many MongoDB nodes to start, defaults to ``3``.

        :cleanup:
            Whether to erase the workspace directory on initialization,
            defaults to ``True``.
        """
        self.master_port = storage_port_base
        MongoMultiNodeLayer.__init__(self, name,
            mongod_bin = mongod_bin,
            hostname = hostname, storage_port_base = storage_port_base,
            count = count, cleanup = cleanup)

    def create_layers(self):
        """
        Populate ``self.layers`` with all sub layers:
        One for each configured MongoDB node
        to be part of the master/slave setup.
        """

        # layers for multiple MongoDB nodes
        for number, (layer_name, storage_port) in enumerate(self.layer_options):
            if number == 0:
                extra_options = {'master': True}
            else:
                master = '{0}:{1}'.format(self.hostname, str(self.master_port))
                extra_options = {
                    'slave': True,
                    'source': master,
                    'slavedelay': 0
                }
            mongo = MongoLayer(layer_name,
                mongod_bin = self.mongod_bin, storage_port = storage_port,
                cleanup = self.cleanup, extra_options = extra_options)
            self.layers.append(mongo)


class MongoReplicaSetLayer(MongoMultiNodeLayer):

    def __init__(self, name,
            mongod_bin = None,
            hostname = 'localhost', storage_port_base = 37030,
            count = 3, cleanup = True, replicaset_name = None):
        """
        Make a ``MongoReplicaSetLayer`` from a ``MongoMultiNodeLayer``

        :name: (required)
            The first and only positional argument is the layer name.

        :mongod_bin:
            The path to ``mongod``, defaults to ``mongod``

        :hostname:
            The hostname to be used for:
                - adding MongoDB nodes to the cluster
                - connecting to a MongoDB node from Python
            Defaults to ``localhost``

        :storage_port_base:
            At which port to start. Will start multiple instances on
            consecutive ports, starting with this value.
            Defaults to ``37030``

        :count:
            How many MongoDB nodes to start, defaults to ``3``

        :cleanup:
            Whether to erase the workspace directory on initialization,
            defaults to ``True``

        :replicaset_name:
            Which name to use for the replica set. Defaults to the layer name.
        """
        self.replicaset_name = replicaset_name or name
        MongoMultiNodeLayer.__init__(self, name,
            mongod_bin = mongod_bin,
            hostname = hostname, storage_port_base = storage_port_base,
            count = count, cleanup = cleanup)

    def create_layers(self):
        """
        Populate ``self.layers`` with all sub layers:
        - One for each configured MongoDB node to be part of the replica set.
        - An additional one for establishing the replica set.
        """

        # layers for multiple MongoDB nodes
        for layer_name, storage_port in self.layer_options:
            extra_options = {
                'replSet': self._get_replset_option(exclude=storage_port)
            }
            mongo = MongoLayer(layer_name,
                mongod_bin = self.mongod_bin, storage_port = storage_port,
                cleanup = self.cleanup, extra_options = extra_options)
            self.layers.append(mongo)

        # final layer for establishing the replica set which will be set up
        # when all nodes have booted
        # hint:
        # use the MongoDB instance booted most recently for inquiry, because
        # this one can reach the other - previously booted - nodes immediately
        self.layers.append(
            MongoReplicaSetInitLayer(self.name + '.init', self.replicaset_name,
                self.storage_ports))

    def _get_replset_option(self, exclude=None):
        """
        Helper function to compute value of the ``--replSet``
        command line option for ``mongod``.
        Format:
        ``<replicasetname>/<hostname1:port1>,<hostname2:port2>,<hostname3:port3>``
        """
        nodelist = []
        for _, storage_port in self.layer_options:
            if storage_port != exclude:
                address = '{0}:{1}'.format(self.hostname, str(storage_port))
                nodelist.append(address)
        return '%s/%s' % (self.replicaset_name, ','.join(nodelist))


class MongoReplicasetInitError(Exception):
    pass


class MongoReplicasetNodenameError(Exception):
    pass


class MongoReplicaSetInitLayer(object):
    """
    A helper layer for establishing the replica set:
        - Periodically checks ``replSetGetStatus``
        - Waits until all nodes are up
        - Runs ``replSetInitiate`` if necessary
        - Waits until
            - replica set initialization took place
            - all cluster nodes established their roles (PRIMARY|SECONDARY)
    """

    __bases__ = ()

    def __init__(self, name, replicaset_name, ports,
            timeout = 60, hostname='localhost'):
        """
        :name: (required)
            The first and only positional argument is the layer name

        :hostname:
            The hostname to be used for:
                - adding MongoDB nodes to the cluster
                - connecting to a MongoDB node from Python
            Defaults to ``localhost``

        :port:
            The port to which node to connect for querying and controlling

        :timeout:
            How long to wait for the replica set to be established,
            defaults to ``60`` seconds
        """
        self.__name__ = name
        self.replicaset_name = replicaset_name
        self.ports = ports
        self.timeout = timeout
        self.hostname = hostname
        self.starttime = 0
        logger.info('Initializing MongoReplicaSetInitLayer')

    def setUp(self):
        """
        Set up the test layer.
        """
        self.replicaset_boot()

    def tearDown(self):
        """
        Tear down the test layer. Nothing to do here, we don't
        actually want to break the replica set in any way.
        """
        pass

    def replicaset_boot(self):
        """
        Waits for the replica set to be established by
        periodically checking the replica set status.
        Also accounts for timeout.
        """

        logger.info('Waiting for replica set to be fully initialized, ' +
                    'this might take up to one minute.')
        # wait for nodes to settle, damn timing-issues
        time.sleep(3)

        self.starttime = time.time()

        if not self.replicaset_initiate():
            msg = 'Could not initiate the replica set'
            logger.error(msg)
            raise MongoReplicasetInitError(msg)

        while not self.replicaset_ready:
            self.check_timeout()
            time.sleep(1)
        logger.info('Replica set ready!')

    def check_timeout(self):
        """
        Raise an exception if the timeout takes place.
        """
        now = time.time()
        if now - self.starttime >= self.timeout:
            msg = 'Error while initializing the replica set (timed out)'
            logger.error(msg)
            raise MongoReplicasetInitError(msg)

    def replicaset_initiate(self):
        """
        call replSetInitiate on one of the nodes of our replicaset in spe
        providing all the other nodes as options
        """
        from pymongo import Connection
        host = '{0}:{1}'.format(self.hostname, self.ports[-1])
        logger.info("Initiating replica set '{0}'".format(
            self.replicaset_name))

        command = 'replSetInitiate'

        try:
            mongo_conn = Connection(host, safe=True)
            # we are not interested in eventual errors
            status = mongo_conn.admin.command('replSetGetStatus', check=False)
            if status.get("set") == self.replicaset_name:
                if status.get("myState") in (1, 2) and \
                    len(status.get("members", [])) == len(self.ports):

                    logger.info("Replica set already initiated")
                    #logger.info(status)
                    return True
                else:
                    #logger.info(status)
                    return False

            result = mongo_conn.admin.command(
                command, self.replicaset_initiate_options())
            if result.get("ok") == 1.0:
                logger.info(
                    "Initiated replica set: '{0}'".format(result.get("info")))
                return True
            else:
                logger.warning(
                    "Could not initiate replica set, result={0}".format(result))

        except Exception, msg:
            logger.error(
                "Could not initiate replica set, exception is '{0}'".format(msg))

        return False

    def replicaset_initiate_options(self):
        options = {
            "_id": self.replicaset_name,
            "members": [],
        }
        for port in self.ports:
            options["members"].append({
                '_id': port - self.ports[0],
                'host': '{0}:{1}'.format(self.hostname, port),
            })
        logger.debug(options)
        return options

    @property
    def replicaset_ready(self):
        """
        State machine logic which tracks the boot process
        of a MongoDB multi-node/replica-set cluster.
        Inquires MongoDB using ``replSetGetStatus`` and checks responses.
        Returns ``True`` if replica set is fully established.
        """

        from pymongo import Connection
        from pymongo.errors import OperationFailure
        host = '{0}:{1}'.format(self.hostname, self.ports[-1])
        mongo_conn = Connection(host, safe = True)

        try:
            result = mongo_conn.admin.command('replSetGetStatus', check=False)
            startup_status = result.get('startupStatus')
            replset_name = result.get('set')
        except OperationFailure, msg:
            logger.error(msg)
            return False

        success = False

        # cluster is still booting
        if startup_status:
            logger.info("startup_status=%s %s" %
                (startup_status, result.get('errmsg')))

        # replica set is initiated, check that all member
        # nodes established their roles (PRIMARY|SECONDARY)
        elif replset_name:
            member_states = [member.get('stateStr')
                                for member in result.get('members')]
            logger.info(
                'name={replset_name}, nodes={member_states}'.format(**locals()))
            logger.debug(
                '{0} of {1} nodes are up'.format(
                    len(member_states), len(self.ports)))

            primary_up = 'PRIMARY' in member_states
            secondaries_up = all(map(
                lambda x: x in ('PRIMARY', 'SECONDARY'), member_states))

            all_up = len(self.ports) == len(member_states)

            success = primary_up and secondaries_up and all_up

        mongo_conn.disconnect()
        return success
