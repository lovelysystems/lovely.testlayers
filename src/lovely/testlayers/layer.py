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

import tempfile
import os
import shutil

BASE = os.path.join(tempfile.gettempdir(), 'LovelyTestLayers')

def cleanAll():
    if os.path.exists(BASE):
        shutil.rmtree(BASE)

def system(c):
    if os.system(c):
        raise SystemError("Failed", c)

class WorkDirectoryLayer(object):

    """a test layer that creates a directory"""

    wdClean = False

    # defines if the work directory is different for different layer
    # names
    wdNameSpecific = True
    snapDir = None

    def getBaseDir(self):
        name = '.'.join((self.__class__.__module__,
                         self.__class__.__name__))
        if self.wdNameSpecific is True:
            name = '.'.join((name, self.__name__))
        path = os.path.join(BASE, name)
        return path

    def setUpWD(self):
        self._bd = self.getBaseDir()
        self._wd = os.path.join(self._bd, 'work')
        if self.wdClean and os.path.exists(self._wd):
            shutil.rmtree(self._wd)
        for p in (BASE, self._bd, self._wd):
            if not os.path.isdir(p):
                os.mkdir(p)

    def wdPath(self, *args):
        if len(args)==0:
            return self._wd
        return os.path.join(self._wd, *args)

    def _snapPath(self, ident):
        d = self.snapDir or self._bd
        return os.path.join(d, ('ss_%s.tar.gz' % ident))

    def makeSnapshot(self, ident="1"):
        assert ident
        system('cd "%s" && tar -zcf "%s" work' % (self._bd,
                                                  self._snapPath(ident)))

    def snapshotInfo(self, ident="1"):
        sp = self._snapPath(ident)
        return os.path.isfile(sp), sp

    def hasSnapshot(self, ident="1"):
        return os.path.isfile(self._snapPath(ident))

    def removeWD(self):
        """removes the working directory"""
        shutil.rmtree(self._wd)

    def restoreSnapshot(self, ident="1"):
        assert ident
        exists, tf = self.snapshotInfo(ident)
        if not exists:
            raise ValueError("Snapshot %r not found" % ident)
        self.removeWD()
        system('cd "%s" && tar -zxf "%s"' % (self._bd, tf))

class CascadedLayer(object):

    def __init__(self, name, *bases):
        self.__name__ = name
        self.__bases__ = tuple(bases)

    def setUp(self):
        pass

    def tearDown(self):
        pass
