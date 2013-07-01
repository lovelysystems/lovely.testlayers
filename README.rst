Lovely Testing Layers for use with zope.testrunner
**************************************************

This package includes various server test layers for mysql, postgres,
nginx, memcached and cassandra. A generic server layer is also
available for use with any network based server implementation.

Development Setup (MAC)
=======================

Macports need to be installed (http://www.macports.org/install.php)

Make sure your port tree is added to the include paths by adding the
following lines to your ``~/.profile``::

    export C_INCLUDE_PATH=/opt/local/include
    export LIBRARY_PATH=/opt/local/lib

Load your new ``~/.profile``::

    . ~/.profile

Install required ports::

    sudo port install python27 coreutils mysql
