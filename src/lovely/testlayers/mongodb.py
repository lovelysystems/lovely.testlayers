##############################################################################
#
# Copyright 2011 Andreas Motl
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

import os, sys
import time
import shutil
import logging
import telnetlib
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
console.setFormatter(logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s'))
logger = logging.getLogger(__name__)
logger.addHandler(console)
logger.addFilter(NonDuplicateLogFilter())
logger.setLevel(logging.DEBUG)


class MongoLayer(WorkDirectoryLayer, ServerLayer):
    """
    Encapsulates controlling a single MongoDB instance.
    """

    __bases__ = ()

    def __init__(self, name, mongod_bin = None, storage_port = 37017, cleanup = True, extra_options = {}):
        """
        Configure proper settings for ``WorkDirectoryLayer`` and ``ServerLayer``.

        :name: (required) The first and only positional argument is the layer name.
        :mongod_bin: The path to ``mongod``, defaults to ``mongod`` (then should be on ``$PATH``).
        :storage_port: On which port MongoDB should listen, defaults to ``37017`` (default port + 1000).
        :cleanup: Whether to erase the workspace directory on initialization, defaults to ``True``.
        :extra_options: Additional command line options to be passed to ``mongod``, defaults to empty dict.
        """
        self.__name__ = name
        self.mongod_bin = mongod_bin
        self.storage_port = storage_port
        self.console_port = storage_port + 1000
        self.directories = ('var', 'run', 'log')
        self.cleanup = cleanup
        self.extra_options = extra_options

        # 1. setup WorkDirectoryLayer
        self.wdNameSpecific = False
        self.setUpWD()
        self.homedir = self.wdPath(name)
        logger.info('Initializing MongoLayer on port=%s, homedir=%s' % (self.storage_port, self.homedir))
        if self.cleanup:
            self._workspace_cleanup()
        self._workspace_create()

        # 2. setup ServerLayer
        ServerLayer.__init__(self, self.__name__)
        self.log_file = os.path.join(self.log, 'mongodb.log')
        self.pid_file = os.path.join(self.run, 'mongodb.pid')
        self.lock_file = os.path.join(self.var, 'mongod.lock')
        self.mongod_bin = self.mongod_bin or 'mongod'
        extra_options_string = self._serialize_options()
        self.start_cmd = "%s --port=%s --rest --dbpath=%s --pidfilepath=%s --logpath=%s %s" % \
            (self.mongod_bin, self.storage_port, self.var, self.pid_file, self.log_file, extra_options_string)
        logger.debug('start_cmd=%s' % self.start_cmd)
        self.servers = [('localhost', self.storage_port), ('localhost', self.console_port)]


    def start(self):
        """
        Propagates start operation to ``ServerLayer``.
        Beforehand, brutally removes pid- and lock-files in case the last shutdown went wrong.
        """
        os.path.exists(self.pid_file) and os.unlink(self.pid_file)
        os.path.exists(self.lock_file) and os.unlink(self.lock_file)
        ServerLayer.start(self)

    def stop_acme(self):
        """
        TODO: maybe use "admin.command('shutdown')" instead of just killing the server process?
        """
        pass

    def _workspace_cleanup(self):
        """
        Removes the MongoDB "home" aka. workspace directory.
        """
        os.path.exists(self.homedir) and shutil.rmtree(self.homedir)

    def _workspace_create(self):
        """
        Creates the MongoDB "home" aka. workspace directory and desired subdirectories.
        """
        os.path.exists(self.homedir) or os.mkdir(self.homedir)
        for subdir_name in self.directories:
            subdir = self.wdPath(self.__name__, subdir_name)
            if not os.path.exists(subdir):
                os.mkdir(subdir)
            setattr(self, subdir_name, subdir)

    def _serialize_options(self):
        """
        Helper function to serialize ``self.extra_options`` into a string
        suitable for using as a command line option to ``mongod``.
        """
        option_list = []
        for key, value in self.extra_options.iteritems():
            if value is None:
                option_entry = '--%s' % key
            else:
                option_entry = '--%s="%s"' % (key, value)
            option_list.append(option_entry)
        return ' '.join(option_list)


class MongoMultiNodeLayer(CascadedLayer):

    def __init__(self, name, mongod_bin = None, storage_port_base = None, count = 0, cleanup = True):
        """
        Base class.

        Configure multiple ``MongoLayer`` into this ``CascadedLayer``.

        :name: (required) The first and only positional argument is the layer name.
        :mongod_bin: The path to ``mongod``, defaults to ``mongod`` (then should be on ``$PATH``).
        :storage_port_base: At which port to start. Will start multiple instances on consecutive ports, starting with this value.
        :count: How many MongoDB nodes to start.
        :cleanup: Whether to erase the workspace directory on initialization, defaults to ``True``.
        """
        self.name = name
        self.mongod_bin = mongod_bin
        self.storage_port_base = storage_port_base
        self.count = count
        self.cleanup = cleanup
        self.layers = []

        logger.info('Initializing %s with layer_options=%s' % (self.__class__.__name__, list(self.layer_options))) 

        # fail early on an otherwise hard to grok exception:
        # OperationFailure: command SON([('replSetInitiate', 1)]) failed: couldn't initiate : can't find self in the replset config my port: 37022
        try:
            import socket
            socket.gethostbyname(socket.gethostname())
        except:
            raise Exception("Sorry, will only work when 'socket.gethostbyname(socket.gethostname())' does not fail, please tune your hostname.")

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

    def get_opcounters(self, nonmaster_is_secondary = False):
        """
        doctest convenience function to retrieve ``opcounters`` from ``serverStatus``
        for each configured node, aggregate the results and compute some custom counters
        on them.
        The purpose is to prove that the ``write`` operations are dispatched to the
        ``PRIMARY``, while the ``read`` operations are dispatched to the ``SECONDARIES``.
        """
        from pymongo import Connection
        stats = {
            'custom': {},
            'hosts': {},
        }
        for port in self.storage_ports:
            host = 'localhost:%s' % port
            mongo_conn = Connection(host, safe = True)
            status = mongo_conn.admin.command('serverStatus')
            mongo_conn.disconnect()

            # get all opcounters
            info = status.get('opcounters')

            # whether the current host is a PRIMARY or a SECONDARY
            info['primary'] = status.get('repl', {}).get('ismaster', False)
            info['secondary'] = status.get('repl', {}).get('secondary', False)
            if nonmaster_is_secondary and not info['primary']:
                info['secondary'] = True

            # record all opcounter data by host
            stats['hosts'][host] = info

            # record custom counters:
            # - how many inserts are done on the PRIMARY
            # - how many queries are routed to all SECONDARIES
            stats['custom'].setdefault('primary.insert', 0)
            stats['custom'].setdefault('secondary.query', 0)
            if info['primary']:
                stats['custom']['primary.insert'] += info['insert']
            if info['secondary']:
                stats['custom']['secondary.query'] += info['query']
        return stats


class MongoMasterSlaveLayer(MongoMultiNodeLayer):

    def __init__(self, name, mongod_bin = None, storage_port_base = 37020, count = 3, cleanup = True):
        """
        Configure multiple ``MongoLayer`` into this ``CascadedLayer``.

        :name: (required) The first and only positional argument is the layer name.
        :mongod_bin: The path to ``mongod``, defaults to ``mongod`` (then should be on ``$PATH``).
        :storage_port_base: At which port to start, defaults to 37020. Will start multiple instances on consecutive ports, starting with this value.
        :count: How many MongoDB nodes to start, defaults to ``3``.
        :cleanup: Whether to erase the workspace directory on initialization, defaults to ``True``.
        """
        self.master_port = storage_port_base
        MongoMultiNodeLayer.__init__(self, name, mongod_bin = mongod_bin, storage_port_base = storage_port_base, count = count, cleanup = cleanup)

    def create_layers(self):
        """
        Populate ``self.layers`` with all sub layers:
        - One for each configured MongoDB node to be part of the master/slave setup.
        """

        # layers for multiple MongoDB nodes
        for number, (layer_name, storage_port) in enumerate(self.layer_options):
            if number == 0:
                extra_options = {'master': None}
            else:
                extra_options = {'slave': None, 'source': ':' + str(self.master_port), 'slavedelay': 0}
            mongo = MongoLayer(layer_name, mongod_bin = self.mongod_bin, storage_port = storage_port, cleanup = self.cleanup, extra_options = extra_options)
            self.layers.append(mongo)


class MongoReplicaSetLayer(MongoMultiNodeLayer):

    def __init__(self, name, mongod_bin = None, storage_port_base = 37030, count = 3, cleanup = True, replicaset_name = None):
        """
        Configure multiple ``MongoLayer`` into this ``CascadedLayer``.

        :name: (required) The first and only positional argument is the layer name.
        :mongod_bin: The path to ``mongod``, defaults to ``mongod`` (then should be on ``$PATH``).
        :storage_port_base: At which port to start, defaults to 37030. Will start multiple instances on consecutive ports, starting with this value.
        :count: How many MongoDB nodes to start, defaults to ``3``.
        :cleanup: Whether to erase the workspace directory on initialization, defaults to ``True``.
        :replicaset_name: Which name to use for the replica set. Defaults to the layer name.
        """
        self.replicaset_name = replicaset_name or name
        MongoMultiNodeLayer.__init__(self, name, mongod_bin = mongod_bin, storage_port_base = storage_port_base, count = count, cleanup = cleanup)

    def create_layers(self):
        """
        Populate ``self.layers`` with all sub layers:
        - One for each configured MongoDB node to be part of the replica set.
        - An additional one for establishing the replica set.
        """

        # layers for multiple MongoDB nodes
        for layer_name, storage_port in self.layer_options:
            extra_options = {'replSet': self._get_replset_option(exclude=storage_port)}
            mongo = MongoLayer(layer_name, mongod_bin = self.mongod_bin, storage_port = storage_port, cleanup = self.cleanup, extra_options = extra_options)
            self.layers.append(mongo)

        # final layer for establishing the replica set which will be set up when all nodes have booted
        # hint: use the MongoDB instance booted most recently for inquiry, because
        # this one can reach the other - previously booted - nodes immediately.
        self.layers.append(MongoReplicaSetInitLayer(self.name + '.init', self.storage_ports[-1]))


    def _get_replset_option(self, exclude=None):
        """
        Helper function to compute value of the ``--replSet`` command line option for ``mongod``.
        Format: ``<replicasetname>/<hostname1:port1>,<hostname2:port2>,<hostname3:port3>``
        """
        nodelist = [':' + str(storage_port) for _, storage_port in self.layer_options if storage_port != exclude]
        return '%s/%s' % (self.replicaset_name, ','.join(nodelist))



class MongoReplicasetInitError(Exception):
    pass

class MongoReplicaSetInitLayer(object):
    """
    A helper layer for establishing the replica set:
        - Periodically checks ``replSetGetStatus``
        - Waits until all nodes are up
        - Runs ``replSetInitiate`` if necessary
        - Waits until replica set initialization took place ...
        - ... and all cluster nodes established their roles (PRIMARY|SECONDARY).
    """

    __bases__ = ()
    
    def __init__(self, name, port, timeout = 60):
        """
        :name: (required) The first and only positional argument is the layer name.
        :port: The port to which node to connect for querying and controlling.
        :timeout: How long to wait for the replica set to be established, defaults to ``60`` seconds.
        """
        self.__name__ = name
        self.port = port
        self.timeout = timeout
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
        logger.info('Waiting for replica set to be fully initialized, this might take up to one minute.')
        self.starttime = time.time()
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
            msg = 'Error while initializing the replica set (timed out).'
            logger.error(msg)
            raise MongoReplicasetInitError(msg)

    @property
    def replicaset_ready(self):
        """
        State machine logic which tracks the boot process
        of a MongoDB multi-node/replica-set cluster.
        Inquiries MongoDB, checks responses, sends log messages
        and runs ``replSetInitiate`` if necessary.
        Returns ``True`` when the replica set is fully established.
        """

        from pymongo import Connection
        host = 'localhost:%s' % self.port
        mongo_conn = Connection(host, safe = True)

        result = mongo_conn.admin.command('replSetGetStatus', check = False)
        startup_status = result.get('startupStatus')
        replset_name = result.get('set')

        success = False

        # cluster is still booting
        if startup_status:
            logger.info("startup_status=%s %s" % (startup_status, result.get('errmsg')))
            # all cluster nodes are up, but replica set doesn't seem to be initiated yet, so just do it
            if startup_status == 3:
                init_result = mongo_conn.admin.command('replSetInitiate')
                logger.info('replSetInitiate: %s' % init_result)

        # replica set is initiated, check that all member
        # nodes established their roles (PRIMARY|SECONDARY)
        elif replset_name:
            member_states = [member.get('stateStr') for member in result.get('members')]
            logger.info('name={replset_name}, nodes={member_states}'.format(**locals()))
            primary_up = 'PRIMARY' in member_states
            secondaries_up = all(map(lambda x: x in ('PRIMARY', 'SECONDARY'), member_states))
            success = primary_up and secondaries_up
        
        mongo_conn.disconnect()
        return success
