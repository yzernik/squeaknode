import logging
import threading
from abc import ABC
from abc import abstractmethod
from typing import List

from squeaknode.core.squeak_peer import SqueakPeer
from squeaknode.sync.peer_connection import PeerConnection

logger = logging.getLogger(__name__)


class NetworkSync(ABC):

    def __init__(
        self,
        squeak_controller,
        timeout_s,
    ):
        self.squeak_controller = squeak_controller
        self.timeout_s = timeout_s

    @abstractmethod
    def get_peers_to_sync(self) -> List[SqueakPeer]:
        pass

    @abstractmethod
    def sync_peer(self, peer_connection: PeerConnection):
        pass

    def sync(self):
        for peer in self.get_peers_to_sync():
            sync_peer_thread = threading.Thread(
                target=self._sync_peer,
                args=(peer,),
            )
            sync_peer_thread.start()

    def _sync_peer(self, peer: SqueakPeer):
        with PeerConnection(
                self.squeak_controller,
                peer.address,
                self.timeout_s,
        ).open_connection() as peer_connection:
            self.sync_peer(peer_connection)


class DownloadSync(NetworkSync):

    def get_peers_to_sync(self):
        return self.squeak_controller.get_downloading_peers()

    @abstractmethod
    def sync_peer(self, peer_connection: PeerConnection):
        pass


class UploadSync(NetworkSync):

    def get_peers_to_sync(self):
        return self.squeak_controller.get_uploading_peers()

    @abstractmethod
    def sync_peer(self, peer_connection: PeerConnection):
        pass


class TimelineDownloadSync(DownloadSync):

    def __init__(
        self,
        squeak_controller,
        timeout_s,
        block_interval,
    ):
        super().__init__(
            squeak_controller,
            timeout_s,
        )
        self.block_interval = block_interval

    def sync_peer(self, peer_connection: PeerConnection):
        try:
            peer_connection.download(self.block_interval)
        except Exception:
            logger.error(
                "Failed to download timeline from peer: {}".format(
                    peer_connection.peer_address,
                ),
                exc_info=True,
            )


class SingleSqueakDownloadSync(DownloadSync):

    def __init__(
        self,
        squeak_controller,
        timeout_s,
        squeak_hash: bytes,
    ):
        super().__init__(
            squeak_controller,
            timeout_s,
        )
        self.squeak_hash = squeak_hash

    def sync_peer(self, peer_connection: PeerConnection):
        try:
            peer_connection.download_single_squeak(self.squeak_hash)
        except Exception:
            logger.info("Failed to download single squeak: {} from peer: {}".format(
                self.squeak_hash.hex(),
                peer_connection.peer_address,
            ))
            logger.error("Download single squeak error:", exc_info=True)


class TimelineUploadSync(UploadSync):

    def __init__(
        self,
        squeak_controller,
        timeout_s,
    ):
        super().__init__(
            squeak_controller,
            timeout_s,
        )

    def sync_peer(self, peer_connection):
        try:
            peer_connection.upload()
        except Exception:
            logger.error(
                "Failed to upload timeline to peer: {}".format(
                    peer_connection.peer_address,
                ),
                exc_info=True,
            )


class SingleSqueakUploadSync(UploadSync):

    def __init__(
        self,
        squeak_controller,
        timeout_s,
        squeak_hash: bytes,
    ):
        super().__init__(
            squeak_controller,
            timeout_s,
        )
        self.squeak_hash = squeak_hash

    def sync_peer(self, peer_connection):
        try:
            peer_connection.upload_single_squeak(self.squeak_hash)
        except Exception:
            logger.info("Failed to upload single squeak: {} from peer: {}".format(
                self.squeak_hash.hex(),
                peer_connection.peer_address,
            ))
