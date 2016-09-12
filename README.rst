**************************************************
Lovely Testing Layers for use with zope.testrunner
**************************************************

Introduction
============
This package includes various server test layers and
a generic server layer for use with any network based
server implementation.

It currently provides server layers for these fine
database and web servers (in alphabetical order):

- ApacheDS
- Cassandra
- Memcached
- MongoDB
- MySQL
- Nginx
- OpenLDAP
- PostgreSQL


Setup
=====
While there are buildout targets based on ``hexagonit.recipe.cmmi`` and
``zc.recipe.cmmi`` included for building PostgreSQL and Memcached inline,
it is perfectly fine to use the native system installments of the
respective services.


Self-tests
==========
``lovely.testlayers`` ships with a bunch of built-in self-tests
for verifying the functionality of the respective test layers.

To get started on that, please follow up reading `<TESTS.rst>`__.

