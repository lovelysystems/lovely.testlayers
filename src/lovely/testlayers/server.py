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

import util


class ServerLayer(object):

    """A layer that starts/stops an subprocess and optionally checks
    server ports"""

    __bases__ = ()

    def __init__(self, name, servers=[], start_cmd=None):
        self.__name__ = name
        self.servers = []
        self.start_cmd = start_cmd
        for server in servers:
            host, port = server.split(':')
            self.servers.append((host, int(port)))

    def start(self):
        raise NotImplementedError

    def start(self):
        assert self.start_cmd, 'No start command defined'
        logging.info('Starting server %r', self.start_cmd)
        return subprocess.Popen(self.start_cmd,
                                shell=True,
                                stderr=subprocess.PIPE)

    def stop(self):
        self.process.kill()
        self.process.wait()

    def setUp(self):
        # make sure we the ports are free
        for server in self.servers:
            assert not util.isUp(
                *server), 'Port already listening %s:%s' % server
        self.process = self.start()
        to_start = deque(self.servers)
        time.sleep(0.05)
        while to_start:
            server = to_start.popleft()
            if not util.isUp(*server):
                logging.info('Server not up %s:%s', *server)
                to_start.append(server)
            else:
                logging.info('Server up %s:%s', *server)

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


