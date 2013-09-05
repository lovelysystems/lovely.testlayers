##############################################################################
#
# Copyright 2009 Lovely Systems AG
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


import logging
import subprocess
import time
from collections import deque
import shlex
import os
import sys

from lovely.testlayers import util


if sys.version_info[0] > 2:
    basestring = str


class ServerLayer(object):

    """A layer that starts/stops an subprocess and optionally checks
    server ports"""

    __bases__ = ()

    def __init__(self, name, servers=[], start_cmd=None, subprocess_args=None,
                 stdout=None, stderr=None):
        self.__name__ = name
        self.servers = []
        self.start_cmd = start_cmd
        if not subprocess_args:
            subprocess_args = {}
        self.subprocess_args = subprocess_args
        for server in servers:
            host, port = server.split(':')
            self.servers.append((host, int(port)))
        self.stdout = None
        self.stderr = None
        if stdout:
            self.stdout = self.getFileObject(stdout)
        if stderr:
            self.stderr = self.getFileObject(stderr, 'stderr')

    def start(self):
        assert self.start_cmd, 'No start command defined'
        if self.stdout:
            self.stdout = self._reopen(self.stdout)
        if self.stderr:
            self.stderr = self._reopen(self.stderr, 'stderr')
        if isinstance(self.start_cmd, basestring):
            cmd = shlex.split(self.start_cmd)
        else:
            cmd = self.start_cmd
        # make sure we the ports are free
        for server in self.servers:
            assert not util.isUp(
                *server), 'Port already listening %s:%s' % server
        logging.info('Starting server %r', cmd)
        self.process = subprocess.Popen(cmd, **self.subprocess_args)
        to_start = deque(self.servers)
        while to_start:
            time.sleep(0.05)
            returncode = self.process.poll()
            if not returncode is None and returncode != 0:
                raise SystemError("Failed to start server rc=%s cmd=%s" %
                                  (returncode, self.start_cmd))
            server = to_start.popleft()
            if not util.isUp(*server):
                logging.info('Server not up %s:%s', *server)
                to_start.append(server)
            else:
                logging.info('Server up %s:%s', *server)

    def stop(self):
        self.process.kill()
        self.process.wait()
        if self.stdout and not self.stdout.closed:
            self.stdout.close()
        if self.stderr and not self.stderr.closed:
            self.stderr.close()

    def setUp(self):
        self.start()

    def tearDown(self):
        self.stop()
        to_stop = deque(self.servers)
        time.sleep(0.05)
        while to_stop:
            server = to_stop.popleft()
            if util.isUp(*server):
                logging.info('Server still up %s:%s', *server)
                to_stop.append(server)
                time.sleep(0.05)
            else:
                logging.info('Server stopped %s:%s', *server)

    def getFileObject(self, path, ident='stdout'):
        """ checks if the object is a file path or already a file object
            If the object is a file path, a file object for the given path gets
            returned.
            If the path is a directory, also a file object gets created at the
            given path """
        if isinstance(path, basestring):
            if os.path.isdir(path):
                path = os.path.join(path, '%s_%s.log' % (self.__name__, ident))
            return open(path, 'w+')
        elif hasattr(path, 'closed') and hasattr(path, 'close'):
            return path
        return None

    def _reopen(self, f, ident='stdout'):
        """ checks if a file is closed and reopen it if so.
            Also the file gets added to the subprocess_args. """
        if f.closed:
            f = open(f.name, 'w+')
        self.subprocess_args[ident] = f
        return f
