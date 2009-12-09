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
from lovely.testlayers.server import ServerLayer


class MemcachedLayer(ServerLayer):

    """A layer that starts and stops memcached, the memcached
    executable needs to be in the path"""

    __bases__ = ()

    def __init__(self, name, port=11222, connections=10):
        self.port = port
        start_cmd = 'memcached -p %s -c %s' % (self.port, connections)
        super(MemcachedLayer, self).__init__(
            name, servers=['localhost:%s' % port],
            start_cmd=start_cmd)



