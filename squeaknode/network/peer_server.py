import logging
import socket
import threading

import squeak.params


MIN_PEERS = 5
MAX_PEERS = 10
UPDATE_THREAD_SLEEP_TIME = 10


logger = logging.getLogger(__name__)


class PeerServer(object):
    """Maintains connections to other peers in the network.
    """

    def __init__(self, connection_manager, port=None):
        self.ip = socket.gethostbyname('localhost')
        self.port = port or squeak.params.params.DEFAULT_PORT
        self.connection_manager = connection_manager

    def start(self, peer_handler):
        self.peer_handler = peer_handler

        # Start Listen thread
        threading.Thread(target=self.accept_connections).start()

    def stop(self):
        # TODO: stop accepting connections thread.
        # TODO: stop every peer in connection manager.
        pass

    def accept_connections(self):
        listen_socket = socket.socket()
        listen_socket.bind(('', self.port))
        listen_socket.listen()
        while True:
            peer_socket, address = listen_socket.accept()
            peer_socket.setblocking(True)
            self.handle_connection(peer_socket, address, outgoing=False)

    def make_connection(self, ip, port):
        address = (ip, port)
        logger.debug('Making connection to {}'.format(address))
        logger.info('Making connection to {}'.format(address))
        try:
            peer_socket = socket.socket()
            logger.info('Got socket to {}'.format(address))
            peer_socket.connect(address)
            peer_socket.setblocking(True)
            self.handle_connection(peer_socket, address, outgoing=True)
        except Exception:
            logger.exception('Failed to make connection to {}'.format(address))

    def handle_connection(self, peer_socket, address, outgoing):
        threading.Thread(
            target=self.peer_handler.start,
            args=(peer_socket, address, outgoing,),
        ).start()

    def connect_address(self, address):
        """Connect to new address."""
        logger.debug('Connecting to peer with address {}'.format(address))
        logger.info('Connecting to peer with address {}'.format(address))
        hostname, port = address
        ip = socket.gethostbyname(hostname)
        new_address = (ip, port)
        if self.connection_manager.has_connection(new_address):
            return
        logger.info('Connecting to peer with ip address {}'.format(ip))
        threading.Thread(
            target=self.make_connection,
            args=(ip, port),
        ).start()

    def disconnect_address(self, address):
        """Connect to new address."""
        logger.info('Disconnecting peer with address {}'.format(address))
        hostname, port = address
        ip = socket.gethostbyname(hostname)
        new_address = (ip, port)
        peer = self.connection_manager.get_peer(new_address)
        if peer is None:
            return
        peer.stop()
