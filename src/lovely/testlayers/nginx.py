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
import subprocess

class NginxLayer(object):

    """A layer that starts and stops nginx under a given directory"""

    __bases__ = ()

    def __init__(self, name, prefix, nginx_cmd='nginx', nginx_conf=None):
        self.__name__ = name
        self.nginx_cmd = nginx_cmd
        self.nginx_conf = nginx_conf
        # we need to add the slash to the prefix because nginx needs it
        self.prefix = os.path.abspath(prefix) + '/'
        assert os.path.isdir(self.prefix), 'prefix not a directory %r' % self.prefix
        self.nginx_version = self._check_config()

    def _nginx_cmd(self, *args):
        opt_args = list(args)
        if self.nginx_conf:
            opt_args.append('-c %s' %self.nginx_conf)
        return ' '.join([self.nginx_cmd, '-p', self.prefix] +  opt_args)

    def _check_config(self):
        cmd = self._nginx_cmd('-v', '-t')
        process = subprocess.Popen(cmd,
                                   shell=True,
                                   stderr=subprocess.PIPE)
        if process.wait():
            raise RuntimeError(
                'Nginx check failed %s' % process.stderr.read())
        return process.stderr.read().split(':', 1)[1]

    def setUp(self):
        cmd = self._nginx_cmd()
        process = subprocess.Popen(cmd,
                                   shell=True,
                                   stderr=subprocess.PIPE)
        if process.wait():
            raise RuntimeError(
                'Nginx start failed %s' % process.stderr.read())

    def tearDown(self):
        cmd = self._nginx_cmd('-s', 'stop')
        process = subprocess.Popen(cmd,
                                   shell=True,
                                   stderr=subprocess.PIPE)
        if process.wait():
            raise RuntimeError(
                'Nginx stop failed %s' % process.stderr.read())
