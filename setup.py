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

long_description=(
        'Lovely Testing Layers for use with zope.testing\n'
        '***********************************************\n'
        + '\n' +
        read('src', 'lovely', 'testlayers', 'layer.txt')
        + '\n' +
        read('src', 'lovely', 'testlayers', 'memcached.txt')
        + '\n' +
        read('src', 'lovely', 'testlayers', 'nginx.txt')
        + '\n' +
        read('src', 'lovely', 'testlayers', 'cass.txt')
        + '\n'
        )

open('doc.txt', 'w').write(long_description)

setup(
    name = 'lovely.testlayers',
    version = '0.1.0a3',
    description="Testing Layers for use with zope.testing",
    long_description=long_description,
    packages = find_packages('src'),
    author = "Lovely Systems",
    author_email = 'office@lovelysystems.com',
    package_dir = {'':'src'},
    keywords = "testing zope layer test cassandra memcached",
    license = "Apache License 2.0",
    zip_safe = True,
    url = 'http://code.google.com/p/lovely-testlayers/',
    include_package_data = True,
    namespace_packages = ['lovely'],
    extras_require = dict(
        mysql=['MySQL-python'],
        pgsql=['psycopg2']),
    install_requires = ['setuptools',
                        'zope.testing',
                        'zc.buildout>=1.4',
                        'transaction',
                        ]
    )
