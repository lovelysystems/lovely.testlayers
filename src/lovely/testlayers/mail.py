# Shared Source Software
# Copyright (c) 2006 - 2012 Lovely Systems GmbH

import asyncore
from threading import Thread
from smtpd import SMTPServer
from collections import defaultdict, deque


class Mailbox(object):

    def __init__(self):
        self.messages = deque()

    def append(self, message):
        self.messages.append(message)

    def is_empty(self):
        """ use to verify that the mailbox is empty

        returns True or False
        """
        return not (self.messages and True or False)

    def popleft(self):
        """
        returns the first message that was received and removes that message
        from the mailbox.

        or none if no message was received
        """
        if self.is_empty():
            return None
        return self.messages.popleft()

    def pop(self):
        """
        returns the last message that was received and removes that message
        from the mailbox.

        or none if no message was received
        """
        if self.is_empty():
            return None
        return self.messages.pop()


class SMTPServerHandler(SMTPServer):
    def __init__(self, localaddr, remoteaddr):
        SMTPServer.__init__(self, localaddr, remoteaddr)
        self.mboxes = defaultdict(Mailbox)

    def process_message(self, peer, mailfrom, rcpttos, data):
        for recipient in rcpttos:
            self.mboxes[recipient].append(data)

    def mbox(self, recipient):
        if recipient in self.mboxes:
            return self.mboxes[recipient]
        return Mailbox()


class SMTPServerLayer(object):

    __bases__ = ()
    smtpd = None

    def __init__(self, name='smtpd', port=1025):
        self.__name__ = name
        self.port = port

    def setUp(self):
        """start the stmpd server layer"""
        self.smtpd = SMTPServerHandler(('localhost', self.port), None)
        self.thread = Thread(target=asyncore.loop, kwargs={'timeout': 1})
        self.thread.start()

    def tearDown(self):
        """
        stops the smtp server.

        This method will block if there are any connections left open.
        """
        self.smtpd.close()
        self.thread.join()
        self.smtpd = None

    @property
    def server(self):
        return self.smtpd
