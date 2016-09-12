============================
lovely.testlayers self-tests
============================


Setup
=====

Prerequisites
-------------
This package should work on all *nix systems providing
a decent Python installation.


Macports
--------
On Mac OS X, let's go for Macports (http://www.macports.org/install.php),
while Homebrew should also be fine.

Make sure your port tree is added to the include paths by adding the
following lines to your ``~/.profile``::

    export C_INCLUDE_PATH=/opt/local/include
    export LIBRARY_PATH=/opt/local/lib

Load your new ``~/.profile``::

    . ~/.profile

Install required ports, e.g.::

    sudo port install python27 coreutils mysql


Development sandbox
-------------------
This project uses buildout, so in order to start developing run the
following in this directory::

    python bootstrap.py
    ./bin/buildout



Basics
======


Run tests
---------
To run tests use::

    ./bin/test

Note that some tests require internet access and are not run by
default. To run all tests use::

    ./bin/test --all

To run individual tests, use e.g.::

    bin/test --test=memcached


Run tests with tox
------------------
To test against multiple python versions tox can be used. The python
interpreter need to be available in the `$PATH` variable as `python2.7`,
`python3.3` and `pypy`. Execute tox using::

    ./bin/tox

To limit the tox test to a single python interpreter use it like this::

    ./bin/tox -e py27



Modules
=======
There are additional self-tests decoupled from the default ``buildout.cfg``
sections in form of "modules". Please read along about how there setup and
operation works.


MongoDB
-------
The MongoDB tests are separated and by default not included if buildout is run.
To install MongoDB and its test suite, execute::

    bin/buildout install mongodb mongodb-test

And then run the tests with::

    bin/test-mongodb --suite-name=mongodb_suite


LDAP in general
---------------
For testing LDAP servers, we use the fine Python module ``python-ldap``. For installing
it, there are a bunch of dependencies to be satisfied, as it requires to be compiled
against the libldap headers. Additionally, the ``ldapadd`` utility is mandatory for
provisioning the directory servers with .ldif files, which comes from the OpenLDAP
distribution. So please install it even when running the ApacheDS self-tests.

Debian Linux::

    aptitude install build-essential python-dev libldap2-dev libsasl2-dev openldap-utils

CentOS Linux::

    yum install gcc gcc-c++ make python-devel openldap-devel cyrus-sasl-devel openldap-clients


OpenLDAP
--------
The OpenLDAP tests are separated and by default not included if buildout is run.
To install the OpenLDAP test suite, execute::

    bin/buildout install openldap-test

And then run the tests with::

    bin/test-openldap


The relevant OpenLDAP system packages are not installed by buildout and have to be installed separately.

Debian Linux::

    aptitude install slapd

CentOS Linux::

    yum install openldap-servers

Mac OS X, Macports::

    sudo port install openldap


ApacheDS
--------
The ApacheDS tests are separated and by default not included if buildout is run.
To install the ApacheDS test suite, execute::

    bin/buildout install apacheds-test

And then run the tests with::

    bin/test-apacheds


The relevant ApacheDS system packages are not installed by buildout and have to be installed separately.

    - https://directory.apache.org/apacheds/downloads.html

Also, a Java runtime is required.

Debian Linux::

    aptitude install default-jre-headless

CentOS Linux::

    yum install java-1.8.0-openjdk-headless

