from typing import NamedTuple
from typing import Optional

from squeaknode.core.peer_address import PeerAddress


class SentOffer(NamedTuple):
    """Represents an offer generated by a seller to be sent."""
    sent_offer_id: Optional[int]
    squeak_hash: bytes
    payment_hash: bytes
    secret_key: bytes
    nonce: bytes
    price_msat: int
    payment_request: str
    invoice_time: int
    invoice_expiry: int
    client_addr: PeerAddress
