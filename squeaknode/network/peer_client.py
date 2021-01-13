import logging
from contextlib import contextmanager
from typing import List

import grpc
from squeak.core import CheckSqueak
from squeak.core import CSqueak

from proto import squeak_server_pb2
from proto import squeak_server_pb2_grpc
from squeaknode.core.util import get_hash
from squeaknode.sync.lookup_response import LookupResponse

logger = logging.getLogger(__name__)


class PeerClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    @contextmanager
    def get_stub(self):
        host_port_str = "{}:{}".format(self.host, self.port)
        with grpc.insecure_channel(host_port_str) as server_channel:
            yield squeak_server_pb2_grpc.SqueakServerStub(server_channel)

    def lookup_squeaks(self, addresses: List[str], min_block: int, max_block: int):
        with self.get_stub() as stub:
            lookup_response = stub.LookupSqueaks(
                squeak_server_pb2.LookupSqueaksRequest(
                    addresses=addresses,
                    min_block=min_block,
                    max_block=max_block,
                )
            )
            return LookupResponse(
                # hashes=[
                #     bytes.fromhex(hash)
                #     for hash in lookup_response.hashes],
                hashes=lookup_response.hashes,
                allowed_addresses=lookup_response.allowed_addresses,
            )

    def post_squeak(self, squeak: CSqueak):
        squeak_msg = self._build_squeak_msg(squeak)
        with self.get_stub() as stub:
            stub.PostSqueak(
                squeak_server_pb2.PostSqueakRequest(
                    squeak=squeak_msg,
                )
            )

    def get_squeak(self, squeak_hash: bytes):
        with self.get_stub() as stub:
            get_response = stub.GetSqueak(
                squeak_server_pb2.GetSqueakRequest(
                    hash=squeak_hash,
                )
            )
            get_response_squeak = self._squeak_from_msg(get_response.squeak)
            CheckSqueak(get_response_squeak, skipDecryptionCheck=True)
            return get_response_squeak

    def buy_squeak(self, squeak_hash: bytes):
        with self.get_stub() as stub:
            buy_response = stub.GetOffer(
                squeak_server_pb2.GetOfferRequest(
                    hash=squeak_hash,
                )
            )
            offer_msg = buy_response.offer
            return offer_msg

    # TODO: use bytes, not string
    def _build_squeak_msg(self, squeak: CSqueak):
        return squeak_server_pb2.Squeak(
            hash=get_hash(squeak).hex(),
            serialized_squeak=squeak.serialize(),
        )

    def _squeak_from_msg(self, squeak_msg: squeak_server_pb2.Squeak):
        if not squeak_msg:
            return None
        if not squeak_msg.serialized_squeak:
            return None
        return CSqueak.deserialize(squeak_msg.serialized_squeak)
