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

from layer import WorkDirectoryLayer
import logging
import os
import setuptools
import shutil
import sys
import telnetlib
import time

def system(c, log='/dev/null'):
    if os.system('%s > "%s"' % (c, log)):
        raise SystemError("Failed", c)


logger = logging.getLogger(__name__)

URL = 'http://archive.apache.org/dist/cassandra/0.4.0/apache-cassandra-incubating-0.4.0-bin.tar.gz'

TMPL_LOG4J = """
log4j.rootLogger=DEBUG,stdout,R
log4j.appender.stdout=org.apache.log4j.ConsoleAppender
log4j.appender.stdout.layout=org.apache.log4j.SimpleLayout
log4j.appender.R=org.apache.log4j.DailyRollingFileAppender
log4j.appender.R.DatePattern='.'yyyy-MM-dd-HH
log4j.appender.R.layout=org.apache.log4j.PatternLayout
log4j.appender.R.layout.ConversionPattern=%%5p [%%t] %%d{ISO8601} %%F (line %%L) %%m%%n
log4j.appender.R.File=%(log)s/system.log
"""

CTL_TMPL="""#!/bin/sh

JVM_OPTS=" \
        -ea \
        -Xdebug \
        -Xrunjdwp:transport=dt_socket,server=y,address=18888,suspend=n \
        -Xms128M \
        -Xmx1G \
        -XX:SurvivorRatio=8 \
        -XX:TargetSurvivorRatio=90 \
        -XX:+AggressiveOpts \
        -XX:+UseParNewGC \
        -XX:+UseConcMarkSweepGC \
        -XX:CMSInitiatingOccupancyFraction=1 \
        -XX:+CMSParallelRemarkEnabled \
        -XX:+HeapDumpOnOutOfMemoryError \
        -Dcom.sun.management.jmxremote.port=18080 \
        -Dcom.sun.management.jmxremote.ssl=false \
        -Dcom.sun.management.jmxremote.authenticate=false"

CASSANDRA_CONF=%(conf)s
CASSANDRA_HOME=%(cassandra_home)s
pidpath=%(pid_file)s
if [ -x $JAVA_HOME/bin/java ]; then
    JAVA=$JAVA_HOME/bin/java
else
    JAVA=`which java`
fi
for jar in $CASSANDRA_HOME/lib/*.jar; do
    CLASSPATH=$CLASSPATH:$jar
done

exec $JAVA $JVM_OPTS -Dcassandra -Dstorage-config=$CASSANDRA_CONF \
     -Dcassandra-pidfile=$pidpath -cp $CLASSPATH \
     org.apache.cassandra.service.CassandraDaemon <&- &
        [ ! -z $pidpath ] && printf "%%d" $! > $pidpath

"""

class CassandraLayer(WorkDirectoryLayer):

    __bases__ = ()

    def __init__(self, name, storage_conf, storage_port=17000,
                 control_port=17001, thrift_port=19160):
        self.storage_port = storage_port
        self.control_port = control_port
        self.thrift_port = thrift_port
        assert os.path.isfile(storage_conf), 'storage_conf invalid path'
        self.storage_conf = storage_conf
        self.__name__ = name
        self.setUpWD()
        for name in ('var', 'run', 'bin', 'conf', 'log'):
            p = self.wdPath(name)
            if not os.path.exists(p):
                os.mkdir(p)
            setattr(self, name, p)
        self.pid_file = os.path.join(self.run, 'cassandra.pid')
        self._install_cassandra_home()
        logger.info('Using CASSANDRA_HOME %r' % self.cassandra_home)
        self._write_ctl()
        self._write_conf()

    def _write_conf(self):
        # copy the config file
        storage_conf_trg = os.path.join(self.conf, 'storage-conf.xml')
        f = open(self.storage_conf)
        tmpl = f.read()
        f.close()
        f = open(storage_conf_trg, 'w')
        f.write(tmpl % dict(var=self.var,
                            storage_port=self.storage_port,
                            control_port=self.control_port,
                            thrift_port=self.thrift_port))
        f.close()

        log4j_conf_trg = os.path.join(self.conf, 'log4j.properties')
        f = file(log4j_conf_trg, 'w')
        f.write(TMPL_LOG4J % dict(log=self.log))
        f.close()

    def _write_ctl(self):
        ctl_contents = CTL_TMPL % dict(
            cassandra_home=self.cassandra_home,
            conf=self.conf,
            pid_file=self.pid_file)
        self.ctl = os.path.join(self.bin, 'cassandra')
        f = open(self.ctl, 'w')
        f.write(ctl_contents)
        f.close()
        print >> sys.stderr, self.ctl

    def _install_cassandra_home(self):
        self.cassandra_home = self.wdPath('cassandra_home')
        if os.path.exists(self.cassandra_home):
            return
        bo = self.wdPath('bo')
        if not os.path.exists(bo):
            os.mkdir(bo)
        dc = os.path.join(bo, 'download-cache')
        if not os.path.exists(dc):
            os.mkdir(dc)
        buildout = {'directory': bo,
                    'download-cache':'download-cache',
                    }
        import zc.buildout.download
        download = zc.buildout.download.Download(
            buildout,
            logger=logger)
        print >> sys.stderr, "Downloading %s" % URL
        fname, is_temp = download(URL)
        dest = self.wdPath('extract')
        print >> sys.stderr, "Extracting %s" % fname
        setuptools.archive_util.unpack_archive(fname, dest)
        root = os.path.join(dest, os.listdir(dest)[0])
        os.rename(root, self.cassandra_home)
        shutil.rmtree(dest)

    def _stop(self):
        if os.path.exists(self.pid_file):
            print >> sys.stderr, "%r stopping cassandra" % self.__name__
            try:
                system('kill -TERM `cat %s`' % self.pid_file)
            except SystemError:
                pass
            os.unlink(self.pid_file)
            # wait until we are down
            while True:
                time.sleep(0.2)
                try:
                    tn =  telnetlib.Telnet('localhost', self.thrift_port)
                    tn.close()
                    print >> sys.stderr, '.',
                except Exception, e:
                    break

    def _cleanup(self):
        for p in (self.var, self.log):
            shutil.rmtree(p)
            os.mkdir(p)

    def _start(self):
        assert not os.path.exists(self.pid_file), 'PID must not exist'
        # remove any data
        self._cleanup()
        print >> sys.stderr, "starting cassandra %r" % self.ctl
        system('sh %s' % self.ctl)
        while True:
            try:
                tn =  telnetlib.Telnet('localhost', self.thrift_port)
                tn.close()
                break
            except Exception, e:
                print >> sys.stderr, '.',
                time.sleep(0.2)

    def setUp(self):
        self._stop()
        self._start()

    def tearDown(self):
        self._stop()

