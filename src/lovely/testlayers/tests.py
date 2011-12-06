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

import unittest
import doctest
from layer import cleanAll
import os

here = os.path.abspath(os.path.dirname(__file__))


def project_path(*path):
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(here))),
        *path)

def setUp(test):
    test.globs['project_path'] = project_path

def cleanWorkDirs(test):
    setUp(test)
    cleanAll()

def create_suite(testfile, setUp=setUp,
                 optionflags=doctest.NORMALIZE_WHITESPACE|doctest.ELLIPSIS,
                 level=None, **kwargs):
    s = doctest.DocFileSuite(
        testfile, setUp=setUp,
        optionflags=optionflags,
        **kwargs
        )
    if level:
        s.level = level
    return s

def test_suite():
    suites = (
        create_suite('layer.txt', setUp=cleanWorkDirs),
        create_suite('memcached.txt'),
        create_suite('server.txt'),
        # the cassandra test needs an internet connection for downloading cassandra
        create_suite('cass.txt', level=3),
        create_suite('pgsql.txt'),
        # needs a mysql installation
        create_suite('mysql.txt', setUp=cleanWorkDirs, level=2),
        create_suite('nginx.txt')
        )
    return unittest.TestSuite(suites)

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')

