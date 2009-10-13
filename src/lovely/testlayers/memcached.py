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

import os
import telnetlib
import time
import socket

class MemcachedLayer(object):

    """A layer that starts and stops memcached, the memcached
    executable needs to be in the path"""

    __bases__ = ()

    def __init__(self, name, port=11222, connections=10):
        # we assume the parts are in our parent dir
        self.__name__ = name
        self.port = port
        self.connections = connections
        self.executable = 'memcached'

    def setUp(self):
        self.pid = os.spawnlp(os.P_NOWAIT, self.executable, self.executable,
                              '-p', str(self.port),
                              '-c', str(self.connections))
        while True:
            try:
                tn =  telnetlib.Telnet('localhost', self.port)
                tn.close()
                break
            except socket.error, e:
                time.sleep(0.5)


    def tearDown(self):
        os.kill(self.pid, 15)
        while True:
            try:
                tn =  telnetlib.Telnet('localhost', self.port)
                tn.close()
            except socket.error, e:
                break
            time.sleep(0.5)
