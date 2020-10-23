import logging
import sys
from concurrent import futures

import grpc

from proto import squeak_admin_pb2, squeak_admin_pb2_grpc
from squeakserver.server.util import get_hash, get_replyto

logger = logging.getLogger(__name__)


class SqueakAdminServerServicer(squeak_admin_pb2_grpc.SqueakAdminServicer):
    """Provides methods that implement functionality of squeak admin server."""

    def __init__(self, host, port, handler):
        self.host = host
        self.port = port
        self.handler = handler

    def LndGetInfo(self, request, context):
        return self.handler.handle_lnd_get_info()

    def LndWalletBalance(self, request, context):
        return self.handler.handle_lnd_wallet_balance()

    def LndNewAddress(self, request, context):
        address_type = request.type
        return self.handler.handle_lnd_new_address(address_type)

    def LndListChannels(self, request, context):
        return self.handler.handle_lnd_list_channels()

    def LndPendingChannels(self, request, context):
        return self.handler.handle_lnd_pending_channels()

    def LndGetTransactions(self, request, context):
        return self.handler.handle_lnd_get_transactions()

    def LndListPeers(self, request, context):
        return self.handler.handle_lnd_list_peers()

    def LndConnectPeer(self, request, context):
        lightning_address = request.addr
        return self.handler.handle_lnd_connect_peer(lightning_address)

    def LndDisconnectPeer(self, request, context):
        pubkey = request.pub_key
        return self.handler.handle_lnd_disconnect_peer(pubkey)

    def LndOpenChannelSync(self, request, context):
        node_pubkey_string = request.node_pubkey_string
        local_funding_amount = request.local_funding_amount
        sat_per_byte = request.sat_per_byte
        return self.handler.handle_lnd_open_channel_sync(
            node_pubkey_string,
            local_funding_amount,
            sat_per_byte,
        )

    def LndCloseChannel(self, request, context):
        channel_point = request.channel_point
        sat_per_byte = request.sat_per_byte
        return self.handler.handle_lnd_close_channel(
            channel_point,
            sat_per_byte,
        )

    def LndSubscribeChannelEvents(self, request, context):
        return self.handler.handle_lnd_subscribe_channel_events()

    def CreateSigningProfile(self, request, context):
        return self.handler.handle_create_signing_profile(request)

    def CreateContactProfile(self, request, context):
        return self.handler.handle_create_contact_profile(request)

    def GetSigningProfiles(self, request, context):
        return self.handler.handle_get_signing_profiles(request)

    def GetContactProfiles(self, request, context):
        return self.handler.handle_get_contact_profiles(request)

    def GetSqueakProfile(self, request, context):
        reply = self.handler.handle_get_squeak_profile(request)
        if reply is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Profile not found.")
            return squeak_admin_pb2.GetSqueakProfileReply()
        return reply

    def GetSqueakProfileByAddress(self, request, context):
        return self.handler.handle_get_squeak_profile_by_address(request)

    def SetSqueakProfileWhitelisted(self, request, context):
        return self.handler.handle_set_squeak_profile_whitelisted(request)

    def SetSqueakProfileFollowing(self, request, context):
        return self.handler.handle_set_squeak_profile_following(request)

    def SetSqueakProfileSharing(self, request, context):
        return self.handler.handle_set_squeak_profile_sharing(request)

    def DeleteSqueakProfile(self, request, context):
        return self.handler.handle_delete_squeak_profile(request)

    def MakeSqueak(self, request, context):
        return self.handler.handle_make_squeak(request)

    def GetSqueakDisplay(self, request, context):
        return self.handler.handle_get_squeak_display_entry(request)

    def GetFollowedSqueakDisplays(self, request, context):
        return self.handler.handle_get_followed_squeak_display_entries(request)

    def GetAddressSqueakDisplays(self, request, context):
        return self.handler.handle_get_squeak_display_entries_for_address(request)

    def GetAncestorSqueakDisplays(self, request, context):
        return self.handler.handle_get_ancestor_squeak_display_entries(request)

    def DeleteSqueak(self, request, context):
        return self.handler.handle_delete_squeak(request)

    def CreatePeer(self, request, context):
        return self.handler.handle_create_peer(request)

    def GetPeer(self, request, context):
        reply = self.handler.handle_get_squeak_peer(request)
        if reply is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Peer not found.")
            return squeak_admin_pb2.GetPeerReply()
        return reply

    def GetPeers(self, request, context):
        return self.handler.handle_get_squeak_peers(request)

    def SetPeerDownloading(self, request, context):
        return self.handler.handle_set_squeak_peer_downloading(request)

    def SetPeerUploading(self, request, context):
        return self.handler.handle_set_squeak_peer_uploading(request)

    def DeletePeer(self, request, context):
        peer_id = request.peer_id
        self.handler.handle_delete_squeak_peer(peer_id)
        return squeak_admin_pb2.DeletePeerReply()

    def GetBuyOffers(self, request, context):
        squeak_hash_str = request.squeak_hash
        offers = self.handler.handle_get_buy_offers(squeak_hash_str)
        offer_msgs = [self._offer_entry_to_message(offer) for offer in offers]
        logger.info("Returning buy offers: {}".format(offer_msgs))
        return squeak_admin_pb2.GetBuyOffersReply(
            offers=offer_msgs,
        )

    def GetBuyOffer(self, request, context):
        offer_id = request.offer_id
        offer = self.handler.handle_get_buy_offer(offer_id)
        offer_msg = self._offer_entry_to_message(offer)
        logger.info("Returning buy offer: {}".format(offer_msg))
        return squeak_admin_pb2.GetBuyOfferReply(
            offer=offer_msg,
        )

    def SyncSqueaks(self, request, context):
        self.handler.handle_sync_squeaks()
        return squeak_admin_pb2.SyncSqueaksReply()

    def PayOffer(self, request, context):
        offer_id = request.offer_id
        sent_payment_id = self.handler.handle_pay_offer(offer_id)
        return squeak_admin_pb2.PayOfferReply(
            sent_payment_id=sent_payment_id,
        )

    def GetSentPayments(self, request, context):
        sent_payments = self.handler.handle_get_sent_payments()
        sent_payment_msgs = [self._sent_payment_to_message(sent_payment) for sent_payment in sent_payments]
        logger.info("Returning sent payments: {}".format(sent_payment_msgs))
        return squeak_admin_pb2.GetSentPaymentsReply(
            sent_payments=sent_payment_msgs,
        )

    def GetSentPayment(self, request, context):
        sent_payment_id = request.sent_payment_id
        sent_payment = self.handler.handle_get_sent_payment(sent_payment_id)
        sent_payment_msg = self._sent_payment_to_message(sent_payment)
        return squeak_admin_pb2.GetSentPaymentReply(
            sent_payment=sent_payment_msg,
        )

    def _squeak_entry_to_message(self, squeak_entry_with_profile):
        if squeak_entry_with_profile is None:
            return None
        squeak_entry = squeak_entry_with_profile.squeak_entry
        squeak = squeak_entry.squeak
        block_header = squeak_entry.block_header
        is_unlocked = squeak.HasDecryptionKey()
        content_str = squeak.GetDecryptedContentStr() if is_unlocked else None
        squeak_profile = squeak_entry_with_profile.squeak_profile
        is_author_known = squeak_profile is not None
        author_name = squeak_profile.profile_name if squeak_profile else None
        author_address = str(squeak.GetAddress())
        is_reply = squeak.is_reply
        reply_to = get_replyto(squeak).hex() if is_reply else None
        return squeak_admin_pb2.SqueakDisplayEntry(
            squeak_hash=get_hash(squeak).hex(),
            is_unlocked=squeak.HasDecryptionKey(),
            content_str=content_str,
            block_height=squeak.nBlockHeight,
            block_time=block_header.nTime,
            is_author_known=is_author_known,
            author_name=author_name,
            author_address=author_address,
            is_reply=is_reply,
            reply_to=reply_to,
        )

    def _squeak_profile_to_message(self, squeak_profile):
        if squeak_profile is None:
            return None
        has_private_key = squeak_profile.private_key is not None
        return squeak_admin_pb2.SqueakProfile(
            profile_id=squeak_profile.profile_id,
            profile_name=squeak_profile.profile_name,
            has_private_key=has_private_key,
            address=squeak_profile.address,
            sharing=squeak_profile.sharing,
            following=squeak_profile.following,
            whitelisted=squeak_profile.whitelisted,
        )

    def _squeak_peer_to_message(self, squeak_peer):
        if squeak_peer is None:
            return None
        return squeak_admin_pb2.SqueakPeer(
            peer_id=squeak_peer.peer_id,
            peer_name=squeak_peer.peer_name,
            host=squeak_peer.host,
            port=squeak_peer.port,
            uploading=squeak_peer.uploading,
            downloading=squeak_peer.downloading,
        )

    def _offer_entry_to_message(self, offer_entry):
        if offer_entry is None:
            return None
        offer = offer_entry.offer
        peer = self._squeak_peer_to_message(offer_entry.peer)
        return squeak_admin_pb2.OfferDisplayEntry(
            offer_id=offer.offer_id,
            squeak_hash=offer.squeak_hash,
            amount=offer.price_msat,
            node_pubkey=offer.destination,
            node_host=offer.node_host,
            node_port=offer.node_port,
            peer=peer,
            invoice_timestamp=offer.invoice_timestamp,
            invoice_expiry=offer.invoice_expiry,
        )

    def _sent_payment_to_message(self, sent_payment):
        if sent_payment is None:
            return None
        logger.info("sent_payment: {}".format(sent_payment))
        return squeak_admin_pb2.SentPayment(
            sent_payment_id=sent_payment.sent_payment_id,
            offer_id=sent_payment.offer_id,
            peer_id=sent_payment.peer_id,
            squeak_hash=sent_payment.squeak_hash,
            preimage_hash=sent_payment.preimage_hash,
            preimage=sent_payment.preimage,
            amount=sent_payment.amount,
            node_pubkey=sent_payment.node_pubkey,
            preimage_is_valid=sent_payment.preimage_is_valid,
        )

    def serve(self):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        squeak_admin_pb2_grpc.add_SqueakAdminServicer_to_server(self, server)
        server.add_insecure_port("{}:{}".format(self.host, self.port))
        server.start()
        server.wait_for_termination()
