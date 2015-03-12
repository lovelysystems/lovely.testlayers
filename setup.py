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

from setuptools import setup, find_packages
import os

def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

long_description='\n'.join((
        read('README.rst'),
        read('src', 'lovely', 'testlayers', 'layer.txt'),
        read('src', 'lovely', 'testlayers', 'server.txt'),
        read('src', 'lovely', 'testlayers', 'memcached.txt'),
        read('src', 'lovely', 'testlayers', 'nginx.txt'),
        read('src', 'lovely', 'testlayers', 'mail.txt'),
        read('src', 'lovely', 'testlayers', 'cass.txt'),
        read('src', 'lovely', 'testlayers', 'mysql.txt'),
        read('src', 'lovely', 'testlayers', 'pgsql.txt'),
        read('src', 'lovely', 'testlayers', 'mongodb_single.txt'),
        read('src', 'lovely', 'testlayers', 'mongodb_masterslave.txt'),
        read('src', 'lovely', 'testlayers', 'mongodb_replicaset.txt'),
        read('CHANGES.txt'),
        ))

setup(
    name = 'lovely.testlayers',
    version = '0.6.1',
    description="mysql, postgres nginx, memcached cassandra test"+\
                " layers for use with zope.testrunner",
    long_description=long_description,
    packages = find_packages('src'),
    author = "Lovely Systems",
    author_email = 'office@lovelysystems.com',
    package_dir = {'':'src'},
    keywords = "testing zope layer test cassandra memcached",
    license = "Apache License 2.0",
    zip_safe = False,
    url = 'https://github.com/lovelysystems/lovely.testlayers',
    include_package_data = True,
    namespace_packages = ['lovely'],
    extras_require = dict(
        mysql=['MySQL-python'],
        cassandra=['zc.buildout>=1.4'],
        pgsql=['psycopg2',
               'transaction'],
        mongodb=['pymongo==2.5.2']),
    install_requires = ['setuptools']
    )
