import logging
import threading
from typing import List
from typing import Optional

import sqlalchemy
from squeak.core import CheckSqueak
from squeak.core import CSqueak
from squeak.core.signing import CSigningKey
from squeak.core.signing import CSqueakAddress
from squeak.messages import msg_getdata
from squeak.messages import msg_getsqueaks
from squeak.messages import msg_sharesqueaks
from squeak.messages import MsgSerializable
from squeak.net import CInterested
from squeak.net import CInv
from squeak.net import CSqueakLocator

from squeaknode.core.block_range import BlockRange
from squeaknode.core.offer import Offer
from squeaknode.core.peer_address import PeerAddress
from squeaknode.core.received_offer import ReceivedOffer
from squeaknode.core.received_offer_with_peer import ReceivedOfferWithPeer
from squeaknode.core.received_payment_summary import ReceivedPaymentSummary
from squeaknode.core.sent_offer import SentOffer
from squeaknode.core.sent_payment_summary import SentPaymentSummary
from squeaknode.core.sent_payment_with_peer import SentPaymentWithPeer
from squeaknode.core.squeak_entry_with_profile import SqueakEntryWithProfile
from squeaknode.core.squeak_peer import SqueakPeer
from squeaknode.core.squeak_profile import SqueakProfile
from squeaknode.core.util import get_hash
from squeaknode.core.util import is_address_valid
from squeaknode.network.connection_manager import ConnectionManager
from squeaknode.network.peer_server import PeerServer
from squeaknode.node.received_payments_subscription_client import ReceivedPaymentsSubscriptionClient


logger = logging.getLogger(__name__)


class SqueakController:

    def __init__(
        self,
        squeak_db,
        squeak_core,
        squeak_rate_limiter,
        payment_processor,
        peer_server: PeerServer,
        connection_manager: ConnectionManager,
        config,
    ):
        self.squeak_db = squeak_db
        self.squeak_core = squeak_core
        self.squeak_rate_limiter = squeak_rate_limiter
        self.payment_processor = payment_processor
        self.peer_server = peer_server
        self.connection_manager = connection_manager
        self.config = config

    def save_uploaded_squeak(self, squeak: CSqueak) -> bytes:
        return self.save_squeak(
            squeak,
            require_decryption_key=True,
        )

    def save_downloaded_squeak(self, squeak: CSqueak) -> bytes:
        return self.save_squeak(
            squeak,
            require_decryption_key=False,
        )

    def save_created_squeak(self, squeak: CSqueak) -> bytes:
        return self.save_squeak(
            squeak,
            require_decryption_key=True,
        )

    def save_squeak(
            self,
            squeak: CSqueak,
            require_decryption_key: bool = False,
    ) -> bytes:
        # Check if squeak is valid.
        squeak_entry = self.squeak_core.validate_squeak(squeak)
        # Check if squeak has decryption key.
        if require_decryption_key and not squeak.HasDecryptionKey():
            raise Exception(
                "Squeak must contain decryption key.")
        # Check if rate limit is violated.
        if not self.squeak_rate_limiter.should_rate_limit_allow(squeak):
            raise Exception(
                "Exceeded allowed number of squeaks per address per block.")
        # Save the squeak.
        logger.info("Saving squeak: {}".format(
            get_hash(squeak).hex(),
        ))
        inserted_squeak_hash = self.squeak_db.insert_squeak(
            squeak, squeak_entry.block_header)
        # Unlock the squeak if decryption key exists.
        if squeak.HasDecryptionKey():
            decryption_key = squeak.GetDecryptionKey()
            self.unlock_squeak(
                inserted_squeak_hash,
                decryption_key,
            )
        # Return the squeak hash.
        return inserted_squeak_hash

    def get_squeak(
            self,
            squeak_hash: bytes,
            clear_decryption_key: bool = False,
    ) -> Optional[CSqueak]:
        squeak_entry = self.squeak_db.get_squeak_entry(squeak_hash)
        if squeak_entry is None:
            return None
        squeak = squeak_entry.squeak
        if clear_decryption_key:
            squeak.ClearDecryptionKey()
        return squeak

    def get_squeak_without_decryption_key(
            self,
            squeak_hash: bytes,
    ) -> Optional[CSqueak]:
        return self.get_squeak(squeak_hash, clear_decryption_key=True)

    def lookup_allowed_addresses(self, addresses: List[str]):
        followed_addresses = self.get_followed_addresses()
        return set(followed_addresses) & set(addresses)

    def get_buy_offer(self, squeak_hash: bytes, client_address: PeerAddress) -> Offer:
        # Check if there is an existing offer for the hash/client_addr combination
        sent_offer = self.get_saved_sent_offer(squeak_hash, client_address)
        return self.squeak_core.package_offer(
            sent_offer,
            self.config.lnd.external_host,
            self.config.lnd.port,
        )

    def get_saved_sent_offer(self, squeak_hash: bytes, client_address: PeerAddress) -> SentOffer:
        # Check if there is an existing offer for the hash/client_addr combination
        sent_offer = self.squeak_db.get_sent_offer_by_squeak_hash_and_client(
            squeak_hash,
            client_address,
        )
        if sent_offer:
            return sent_offer
        squeak = self.get_squeak(squeak_hash)
        sent_offer = self.squeak_core.create_offer(
            squeak,
            client_address,
            self.config.core.price_msat,
        )
        self.squeak_db.insert_sent_offer(sent_offer)
        return sent_offer

    def create_signing_profile(self, profile_name: str) -> int:
        if len(profile_name) == 0:
            raise Exception(
                "Profile name cannot be empty.",
            )
        signing_key = CSigningKey.generate()
        verifying_key = signing_key.get_verifying_key()
        address = CSqueakAddress.from_verifying_key(verifying_key)
        signing_key_str = str(signing_key)
        signing_key_bytes = signing_key_str.encode()
        squeak_profile = SqueakProfile(
            profile_id=None,
            profile_name=profile_name,
            private_key=signing_key_bytes,
            address=str(address),
            sharing=True,
            following=True,
            profile_image=None,
        )
        return self.squeak_db.insert_profile(squeak_profile)

    def import_signing_profile(self, profile_name: str, private_key: str) -> int:
        signing_key = CSigningKey(private_key)
        verifying_key = signing_key.get_verifying_key()
        address = CSqueakAddress.from_verifying_key(verifying_key)
        signing_key_str = str(signing_key)
        signing_key_bytes = signing_key_str.encode()
        squeak_profile = SqueakProfile(
            profile_id=None,
            profile_name=profile_name,
            private_key=signing_key_bytes,
            address=str(address),
            sharing=False,
            following=False,
            profile_image=None,
        )
        return self.squeak_db.insert_profile(squeak_profile)

    def create_contact_profile(self, profile_name: str, squeak_address: str) -> int:
        if len(profile_name) == 0:
            raise Exception(
                "Profile name cannot be empty.",
            )
        if not is_address_valid(squeak_address):
            raise Exception(
                "Invalid squeak address: {}".format(
                    squeak_address
                ),
            )
        squeak_profile = SqueakProfile(
            profile_id=None,
            profile_name=profile_name,
            private_key=None,
            address=squeak_address,
            sharing=False,
            following=True,
            profile_image=None,
        )
        return self.squeak_db.insert_profile(squeak_profile)

    def get_signing_profiles(self) -> List[SqueakProfile]:
        return self.squeak_db.get_signing_profiles()

    def get_contact_profiles(self) -> List[SqueakProfile]:
        return self.squeak_db.get_contact_profiles()

    def get_squeak_profile(self, profile_id: int) -> SqueakProfile:
        profile = self.squeak_db.get_profile(profile_id)
        if profile is None:
            raise Exception("Profile not found with id: {}.".format(
                profile_id,
            ))
        return profile

    def get_squeak_profile_by_address(self, address: str) -> SqueakProfile:
        profile = self.squeak_db.get_profile_by_address(address)
        if profile is None:
            raise Exception("Profile not found with address: {}.".format(
                address,
            ))
        return profile

    def get_squeak_profile_by_name(self, name: str) -> SqueakProfile:
        profile = self.squeak_db.get_profile_by_name(name)
        if profile is None:
            raise Exception("Profile not found with name: {}.".format(
                name,
            ))
        return profile

    def set_squeak_profile_following(self, profile_id: int, following: bool) -> None:
        self.squeak_db.set_profile_following(profile_id, following)

    def set_squeak_profile_sharing(self, profile_id: int, sharing: bool) -> None:
        self.squeak_db.set_profile_sharing(profile_id, sharing)

    def rename_squeak_profile(self, profile_id: int, profile_name: str) -> None:
        self.squeak_db.set_profile_name(profile_id, profile_name)

    def delete_squeak_profile(self, profile_id: int) -> None:
        self.squeak_db.delete_profile(profile_id)

    def set_squeak_profile_image(self, profile_id: int, profile_image: bytes) -> None:
        self.squeak_db.set_profile_image(profile_id, profile_image)

    def clear_squeak_profile_image(self, profile_id: int) -> None:
        self.squeak_db.set_profile_image(profile_id, None)

    def get_squeak_profile_private_key(self, profile_id: int) -> bytes:
        profile = self.get_squeak_profile(profile_id)
        if profile.private_key is None:
            raise Exception("Profile with id: {} does not have a private key.".format(
                profile_id
            ))
        return profile.private_key

    def make_squeak(self, profile_id: int, content_str: str, replyto_hash: bytes) -> bytes:
        squeak_profile = self.squeak_db.get_profile(profile_id)
        squeak_entry = self.squeak_core.make_squeak(
            squeak_profile, content_str, replyto_hash)
        return self.save_created_squeak(squeak_entry.squeak)

    def delete_squeak(self, squeak_hash: bytes) -> None:
        num_deleted_offers = self.squeak_db.delete_offers_for_squeak(
            squeak_hash)
        logger.info("Deleted number of offers : {}".format(num_deleted_offers))
        self.squeak_db.delete_squeak(squeak_hash)

    def create_peer(self, peer_name: str, host: str, port: int):
        if len(peer_name) == 0:
            raise Exception(
                "Peer name cannot be empty.",
            )
        port = port or self.config.core.default_peer_rpc_port
        peer_address = PeerAddress(
            host=host,
            port=port,
        )
        squeak_peer = SqueakPeer(
            peer_id=None,
            peer_name=peer_name,
            address=peer_address,
            uploading=False,
            downloading=False,
        )
        return self.squeak_db.insert_peer(squeak_peer)

    def get_peer(self, peer_id: int) -> SqueakPeer:
        peer = self.squeak_db.get_peer(peer_id)
        if peer is None:
            raise Exception("Peer with id {} not found.".format(
                peer_id,
            ))
        return peer

    def get_peers(self):
        return self.squeak_db.get_peers()

    def get_downloading_peers(self) -> List[SqueakPeer]:
        return self.squeak_db.get_downloading_peers()

    def get_uploading_peers(self) -> List[SqueakPeer]:
        return self.squeak_db.get_uploading_peers()

    def set_peer_downloading(self, peer_id: int, downloading: bool):
        self.squeak_db.set_peer_downloading(peer_id, downloading)

    def set_peer_uploading(self, peer_id: int, uploading: bool):
        self.squeak_db.set_peer_uploading(peer_id, uploading)

    def rename_peer(self, peer_id: int, peer_name: str):
        self.squeak_db.set_peer_name(peer_id, peer_name)

    def delete_peer(self, peer_id: int):
        self.squeak_db.delete_peer(peer_id)

    def get_received_offers_with_peer(self, squeak_hash: bytes) -> List[ReceivedOfferWithPeer]:
        return self.squeak_db.get_received_offers_with_peer(squeak_hash)

    def get_received_offer_for_squeak_and_peer(
            self,
            squeak_hash: bytes,
            peer_addresss: PeerAddress,
    ) -> Optional[ReceivedOfferWithPeer]:
        return self.squeak_db.get_received_offer_for_squeak_and_peer(
            squeak_hash,
            peer_addresss,
        )

    def get_buy_offer_with_peer(self, received_offer_id: int) -> ReceivedOfferWithPeer:
        received_offer_with_peer = self.squeak_db.get_offer_with_peer(
            received_offer_id)
        if received_offer_with_peer is None:
            raise Exception("Received offer with id {} not found.".format(
                received_offer_id,
            ))
        return received_offer_with_peer

    def pay_offer(self, received_offer_id: int) -> int:
        # Get the offer from the database
        received_offer_with_peer = self.squeak_db.get_offer_with_peer(
            received_offer_id)
        if received_offer_with_peer is None:
            raise Exception("Received offer with id {} not found.".format(
                received_offer_id,
            ))
        received_offer = received_offer_with_peer.received_offer
        logger.info("Paying received offer: {}".format(received_offer))
        sent_payment = self.squeak_core.pay_offer(received_offer)
        sent_payment_id = self.squeak_db.insert_sent_payment(sent_payment)
        # # Delete the received offer
        # self.squeak_db.delete_offer(sent_payment.payment_hash)
        # Mark the received offer as paid
        self.squeak_db.set_received_offer_paid(
            sent_payment.payment_hash,
            paid=True,
        )
        secret_key = sent_payment.secret_key
        squeak_entry = self.squeak_db.get_squeak_entry(
            received_offer.squeak_hash)
        squeak = squeak_entry.squeak
        # Check the decryption key
        squeak.SetDecryptionKey(secret_key)
        CheckSqueak(squeak)
        # Set the decryption key in the database
        self.unlock_squeak(
            received_offer.squeak_hash,
            secret_key,
        )
        return sent_payment_id

    def unlock_squeak(self, squeak_hash: bytes, secret_key: bytes):
        logger.info("Unlocking squeak: {}".format(
            squeak_hash.hex(),
        ))
        self.squeak_db.set_squeak_decryption_key(
            squeak_hash,
            secret_key,
        )

    def get_sent_payments(self) -> List[SentPaymentWithPeer]:
        return self.squeak_db.get_sent_payments()

    def get_sent_payment(self, sent_payment_id: int) -> SentPaymentWithPeer:
        sent_payment = self.squeak_db.get_sent_payment(sent_payment_id)
        if sent_payment is None:
            raise Exception("Sent payment not found with id: {}.".format(
                sent_payment_id,
            ))
        return sent_payment

    def get_sent_offers(self):
        return self.squeak_db.get_sent_offers()

    def get_received_payments(self):
        return self.squeak_db.get_received_payments()

    def delete_all_expired_received_offers(self):
        num_expired_received_offers = self.squeak_db.delete_expired_received_offers()
        if num_expired_received_offers > 0:
            logger.info("Deleted number of expired received offers: {}".format(
                num_expired_received_offers))

    def delete_all_expired_sent_offers(self):
        sent_offer_retention_s = self.config.core.sent_offer_retention_s
        num_expired_sent_offers = self.squeak_db.delete_expired_sent_offers(
            sent_offer_retention_s,
        )
        if num_expired_sent_offers > 0:
            logger.info(
                "Deleted number of expired sent offers: {}".format(
                    num_expired_sent_offers)
            )

    def subscribe_received_payments(self, initial_index: int, stopped: threading.Event):
        with ReceivedPaymentsSubscriptionClient(
            self.squeak_db,
            initial_index,
            stopped,
        ).open_subscription() as client:
            for payment in client.get_received_payments():
                yield payment

    def get_block_range(self) -> BlockRange:
        max_block = self.squeak_core.get_best_block_height()
        block_interval = self.config.sync.block_interval
        min_block = max(0, max_block - block_interval)
        return BlockRange(min_block, max_block)

    def get_network(self) -> str:
        return self.config.core.network

    # TODO: Rename this method. All it does is unpack.
    def get_offer(self, squeak: CSqueak, offer: Offer, peer_address: PeerAddress) -> ReceivedOffer:
        return self.squeak_core.unpack_offer(squeak, offer, peer_address)

    def get_squeak_entry_with_profile(self, squeak_hash: bytes) -> SqueakEntryWithProfile:
        squeak_entry_with_profile = self.squeak_db.get_squeak_entry_with_profile(
            squeak_hash)
        if squeak_entry_with_profile is None:
            raise Exception("Squeak not found with hash: {}.".format(
                squeak_hash.hex(),
            ))
        return squeak_entry_with_profile

    def get_timeline_squeak_entries_with_profile(self):
        return self.squeak_db.get_timeline_squeak_entries_with_profile()

    def get_liked_squeak_entries_with_profile(self):
        return self.squeak_db.get_liked_squeak_entries_with_profile()

    def get_squeak_entries_with_profile_for_address(
        self, address: str, min_block: int, max_block: int
    ):
        return self.squeak_db.get_squeak_entries_with_profile_for_address(
            address,
            min_block,
            max_block,
        )

    def get_ancestor_squeak_entries_with_profile(self, squeak_hash: bytes):
        return self.squeak_db.get_thread_ancestor_squeak_entries_with_profile(
            squeak_hash,
        )

    def get_reply_squeak_entries_with_profile(self, squeak_hash: bytes):
        return self.squeak_db.get_thread_reply_squeak_entries_with_profile(
            squeak_hash,
        )

    def lookup_squeaks(self, addresses: List[str], min_block: int, max_block: int):
        return self.squeak_db.lookup_squeaks(
            addresses,
            min_block,
            max_block,
        )

    def save_offer(self, received_offer: ReceivedOffer) -> None:
        logger.info("Saving received offer: {}".format(received_offer))
        try:
            self.squeak_db.insert_received_offer(received_offer)
        except sqlalchemy.exc.IntegrityError:
            logger.error("Failed to save offer.")

    def get_followed_addresses(self) -> List[str]:
        followed_profiles = self.squeak_db.get_following_profiles()
        return [profile.address for profile in followed_profiles]

    def get_sharing_addresses(self) -> List[str]:
        sharing_profiles = self.squeak_db.get_sharing_profiles()
        return [profile.address for profile in sharing_profiles]

    def get_received_payment_summary(self) -> ReceivedPaymentSummary:
        return self.squeak_db.get_received_payment_summary()

    def get_sent_payment_summary(self) -> SentPaymentSummary:
        return self.squeak_db.get_sent_payment_summary()

    def reprocess_received_payments(self) -> None:
        self.squeak_db.clear_received_payment_settle_indices()
        self.payment_processor.start_processing()

    def delete_old_squeaks(self):
        squeaks_to_delete = self.squeak_db.get_old_squeaks_to_delete(
            self.config.core.squeak_retention_s,
        )
        for squeak_entry_with_profile in squeaks_to_delete:
            squeak = squeak_entry_with_profile.squeak_entry.squeak
            squeak_hash = get_hash(squeak)
            self.squeak_db.delete_squeak(
                squeak_hash,
            )
            logger.info("Deleted squeak: {}".format(
                squeak_hash.hex(),
            ))

    def like_squeak(self, squeak_hash: bytes):
        logger.info("Liking squeak: {}".format(
            squeak_hash.hex(),
        ))
        self.squeak_db.set_squeak_liked(
            squeak_hash,
        )

    def unlike_squeak(self, squeak_hash: bytes):
        logger.info("Unliking squeak: {}".format(
            squeak_hash.hex(),
        ))
        self.squeak_db.set_squeak_unliked(
            squeak_hash,
        )

    def connect_peer(self, peer_id: int) -> None:
        peer = self.squeak_db.get_peer(peer_id)
        if peer is None:
            raise Exception("Peer with id {} not found.".format(
                peer_id,
            ))
        # TODO
        logger.info("Connect to peer: {}".format(
            peer,
        ))
        self.peer_server.connect_address(peer.address)

    def connect_peers(self) -> None:
        peers = self.squeak_db.get_peers()
        for peer in peers:
            logger.info("Connect to peer: {}".format(
                peer,
            ))
            try:
                self.peer_server.connect_address(peer.address)
            except Exception:
                logger.exception("Failed to connect to peer {}".format(
                    peer,
                ))

    def get_address(self):
        # TODO: Add return type.
        return (self.peer_server.ip, self.peer_server.port)

    def get_connected_peers(self):
        return self.connection_manager.peers

    def lookup_squeaks_for_interest(
            self,
            address: str,
            min_block: int,
            max_block: int,
    ):
        return self.squeak_db.lookup_squeaks(
            [address],
            min_block,
            max_block,
        )

    def filter_known_invs(self, invs):
        ret = []
        for inv in invs:
            if inv.type == 1:
                squeak_entry = self.squeak_db.get_squeak_entry(
                    inv.hash,
                )
                if squeak_entry is None:
                    ret.append(
                        CInv(type=1, hash=inv.hash)
                    )
                elif not squeak_entry.squeak.HasDecryptionKey():
                    ret.append(
                        CInv(type=2, hash=inv.hash)
                    )
        return ret

    def sync_timeline(self):
        block_range = self.get_block_range()
        logger.info("Syncing timeline with block range: {}".format(block_range))
        followed_addresses = self.get_followed_addresses()
        logger.info("Syncing timeline with followed addresses: {}".format(
            followed_addresses))
        interests = [
            CInterested(
                address=CSqueakAddress(address),
                nMinBlockHeight=block_range.min_block,
                nMaxBlockHeight=block_range.max_block,
            )
            for address in followed_addresses
        ]
        locator = CSqueakLocator(
            vInterested=interests,
        )
        getsqueaks_msg = msg_getsqueaks(
            locator=locator,
        )
        # for peer in self.connection_manager.peers:
        #     peer.send_msg(getsqueaks_msg)
        self.broadcast_msg(getsqueaks_msg)

    def download_single_squeak(self, squeak_hash: bytes):
        logger.info("Downloading single squeak: {}".format(
            squeak_hash.hex(),
        ))
        invs = [
            CInv(type=1, hash=squeak_hash)
        ]
        getdata_msg = msg_getdata(
            inv=invs,
        )
        # for peer in self.connection_manager.peers:
        #     peer.send_msg(getdata_msg)
        self.broadcast_msg(getdata_msg)

    def share_squeaks(self):
        block_range = self.get_block_range()
        logger.info("Sharing timeline with block range: {}".format(block_range))
        sharing_addresses = self.get_sharing_addresses()
        logger.info("Sharing squeaks with sharing addresses: {}".format(
            sharing_addresses))
        interests = [
            CInterested(
                address=CSqueakAddress(address),
                nMinBlockHeight=0,
                nMaxBlockHeight=block_range.max_block,
            )
            for address in sharing_addresses
        ]
        locator = CSqueakLocator(
            vInterested=interests,
        )
        sharesqueaks_msg = msg_sharesqueaks(
            locator=locator,
        )
        # for peer in self.connection_manager.peers:
        #     peer.send_msg(sharesqueaks_msg)
        self.broadcast_msg(sharesqueaks_msg)

    def filter_shared_squeak_locator(self, interests: List[CInterested]):
        ret = []
        block_range = self.get_block_range()
        followed_addresses = self.get_followed_addresses()
        for interest in interests:
            if str(interest.address) in followed_addresses:
                min_block = max(interest.nMinBlockHeight,
                                block_range.min_block)
                max_block = min(interest.nMaxBlockHeight,
                                block_range.max_block)
                if min_block <= max_block:
                    ret.append(
                        CInterested(
                            address=interest.address,
                            nMinBlockHeight=min_block,
                            nMaxBlockHeight=max_block,
                        )
                    )
        return ret

    def broadcast_msg(self, msg: MsgSerializable) -> None:
        for peer in self.connection_manager.peers:
            try:
                peer.send_msg(msg)
            except Exception:
                logger.exception("Failed to send msg to peer: {}".format(
                    peer,
                ))

    def disconnect_peer(self, peer_id: int) -> None:
        peer = self.squeak_db.get_peer(peer_id)
        if peer is None:
            raise Exception("Peer with id {} not found.".format(
                peer_id,
            ))
        # TODO
        logger.info("Disconnect peer: {}".format(
            peer,
        ))
        self.peer_server.disconnect_address(peer.address)
