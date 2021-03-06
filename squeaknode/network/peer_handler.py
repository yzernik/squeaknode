import logging

from squeaknode.network.connection import Connection
from squeaknode.network.connection_manager import ConnectionManager
from squeaknode.network.peer import Peer
from squeaknode.node.squeak_controller import SqueakController


logger = logging.getLogger(__name__)


class PeerHandler():
    """Handles new peer connection.
    """

    def __init__(
            self,
            squeak_controller: SqueakController,
            connection_manager: ConnectionManager,
    ):
        super().__init__()
        self.squeak_controller = squeak_controller
        self.connection_manager = connection_manager

    def start(self, peer_socket, address, outgoing):
        """Handles all sending and receiving of messages for the given peer.

        This method blocks until the peer connection has stopped.
        """
        logger.debug(
            'Setting up controller for peer address {} ...'.format(address))
        logger.info(
            'Setting up controller for peer address {} ...'.format(address))
        with Peer(peer_socket, address, outgoing) as p:
            with Connection(p, self.squeak_controller, self.connection_manager).open_connection() as c:
                # p.stopped.wait()
                c.handle_messages()
        logger.debug('Stopped controller for peer address {}.'.format(address))
        logger.info('Stopped controller for peer address {}.'.format(address))


# class PeerListener(PeerMessageHandler):
#     """Handles receiving messages from a peer.
#     """

#     def __init__(self, peer_message_handler) -> None:
#         self.peer_message_handler = peer_message_handler

#     def listen_msgs(self):
#         while True:
#             try:
#                 self.peer_message_handler.handle_msgs()
#             except Exception as e:
#                 logger.exception('Error in handle_msgs: {}'.format(e))
#                 return


# class PeerHandshaker(Connection):
#     """Handles the peer handshake.
#     """

#     def __init__(self, peer, connection_manager, peer_server, squeaks_access) -> None:
#         super().__init__(peer, connection_manager, peer_server, squeaks_access)

#     def hanshake(self):
#         # Initiate handshake with the peer if the connection is outgoing.
#         if self.peer.outgoing:
#             self.initiate_handshake()

#         # Sleep for 10 seconds.
#         time.sleep(10)

#         # Disconnect from peer if handshake is not complete.
#         if self.peer.has_handshake_timeout():
#             logger.info('Closing peer because of handshake timeout {}'.format(self.peer))
#             self.peer.close()


# class PeerPingChecker():
#     """Handles receiving messages from a peer.
#     """

#     def __init__(self, peer_message_handler) -> None:
#         super().__init__()
#         self.peer_message_handler = peer_message_handler

#     def handle_msgs(self):
#         while True:
#             try:
#                 self.peer_message_handler.handle_msgs()
#             except Exception as e:
#                 logger.exception('Error in handle_msgs: {}'.format(e))
#                 return
