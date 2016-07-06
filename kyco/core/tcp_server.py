"""Basic TCP Server that will listen to port 6633."""
import logging

from socketserver import ThreadingMixIn
from socketserver import BaseRequestHandler
from socketserver import TCPServer
from struct import unpack
from threading import current_thread

# TODO: Fix version scheme
from pyof.v0x01.common.header import Header

from kyco.events import KycoRawConnectionUp
from kyco.events import KycoRawConnectionDown
from kyco.events import KycoRawOpenFlowMessageIn

__all__ = ['KycoServer', 'KycoOpenFlowRequestHandler']

log = logging.getLogger('Kyco')


class KycoServer(ThreadingMixIn, TCPServer):
    # daemon_threads = True
    allow_reuse_address = True
    main_threads = {}

    def __init__(self, server_address, RequestHandlerClass,
                 controller_put_raw_event):
        super().__init__(server_address, RequestHandlerClass,
                         bind_and_activate=False)
        # Registering the register_event 'endpoint' on the server to be
        #   accessed on the RequestHandler
        self.controller_put_raw_event = controller_put_raw_event

    def serve_forever(self, poll_interval=0.5):
        try:
            self.server_bind()
            self.server_activate()
            log.info("Kyco listening at {}:{}".format(self.server_address[0],
                                                      self.server_address[1]))
            super().serve_forever(poll_interval)
        except:
            self.server_close()
            raise


class KycoOpenFlowRequestHandler(BaseRequestHandler):
    """The socket/request handler class for our controller.

    It is instantiated once per connection between each switche and the
    controller.
    The setup class will dispatch a KycoEvent (SwitchUp?) on the controller,
    that will be processed by the Controller Core (or a Core App).
    The finish class will close the connection and dispatch a KytonEvents
    (SwitchDown?) on the controller. Or this method will be called by the
    handler of this (SwitchDown) event?
    """
    def setup(self):
        self.ip = self.client_address[0]
        self.port = self.client_address[1]
        context = {'connection': (self.ip, self.port),
                   'socket': self.request}
        event = KycoRawConnectionUp(context)
        self.server.controller_put_raw_event(event)
        log.debug("New connection {}:{}".format(self.ip, self.port))

    def handle(self):
        curr_thread = current_thread()
        header_length = 8
        while True:
            raw_header = None
            buff = b''

            raw_header = self.request.recv(header_length)
            print(len(raw_header))
            buff += raw_header
            log.debug("New message from {}:{} at thread "
                      "{}".format(self.ip, self.port, curr_thread.name))

            header = Header()
            header.unpack(raw_header)
            # Just to close the sock with CTRL+C or CTRL+D
            # if header == 255 or header == 4:
            #     log.info('Closing connection')
            #     self.request.close()
            #     break

            # This is just for now, will be changed soon....
            message_size = header.length - header_length
            if message_size > 0:
                log.debug('Reading the buffer')
                buff += self.request.recv(message_size)

            context = {'connection': (self.ip, self.port),
                       'header': header,
                       'buff': buff}
            event = KycoRawOpenFlowMessageIn(context)
            self.server.controller_put_raw_event(event)

    def finish(self):
        log.debug("Connection lost from {}:{}".format(self.ip, self.port))
        context = {'connection': (self.ip, self.port)}
        event = KycoRawConnectionDown(context)
        self.server.controller_put_raw_event(event)
