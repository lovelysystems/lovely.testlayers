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
import glob
import shutil
import tempfile

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

class WorkspaceLayer(WorkDirectoryLayer):
    """
    The WorkspaceLayer sits on top of the WorkDirectoryLayer
    and provides additional convenience. To get an idea:

    - Append self.__name__ introduced by ServerLayer to working directory to isolate
      multiple working directories against each other in multi-daemon/cluster scenarios.

    - Provide full path to working directory as instance attribute ``self.workingdir``.

    - Create multiple subdirectories and also provide their full
      paths as instance attributes, suffixed by ``_path``.
      e.g. ``self.log_path``, ``self.etc_path``.

    - Clean up working directory before and after test runs.
      TODO: Improve configurability.

    - Provide helper methods ``find_daemon`` and ``find_configuration`` to
      compute paths to appropriate artifacts based on lists of candidates and $PATH.

    """

    subdir_suffix = u'_path'

    def workspace_setup(self):
        self.wdNameSpecific = False
        self.setUpWD()
        self.workingdir = self.wdPath(self.__name__)
        # TODO: Differentiate between cleaning up the working directory on startup vs. teardown
        self.workspace_cleanup()
        self.workspace_create()

    def workspace_create(self):
        """
        Create the workspace directory and specified subdirectories.
        TODO: Improve docs.
        """
        os.path.exists(self.workingdir) or os.mkdir(self.workingdir)

        # Create subdirectories
        if hasattr(self, 'directories'):
            for subdir_name in self.directories:
                subdir = self.wdPath(self.__name__, subdir_name)
                if not os.path.exists(subdir):
                    os.mkdir(subdir)
                subdir_name += self.subdir_suffix
                setattr(self, subdir_name, subdir)

    def workspace_cleanup(self, force=False):
        """
        Remove the workspace directory.
        """
        if self.cleanup or force:
            os.path.exists(self.workingdir) and shutil.rmtree(self.workingdir)


    def find_daemon(self, cmd=None, use_path=True):
        """
        Compute appropriate path to the daemon executable based on ``self.daemon_candidates`` and $PATH.
        """
        if not hasattr(self, 'daemon_candidates'):
            return cmd

        candidates = self.daemon_candidates
        if use_path:
            candidates += [os.path.join(path, cmd) for path in os.environ["PATH"].split(os.pathsep)]

        for candidate in candidates:
            program = self.find_thing(candidate)
            if program and os.access(program, os.X_OK):
                return program

    def find_configuration(self):
        """
        Compute appropriate path to configuration file based on ``self.configuration_candidates``.
        """
        if not hasattr(self, 'configuration_candidates'):
            return

        candidates = self.configuration_candidates
        for candidate in candidates:
            config = self.find_thing(candidate)
            if config and os.path.isfile(config):
                return config

    def find_thing(self, pattern):
        """
        Apply shell glob to candidate pattern to find appropriate file.
        """
        # TODO: Currently gets the last item of the list as it is assumed to be the most recent one. Improve this.
        candidates = glob.glob(pattern)
        if candidates:
            recent = candidates[-1]
            return recent


class CascadedLayer(object):

    def __init__(self, name, *bases):
        self.__name__ = name
        self.__bases__ = tuple(bases)

    def setUp(self):
        pass

    def tearDown(self):
        pass
