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

import sys
import os
import sha
import time
import tempfile
import _mysql
from lovely.testlayers import util
from lovely.testlayers import sql


BASE = os.path.join(tempfile.gettempdir(), __name__)

class Server(object):
    """ Class to control a mysql server"""

    def __init__(self, dbDir=None, host='127.0.0.1', port=6543):
        self.port = port
        self.host = host
        self.dbDir = dbDir

        self.cmd_post_fix = ''
        f = os.popen('which "mysql"')
        mysql_path = f.read().strip()
        f.close()
        if not mysql_path:
            f = os.popen('which "mysql5"')
            mysql_path = f.read().strip()
            f.close()
            self.cmd_post_fix = '5'
            if not mysql_path:
                raise ValueError, "Neither mysql nor mysql5 was found"
        self.bin_dir = os.path.dirname(mysql_path)

    def cmd(self, name, use_post_fix=True):
        name = name + (use_post_fix and self.cmd_post_fix)
        return os.path.join(self.bin_dir, name)

    @property
    def mysql(self):
        cmd = "%s --user=root --port=%i --host=%s --protocol=tcp -s "
        return cmd % (self.cmd('mysql'), self.port, self.host)

    @property
    def mysqladmin(self):
        cmd = "%s --user=root --port=%i --host=%s --protocol=tcp -s "
        return cmd % (self.cmd('mysqladmin'), self.port, self.host)

    @property
    def mysqldump(self):
        cmd = "%s --user=root --port=%i --host=%s --protocol=tcp "
        return cmd % (self.cmd('mysqldump'), self.port, self.host)

    def createDB(self, dbName):
        cmd = "%s -e 'CREATE DATABASE %s'" % (self.mysql, dbName)
        util.system(cmd)

    def dropDB(self, dbName):
        if not dbName in self.listDatabases():
            return
        cmd = "%s -e 'DROP DATABASE %s'" % (self.mysql, dbName)
        util.system(cmd)

    def runScripts(self, dbName, scripts):
        """runs sql scripts from given paths"""
        for script in scripts:
            script = os.path.abspath(script)
            cmd = "%s %s < %s" % (self.mysql, dbName, script)
            util.system(cmd)

    def initDB(self):
        if not os.path.exists(self.dbDir):
            os.makedirs(self.dbDir)
        cmd = "%s --ldata=%s" % (self.cmd('mysql_install_db'), self.dbDir)
        t = time.time()
        util.system(cmd)
        print >> sys.stderr, "INITDB: %r in %s secs" % (self.dbDir,
                                                        time.time()-t)

    def mysqld_path(self):
        f = os.popen('locate -l1 "*\/mysqld"')
        daemon_path = f.read().strip()
        f.close()
        return daemon_path

    def start(self):

        daemon_path = self.mysqld_path()
        if not daemon_path:
            raise IOError, "mysqld was not found. Is a MySQL server installed?"

        cmd = "%s --no-defaults --datadir=%s --port=%i --pid-file=%s/mysql.pid --socket=%s/mysql.sock & > /dev/null 2>&1 " % (daemon_path, self.dbDir, self.port, self.dbDir, self.dbDir)
        util.system(cmd)
        while not self.isRunning():
            time.sleep(1)

    def stop(self):
        cmd = "%s shutdown > /dev/null 2>&1" % self.mysqladmin
        util.system(cmd)
        while self.isRunning():
            time.sleep(1)

    def isRunning(self):
        cmd = "%s ping" % self.mysqladmin
        o, i , e = os.popen3(cmd)
        res = i.read()
        o.close()
        i.close()
        e.close()
        return 'alive' in res

    def isListening(self):
        return self.isRunning()

    def listDatabases(self):
        cmd = "%s -e 'SHOW DATABASES'" % self.mysql
        f = os.popen(cmd)
        res = f.read()
        res = res.split('\n')[1:]
        dbs = []
        for l in res:
            if not l or l.startswith('('):
                break
            dbs.append(l.split('|', 1)[0].strip())
        f.close()
        return dbs

    def dump(self, dbName, path):
        assert self.isRunning()
        path = os.path.abspath(path)
        cmd = "%s -r %s %s" % (self.mysqldump, path, dbName)
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

        cmd = "%s %s < %s" % (self.mysql, dbName, path)
        import popen2
        p = popen2.Popen3(cmd)
        p.wait()
        print >> sys.stderr, "RESTORED %r in %r secs" % (
            path, time.time()-t)

    def getURI(self, dbName):
        return 'mysql://localhost:%s/%s' % (self.port, dbName)

    def dbExists(self, dbName):
        return dbName in self.listDatabases()

    def newConnection(self, dbName):
        c = _mysql.connect(host=self.host, port=self.port,
                           user='root', db=dbName)
        return c


class MySQLDBScript(sql.BaseSQLScript):
    """ Script to controll a postgresql server"""

    @property
    def srv(self):
        if not hasattr(self, '_srv'):
            self._srv = Server(**self.srvArgs)
        return self._srv

main = MySQLDBScript()


class MySQLDatabaseLayer(sql.BaseSQLLayer):

    """A test layer which creates a database and starts a postgres
    server"""


    def __init__(self, dbName, scripts=[], setup=None,
                 snapshotIdent=None, port=16543):
        super(MySQLDatabaseLayer, self).__init__(dbName, scripts, setup,
                                                 snapshotIdent)
        self.dbDir = os.path.join(self.base_path, 'data')
        self.port = port
        self.srvArgs = dict(port=self.port,
                            dbDir=self.dbDir)

    @property
    def base_path(self):
        return BASE

    @property
    def srv(self):
        if not hasattr(self, '_srv'):
            self._srv = Server(**self.srvArgs)
        return self._srv


class ExecuteSQL(object):

    def __init__(self, stmt):
        self.stmt = stmt
        self.__name__ = self.__class__.__name__ + sha.new(str((
            self.stmt))).hexdigest()

    def __call__(self, layer):
        conn = layer.newConnection()
        conn.query(self.stmt)
        conn.commit()
        conn.close()
