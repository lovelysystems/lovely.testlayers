import os
import socket

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
