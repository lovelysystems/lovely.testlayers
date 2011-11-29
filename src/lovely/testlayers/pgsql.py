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

import time
import os
import stat
import sys
import hashlib
import tempfile
import shutil
import psycopg2
from lovely.testlayers import util
from lovely.testlayers import sql
import re

BASE = os.path.join(tempfile.gettempdir(), __name__)
here = os.path.dirname(__file__)

Q_PIDS="""select procpid from
pg_stat_activity where datname='%s' and procpid <> pg_backend_pid();"""


class Server(sql.ServerBase):
    """ Class to control a pg server"""

    postgresqlConf = None

    def __init__(self, dbDir=None, host='127.0.0.1', port=5432,
                 verbose=False, pgConfig='pg_config', postgresqlConf=None):
        self.verbose = verbose
        self.port = port
        self.host = host
        self.dbDir = dbDir

        f = os.popen('which "%s"' % pgConfig)
        self.pgConfig = f.read().strip()
        f.close()
        if not self.pgConfig:
            raise ValueError, "pgConfig not found %r" % pgConfig
        f = os.popen('%s --version' % self.pgConfig)
        self.pgVersion = tuple(map(int,f.read().strip().split()[1].split('.')))
        f.close()

        if postgresqlConf is None:
            found = False
            for i in range(len(self.pgVersion)):
                v = '.'.join(map(str, self.pgVersion[:len(self.pgVersion)-i]))
                name = 'postgresql%s.conf' % v
                path = os.path.join(here, name)
                if os.path.exists(path):
                    self.postgresqlConf = path
                    found = True
                    break
            if not found:
                raise RuntimeError, "postgresql.conf not found for " \
                      "version %r" % (self.pgVersion,)
        else:
            if not os.path.exists(postgresqlConf):
                raise ValueError, "postgresqlConf not found %r" % postgresqlConf
            self.postgresqlConf = postgresqlConf
        f = os.popen('%s --bindir' % self.pgConfig)
        self.binDir = f.read().strip()
        f.close()
        f = os.popen('%s --sharedir' % self.pgConfig)
        self.shareDir = f.read().strip()
        f.close()
        self.psql = '%s -q -h %s -p %s' % (self.cmd('psql'),
                                        self.host,
                                        self.port)

    def cmd(self, name):
        return os.path.join(self.binDir, name)

    def createDB(self, dbName):
        cmd = '%s -p %s -h %s %s' % (self.cmd('createdb'),
                                     self.port, self.host, dbName)
        util.system(cmd)

    def disconnectAll(self, dbName):
        """disconnects all from this db"""

        cs = "dbname='%s' host='%s' port='%i'" % (dbName, self.host, self.port)
        conn = psycopg2.connect(cs)
        cur = conn.cursor()
        cur.execute(Q_PIDS)
        pids = cur.fetchall()
        for pid, in pids:
            self.ctl(' kill TERM %s' % pid)
        cur.close()
        conn.close()

    def dropDB(self, dbName):
        if not dbName in self.listDatabases():
            return
        self.disconnectAll(dbName)
        cmd = '%s -p %s -h %s %s' % (self.cmd('dropdb'),
                                     self.port, self.host, dbName)
        util.system(cmd)

    def runScripts(self, dbName, scripts):
        """runs sql scripts from given paths"""
        for script in scripts:
            script = self.resolveScriptPath(script)
            if self.verbose:
                output = ''
            else:
                output = '>/dev/null 2>&1'
            util.system('%s -q -f %s %s %s' % (
                                    self.psql, script, dbName, output))

    def resolveScriptPath(self, path):
        parts = path.split(':')
        if not path.startswith('pg_config:') or len(parts)!=3:
            return os.path.abspath(path)
        ignored, opt, path = parts

        assert opt in ('bin', 'doc', 'include', 'share', 'locale')
        f = os.popen('%s --%sdir' % (self.pgConfig, opt))
        base = f.read().strip()
        f.close()
        return os.path.join(base, path)

    def initDB(self):
#         if not os.path.exists(self.dbDir):
#             os.makedirs(self.dbDir)
        cmd = '%s -A trust -D %s >/dev/null' % (self.cmd('initdb'),
                                                self.dbDir)
        t = time.time()
        util.system(cmd)
        print >> sys.stderr, "INITDB: %r in %s secs" % (self.dbDir,
                                                        time.time()-t)


    def _copyConf(self):
        to = os.path.join(self.dbDir, 'postgresql.conf')
        if os.path.exists(to) and (
            os.stat(to)[stat.ST_MTIME] <= os.stat(
            self.postgresqlConf)[stat.ST_MTIME]):
            return False
        # copy conf
        shutil.copyfile(self.postgresqlConf, to)
        return True

    def ctl(self, arg):
        cmd = '%s -l "%s" -D %s %s' % (self.cmd('pg_ctl'),
                                       self.pgCtlLog,
                                       self.dbDir, arg)
        util.system(cmd)

    @property
    def pgCtlLog(self):
        base = self.dbDir or tempfile.gettempdir()
        return os.path.join(base, 'pg_ctl.log')

    def start(self):
        self._copyConf()
        self.ctl('-o "-p %s" -s -w start' % self.port)

    def stop(self):
        self.ctl('stop -s -w -m fast > /dev/null')

    def isRunning(self):
        o, i , e = os.popen3('%s -D %s -w status' % (self.cmd('pg_ctl'),
                                                     self.dbDir))
        res = i.read()
        o.close()
        i.close()
        e.close()
        return 'is running' in res

    def isListening(self):
        i, o, e = os.popen3('%s -l' % self.psql)
        return not e.read()

    def listDatabases(self):
        f = os.popen('%s -l' % self.psql)
        res = f.read()

        res = res.split('\n')[3:]
        dbs = []
        pat = re.compile(r'^(\w+)\s.*')
        for l in res:
            if not l:
                break
            m = pat.match(l.strip())
            if m:
                dbs.append(m.group(1))
        f.close()
        return dbs

    def dump(self, dbName, path):
        assert self.isRunning()
        path = os.path.abspath(path)
        cmd = '%s -p %s %s > %s' % (self.cmd('pg_dump'),
                                    self.port, dbName,
                                    path)
        print >> sys.stderr, "DUMP: %r" % cmd
        util.system(cmd)

    def restore(self, dbName, path):
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            raise ValueError, "No such file %r" % path
        assert self.isRunning()
        t = time.time()
        self.dropDB(dbName)
        self.createDB(dbName)
        cmd = '%s -p %s -f %s %s' % (self.cmd('psql'),
                                     self.port, path,
                                     dbName)
        import popen2
        p = popen2.Popen3(cmd)
        p.wait()
        print >> sys.stderr, "RESTORED %r in %r secs" % (
            path, time.time()-t)

    def getURI(self, dbName):
        return 'postgres://localhost:%s/%s' % (self.port, dbName)

    def newConnection(self, dbName):
        cs = "dbname='%s' host='%s' port='%i'" % (dbName, self.host, self.port)
        return psycopg2.connect(cs)


class PGDBScript(sql.BaseSQLScript):
    """ Script to controll a postgresql server"""

    server_impl = Server

main = PGDBScript()


class PGDatabaseLayer(sql.BaseSQLLayer):

    """A test layer which creates a database and starts a postgres
    server"""

    server_impl = Server

    def __init__(self, dbName, scripts=[], setup=None,
                 snapshotIdent=None, verbose=False,
                 port=15432, pgConfig='pg_config', postgresqlConf=None):
        self.dbDir = os.path.join(self.base_path, 'data')
        self.verbose = verbose
        self.port = port
        self.srvArgs = dict(verbose=verbose,
                            port=self.port,
                            dbDir=self.dbDir,
                            pgConfig=pgConfig,
                            postgresqlConf=postgresqlConf)
        super(PGDatabaseLayer, self).__init__(dbName, scripts, setup, snapshotIdent)

    @property
    def base_path(self):
        return BASE

class ExecuteSQL(object):

    def __init__(self, stmt):
        self.stmt = stmt
        self.__name__ = self.__class__.__name__ + hashlib.sha1(str(
            self.stmt)).hexdigest()

    def __call__(self, layer):
        conn = layer.newConnection()
        cur = conn.cursor()
        cur.execute(self.stmt)
        conn.commit()
        cur.close()
        conn.close()
