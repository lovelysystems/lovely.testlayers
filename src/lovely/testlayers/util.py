import os
import types
import socket
import logging

def isUp(host, port):
    """test if a host is up"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ex = s.connect_ex((host, port))
    if ex == 0:
        s.close()
        return True
    return False


def dotted_name(obj):
    return u'.'.join([obj.__module__ ,obj.__name__])


def system(c):

    """execute a system call and raise SystemError on failure

    >>> system('ls')
    >>> system('unknowncommand')
    Traceback (most recent call last):
    ...
    SystemError: ('Failed', 'unknowncommand')

    """

    if os.system(c):
        raise SystemError("Failed", c)


class DuplicateSuppressingLogFilter(logging.Filter):
    """
    Suppress duplicate log messages.
    """

    def __init__(self):
        self.last_message = None

    def filter(self, record):
        outcome = self.last_message != record.msg
        self.last_message = record.msg
        return outcome


# (c) 2005 Ian Bicking and contributors; written for Paste (http://pythonpaste.org)
# Licensed under the MIT license: http://www.opensource.org/licenses/mit-license.php
# From beaker.converters.asbool
def asbool(obj):
    if isinstance(obj, types.StringTypes):
        obj = obj.strip().lower()
        if obj in ['true', 'yes', 'on', 'y', 't', '1']:
            return True
        elif obj in ['false', 'no', 'off', 'n', 'f', '0']:
            return False
        else:
            raise ValueError(
                "String is not true/false: %r" % obj)
    return bool(obj)

