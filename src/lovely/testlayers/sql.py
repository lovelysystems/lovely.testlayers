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
import sys
import hashlib
import tempfile
from optparse import OptionParser
from lovely.testlayers import util

try:
    import transaction
except ImportError:
    transaction = None


class ServerBase(object):

    """Base class for abstracting sql servers"""

    def resolveScriptPath(self, path):
        return os.path.abspath(path)

    def dbExists(self, dbName):
        return dbName in self.listDatabases()

    def isListening(self):
        return self.isRunning()

class ServerGetterMixin(object):

    server_impl = None

    @property
    def srv(self):
        assert self.server_impl, "No server implementation specified"
        if not hasattr(self, '_srv'):
            self._srv = self.server_impl(**self.srvArgs)
        return self._srv

class BaseSQLScript(ServerGetterMixin):
    """Base script to controll a sql server"""

    dbName = None
    scripts = ()

    def __init__(self, dbDir=None, **kwargs):
        self.srvArgs={}
        kwargs.update(dict(dbDir=dbDir))
        self._init(kwargs)

    def _init(self, kwargs):
        self.dbName = kwargs.pop('dbName', self.dbName)
        self.scripts = kwargs.pop('scripts', self.scripts)
        self.srvArgs.update(kwargs)

    def _setup(self, runscripts=False):
        self._checkListening()
        self._checkDBName()
        if not self.srv.dbExists(self.dbName):
            self.srv.createDB(self.dbName)
            runscripts = True
        if runscripts and self.scripts:
            self.srv.runScripts(self.dbName, self.scripts)

    def runscripts(self):
        self._setup(runscripts=True)

    def start(self):
        self._checkStopped()
        if not os.path.exists(self.srvArgs.get('dbDir')):
            self.srv.initDB()
        self.srv.start()
        if self.dbName is not None:
            self._setup()

    def _checkDBDir(self):
        if self.srvArgs.get('dbDir') is None:
            raise RuntimeError, "No db directory defined"

    def _checkRunning(self):
        self._checkDBDir()
        if not self.srv.isRunning():
            raise RuntimeError, "SQL server not runnng at %s:%s" % (
                self.srvArgs.get('host'), self.srvArgs.get('port'))

    def _checkListening(self):
        if not self.srv.isListening():
            raise RuntimeError, "No sql server listening on %s:%s" % (
                self.srvArgs.get('host'), self.srvArgs.get('port'))

    def _checkStopped(self):
        if self.srv.isRunning():
            raise RuntimeError, "SQL server already runnng at %s:%s" % (
                self.srvArgs.get('host'), self.srvArgs.get('port'))

    def _checkDBName(self):
        if self.dbName is None:
            raise RuntimeError, "No database name defined"

    def stop(self):
        self._checkRunning()
        self.srv.stop()

    def __call__(self, **kwargs):
        self._init(kwargs)
        parser = OptionParser(
            usage="usage: %s [options] (start, stop, runscripts)" % sys.argv[0])
        options, args = parser.parse_args()
        if not len(args)==1 or args[0] not in ('start', 'stop', 'runscripts'):
            parser.print_help()
            sys.exit(1)
        try:
            getattr(self, args[0])()
        except RuntimeError, e:
            print str(e)
            sys.exit(1)


class BaseSQLLayer(ServerGetterMixin):
    """A test layer which creates a database and starts a sql server"""

    __bases__ = ()
    setup = None
    snapshotIdent = None
    firstTest = True

    def __init__(self, dbName, scripts=[], setup=None, snapshotIdent=None):
        self.dbName = dbName
        self.scripts_hash = self._gen_scripts_hash(scripts)
        self.scripts = scripts
        if setup is not None:
            self.setup = setup
            if snapshotIdent is None:
                self.snapshotIdent = util.dotted_name(setup)
            else:
                self.snapshotIdent = snapshotIdent
        self.__name__ = "%s_%s" % (self.__class__.__name__, dbName)

    def _snapPath(self, ident):
        # dbname does not matter here
        return os.path.join(self.base_path, '%s_%s.sql' % (
            self.scripts_hash, ident))

    def _gen_scripts_hash(self, scripts):
        ident = []
        for script in scripts:
            path = self.srv.resolveScriptPath(script)
            statinfo = os.stat(path)
            ident.append((path, statinfo.st_mtime))
        digest = hashlib.sha1(str(ident)).hexdigest()
        return digest

    def snapshotInfo(self, ident):
        sp = self._snapPath(ident)
        return os.path.isfile(sp), sp

    def setUp(self):
        if util.isUp('', self.port):
            raise RuntimeError, "Port already listening: %r" % self.port
        if not os.path.exists(self.dbDir):
            self.srv.initDB()
        self.srv.start()
        exists, sp = self.snapshotInfo('__scripts__')
        if exists:
            if not self.srv.dbExists(self.dbName):
                self.srv.createDB(self.dbName)
            if self.setup is None:
                self.srv.restore(self.dbName, sp)
        else:
            self.srv.dropDB(self.dbName)
            self.srv.createDB(self.dbName)
            if self.scripts:
                try:
                    self.srv.runScripts(self.dbName, self.scripts)
                except:
                    self.srv.stop()
                    raise
            self.srv.dump(self.dbName, sp)
        # create the snapshot for app
        dirty = False
        if self.setup is not None:
            exists, sps = self.snapshotInfo(self.snapshotIdent)
            if not exists:
                self.setup(self)
                self.srv.dump(self.dbName, sps)
            else:
                self.srv.restore(self.dbName, sps)

    def testSetUp(self):
        ident = self.snapshotIdent or '__scripts__'
        if not self.firstTest:
            # if we run the first time we ar clean
            exists, sps = self.snapshotInfo(ident)
            assert exists
            self.srv.restore(self.dbName, sps)
        self.firstTest = False

    def testTearDown(self):
        if transaction is not None:
            try:
                transaction.abort()
            except AttributeError:
                # we have no connection anymore, ignore
                # XXX how to reproduce?
                pass

    def tearDown(self):
        self.firstTest = True
        self.srv.stop()

    def newConnection(self):
        return self.srv.newConnection(self.dbName)

    def storeURI(self):
        return self.srv.getURI(self.dbName)
