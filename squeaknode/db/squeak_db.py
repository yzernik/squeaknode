import logging
from contextlib import contextmanager
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Iterator
from typing import List
from typing import Optional

import sqlalchemy
from bitcoin.core import CBlockHeader
from sqlalchemy import func
from sqlalchemy import literal
from sqlalchemy.sql import and_
from sqlalchemy.sql import select
from squeak.core import CSqueak

from squeaknode.bitcoin.util import parse_block_header
from squeaknode.core.lightning_address import LightningAddressHostPort
from squeaknode.core.peer_address import PeerAddress
from squeaknode.core.received_offer import ReceivedOffer
from squeaknode.core.received_offer_with_peer import ReceivedOfferWithPeer
from squeaknode.core.received_payment import ReceivedPayment
from squeaknode.core.received_payment_summary import ReceivedPaymentSummary
from squeaknode.core.sent_offer import SentOffer
from squeaknode.core.sent_payment import SentPayment
from squeaknode.core.sent_payment_summary import SentPaymentSummary
from squeaknode.core.sent_payment_with_peer import SentPaymentWithPeer
from squeaknode.core.squeak_entry import SqueakEntry
from squeaknode.core.squeak_entry_with_profile import SqueakEntryWithProfile
from squeaknode.core.squeak_peer import SqueakPeer
from squeaknode.core.squeak_profile import SqueakProfile
from squeaknode.core.util import get_hash
from squeaknode.db.exception import DuplicateReceivedPaymentError
from squeaknode.db.migrations import run_migrations
from squeaknode.db.models import Models


logger = logging.getLogger(__name__)


class SqueakDb:
    def __init__(self, engine, schema=None):
        self.engine = engine
        self.schema = schema
        self.models = Models(schema=schema)

    @contextmanager
    def get_connection(self):
        with self.engine.connect() as connection:
            yield connection

    def init(self):
        """ Create the tables and indices in the database. """
        logger.debug("SqlAlchemy version: {}".format(sqlalchemy.__version__))
        run_migrations(self.engine)

    @property
    def squeaks(self):
        return self.models.squeaks

    @property
    def profiles(self):
        return self.models.profiles

    @property
    def peers(self):
        return self.models.peers

    @property
    def received_offers(self):
        return self.models.received_offers

    @property
    def sent_payments(self):
        return self.models.sent_payments

    @property
    def received_payments(self):
        return self.models.received_payments

    @property
    def sent_offers(self):
        return self.models.sent_offers

    @property
    def squeak_has_secret_key(self):
        return self.squeaks.c.secret_key != None  # noqa: E711

    @property
    def squeak_is_liked(self):
        return self.squeaks.c.liked

    @property
    def squeak_is_not_liked(self):
        return self.squeaks.c.liked == False  # noqa: E711

    @property
    def squeak_has_no_secret_key(self):
        return self.squeaks.c.secret_key == None  # noqa: E711

    def squeak_is_older_than_retention(self, interval_s):
        return self.datetime_now - timedelta(seconds=interval_s) > \
            self.squeaks.c.created

    @property
    def profile_has_private_key(self):
        return self.profiles.c.private_key != None  # noqa: E711

    @property
    def profile_has_no_private_key(self):
        return self.profiles.c.private_key == None  # noqa: E711

    @property
    def received_offer_does_not_exist(self):
        return self.received_offers.c.squeak_hash == None  # noqa: E711

    @property
    def datetime_now(self):
        return datetime.now(timezone.utc)

    # def squeak_newer_than_interval_s(self, interval_s):
    #     return self.squeaks.c.created > \
    #         self.datetime_now - timedelta(seconds=interval_s)

    def received_offer_should_be_deleted(self):
        expire_time = (
            self.received_offers.c.invoice_timestamp
            + self.received_offers.c.invoice_expiry
        )
        return self.datetime_now.timestamp() >= expire_time

    @property
    def received_offer_is_not_paid(self):
        return self.received_offers.c.paid == False  # noqa: E711

    @property
    def received_offer_is_not_expired(self):
        expire_time = (
            self.received_offers.c.invoice_timestamp
            + self.received_offers.c.invoice_expiry
        )
        return self.datetime_now.timestamp() < expire_time

    def sent_offer_should_be_deleted(self, interval_s):
        expire_time = (
            self.sent_offers.c.invoice_timestamp
            + self.sent_offers.c.invoice_expiry
        )
        return self.datetime_now.timestamp() >= expire_time + interval_s

    @property
    def sent_offer_is_not_paid(self):
        return self.sent_offers.c.paid == False  # noqa: E711

    @property
    def sent_offer_is_not_expired(self):
        expire_time = (
            self.sent_offers.c.invoice_timestamp
            + self.sent_offers.c.invoice_expiry
        )
        return self.datetime_now.timestamp() < expire_time

    def insert_squeak(self, squeak: CSqueak, block_header: CBlockHeader) -> bytes:
        """ Insert a new squeak.
        TODO: Clear the decryption key from the serialized bytes
        without modifying the passed squeak object.

        Return the hash (bytes) of the inserted squeak.
        """
        ins = self.squeaks.insert().values(
            hash=get_hash(squeak).hex(),
            squeak=squeak.serialize(),
            hash_reply_sqk=squeak.hashReplySqk.hex(),
            hash_block=squeak.hashBlock.hex(),
            n_block_height=squeak.nBlockHeight,
            n_time=squeak.nTime,
            author_address=str(squeak.GetAddress()),
            secret_key=None,
            block_header=block_header.serialize(),
        )
        with self.get_connection() as connection:
            try:
                connection.execute(ins)
                # inserted_squeak_hash = res.inserted_primary_key[0]
            except sqlalchemy.exc.IntegrityError:
                pass
            return get_hash(squeak)

    def get_squeak_entry(self, squeak_hash: bytes) -> Optional[SqueakEntry]:
        """ Get a squeak. """
        s = select([self.squeaks]).where(
            self.squeaks.c.hash == squeak_hash.hex())
        with self.get_connection() as connection:
            result = connection.execute(s)
            row = result.fetchone()
            if row is None:
                return None
            return self._parse_squeak_entry(row)

    def get_squeak_entry_with_profile(self, squeak_hash: bytes) -> Optional[SqueakEntryWithProfile]:
        """ Get a squeak with the author profile. """
        s = (
            select([self.squeaks, self.profiles])
            .select_from(
                self.squeaks.outerjoin(
                    self.profiles,
                    self.profiles.c.address == self.squeaks.c.author_address,
                )
            )
            .where(self.squeaks.c.hash == squeak_hash.hex())
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            row = result.fetchone()
            if row is None:
                return None
            return self._parse_squeak_entry_with_profile(row)

    def get_timeline_squeak_entries_with_profile(
            self,
            only_liked: bool = False,
    ) -> List[SqueakEntryWithProfile]:
        """ Get all followed squeaks. """
        s = (
            select([self.squeaks, self.profiles])
            .select_from(
                self.squeaks.outerjoin(
                    self.profiles,
                    self.profiles.c.address == self.squeaks.c.author_address,
                )
            )
            .where(
                or_(
                    self.squeak_is_liked,
                    not only_liked,
                )
            )
            .order_by(
                self.squeaks.c.n_block_height.desc(),
                self.squeaks.c.n_time.desc(),
            )
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            return [self._parse_squeak_entry_with_profile(row) for row in rows]

    def get_squeak_entries_with_profile_for_address(
        self, address: str, min_block: int, max_block: int
    ) -> List[SqueakEntryWithProfile]:
        """ Get a squeak. """
        s = (
            select([self.squeaks, self.profiles])
            .select_from(
                self.squeaks.outerjoin(
                    self.profiles,
                    self.profiles.c.address == self.squeaks.c.author_address,
                )
            )
            .where(self.squeaks.c.author_address == address)
            .where(self.squeaks.c.n_block_height >= min_block)
            .where(self.squeaks.c.n_block_height <= max_block)
            .order_by(
                self.squeaks.c.n_block_height.desc(),
                self.squeaks.c.n_time.desc(),
            )
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            return [self._parse_squeak_entry_with_profile(row) for row in rows]

    def get_thread_ancestor_squeak_entries_with_profile(self, squeak_hash: bytes) -> List[SqueakEntryWithProfile]:
        """ Get all reply ancestors of squeak hash. """
        ancestors = (
            select(
                [
                    self.squeaks.c.hash.label("hash"),
                    literal(0).label("depth"),
                ]
            )
            .where(self.squeaks.c.hash == squeak_hash.hex())
            .cte(recursive=True)
        )

        ancestors_alias = ancestors.alias()
        squeaks_alias = self.squeaks.alias()

        ancestors = ancestors.union_all(
            select(
                [
                    squeaks_alias.c.hash_reply_sqk.label("hash"),
                    (ancestors_alias.c.depth + 1).label("depth"),
                ]
            ).where(squeaks_alias.c.hash == ancestors_alias.c.hash)
        )

        s = (
            select([self.squeaks, self.profiles])
            .select_from(
                self.squeaks.join(
                    ancestors,
                    ancestors.c.hash == self.squeaks.c.hash,
                ).outerjoin(
                    self.profiles,
                    self.profiles.c.address == self.squeaks.c.author_address,
                )
            )
            .order_by(
                ancestors.c.depth.desc(),
            )
        )

        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            return [self._parse_squeak_entry_with_profile(row) for row in rows]

        # sql = """
        # WITH RECURSIVE is_thread_ancestor(hash, depth) AS (
        #     VALUES(%s, 1)
        #   UNION\n
        #     SELECT squeak.hash_reply_sqk AS hash, is_thread_ancestor.depth + 1 AS depth FROM squeak, is_thread_ancestor
        #     WHERE squeak.hash=is_thread_ancestor.hash
        #   )
        #   SELECT * FROM squeak
        #   JOIN is_thread_ancestor
        #     ON squeak.hash=is_thread_ancestor.hash
        #   LEFT JOIN profile
        #     ON squeak.author_address=profile.address
        #   WHERE squeak.block_header IS NOT NULL
        #   ORDER BY is_thread_ancestor.depth DESC;
        # """
        # with self.get_cursor() as curs:
        #     curs.execute(sql, (squeak_hash_str,))
        #     rows = curs.fetchall()
        #     return [self._parse_squeak_entry_with_profile(row) for row in rows]

    def get_thread_reply_squeak_entries_with_profile(self, squeak_hash: bytes) -> List[SqueakEntryWithProfile]:
        """ Get all replies for a squeak hash. """
        s = (
            select([self.squeaks, self.profiles])
            .select_from(
                self.squeaks.outerjoin(
                    self.profiles,
                    self.profiles.c.address == self.squeaks.c.author_address,
                )
            )
            .where(self.squeaks.c.hash_reply_sqk == squeak_hash.hex())
            .order_by(
                self.squeaks.c.n_block_height.desc(),
                self.squeaks.c.n_time.desc(),
            )
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            return [self._parse_squeak_entry_with_profile(row) for row in rows]

    def lookup_squeaks(
        self,
        addresses: List[str],
        min_block: int,
        max_block: int,
        include_locked: bool = False,
    ) -> List[bytes]:
        """ Lookup squeaks. """
        if not addresses:
            return []

        s = (
            select([self.squeaks.c.hash])
            .where(self.squeaks.c.author_address.in_(addresses))
            .where(self.squeaks.c.n_block_height >= min_block)
            .where(self.squeaks.c.n_block_height <= max_block)
            .where(self.squeak_has_secret_key)
        )
        with self.get_connection() as connection:
            logger.info("Mogrify lookup_squeaks: {}.".format(
                connection.connection.cursor().mogrify(s),
            ))

            result = connection.execute(s)
            rows = result.fetchall()
            hashes = [bytes.fromhex(row["hash"]) for row in rows]
            return hashes

    def number_of_squeaks_with_address_with_block(
        self,
        address: str,
        block_height: int,
    ) -> int:
        """ Get number of squeaks with address with block height. """
        s = (
            select([
                func.count().label("num_squeaks"),
            ])
            .select_from(self.received_payments)
            .where(self.squeaks.c.author_address == address)
            .where(self.squeaks.c.n_block_height == block_height)
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            row = result.fetchone()
            num_squeaks = row["num_squeaks"]
            return num_squeaks

    def lookup_squeaks_needing_offer(
            self,
            addresses: List[str],
            min_block: int,
            max_block: int,
            peer_address: PeerAddress,
    ) -> List[bytes]:
        """ Lookup squeaks that are locked and don't have an offer. """
        if not addresses:
            return []

        s = (
            select([self.squeaks.c.hash])
            .select_from(
                self.squeaks.outerjoin(
                    self.received_offers,
                    and_(
                        self.received_offers.c.squeak_hash == self.squeaks.c.hash,
                        self.received_offers.c.peer_host == peer_address.host,
                        self.received_offers.c.peer_port == peer_address.port,
                    ),
                )
            )
            .where(self.squeaks.c.author_address.in_(addresses))
            .where(self.squeaks.c.n_block_height >= min_block)
            .where(self.squeaks.c.n_block_height <= max_block)
            .where(self.squeak_has_no_secret_key)
            .where(self.received_offer_does_not_exist)
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            hashes = [bytes.fromhex(row["hash"]) for row in rows]
            return hashes

    def get_old_squeaks_to_delete(
            self,
            interval_s: int,
    ) -> List[SqueakEntryWithProfile]:
        """ Get squeaks older than retention that meet the
        criteria for deletion.
        """
        s = (
            select([self.squeaks, self.profiles])
            .select_from(
                self.squeaks.outerjoin(
                    self.profiles,
                    self.profiles.c.address == self.squeaks.c.author_address,
                )
            )
            .where(self.squeak_is_older_than_retention(interval_s))
            .where(self.profile_has_no_private_key)
            .where(self.squeak_is_not_liked)
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            return [self._parse_squeak_entry_with_profile(row) for row in rows]

    def insert_profile(self, squeak_profile: SqueakProfile) -> int:
        """ Insert a new squeak profile. """
        ins = self.profiles.insert().values(
            profile_name=squeak_profile.profile_name,
            private_key=squeak_profile.private_key,
            address=squeak_profile.address,
            sharing=squeak_profile.sharing,
            following=squeak_profile.following,
        )
        with self.get_connection() as connection:
            res = connection.execute(ins)
            profile_id = res.inserted_primary_key[0]
            return profile_id

    def get_signing_profiles(self) -> List[SqueakProfile]:
        """ Get all signing profiles. """
        s = select([self.profiles]).where(self.profile_has_private_key)
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            profiles = [self._parse_squeak_profile(row) for row in rows]
            return profiles

    def get_contact_profiles(self) -> List[SqueakProfile]:
        """ Get all contact profiles. """
        s = select([self.profiles]).where(self.profile_has_no_private_key)
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            profiles = [self._parse_squeak_profile(row) for row in rows]
            return profiles

    def get_following_profiles(self) -> List[SqueakProfile]:
        """ Get all following profiles. """
        s = select([self.profiles]).where(self.profiles.c.following)
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            profiles = [self._parse_squeak_profile(row) for row in rows]
            return profiles

    def get_following_profiles_from_addreses(self, addresses: List[str]) -> List[SqueakProfile]:
        """ Get all following profiles. """
        s = (
            select([self.profiles])
            .where(self.profiles.c.following)
            .where(self.profiles.c.address.in_(addresses))
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            profiles = [self._parse_squeak_profile(row) for row in rows]
            return profiles

    def get_sharing_profiles(self) -> List[SqueakProfile]:
        """ Get all sharing profiles. """
        s = select([self.profiles]).where(self.profiles.c.sharing)
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            profiles = [self._parse_squeak_profile(row) for row in rows]
            return profiles

    def get_profile(self, profile_id: int) -> Optional[SqueakProfile]:
        """ Get a profile. """
        s = select([self.profiles]).where(
            self.profiles.c.profile_id == profile_id)
        with self.get_connection() as connection:
            result = connection.execute(s)
            row = result.fetchone()
            if row is None:
                return None
            return self._parse_squeak_profile(row)

    def get_profile_by_address(self, address: str) -> Optional[SqueakProfile]:
        """ Get a profile by address. """
        s = select([self.profiles]).where(self.profiles.c.address == address)
        with self.get_connection() as connection:
            result = connection.execute(s)
            row = result.fetchone()
            if row is None:
                return None
            return self._parse_squeak_profile(row)

    def get_profile_by_name(self, name: str) -> Optional[SqueakProfile]:
        """ Get a profile by name. """
        s = select([self.profiles]).where(self.profiles.c.profile_name == name)
        with self.get_connection() as connection:
            result = connection.execute(s)
            row = result.fetchone()
            if row is None:
                return None
            return self._parse_squeak_profile(row)

    def set_profile_following(self, profile_id: int, following: bool) -> None:
        """ Set a profile is following. """
        stmt = (
            self.profiles.update()
            .where(self.profiles.c.profile_id == profile_id)
            .values(following=following)
        )
        with self.get_connection() as connection:
            connection.execute(stmt)

    def set_profile_sharing(self, profile_id: int, sharing: bool) -> None:
        """ Set a profile is sharing. """
        stmt = (
            self.profiles.update()
            .where(self.profiles.c.profile_id == profile_id)
            .values(sharing=sharing)
        )
        with self.get_connection() as connection:
            connection.execute(stmt)

    def set_profile_name(self, profile_id: int, profile_name: str) -> None:
        """ Set a profile name. """
        stmt = (
            self.profiles.update()
            .where(self.profiles.c.profile_id == profile_id)
            .values(profile_name=profile_name)
        )
        with self.get_connection() as connection:
            connection.execute(stmt)

    def delete_profile(self, profile_id: int) -> None:
        """ Delete a profile. """
        delete_profile_stmt = self.profiles.delete().where(
            self.profiles.c.profile_id == profile_id
        )
        with self.get_connection() as connection:
            connection.execute(delete_profile_stmt)

    def set_profile_image(self, profile_id: int, profile_image: bytes) -> None:
        """ Set a profile image. """
        stmt = (
            self.profiles.update()
            .where(self.profiles.c.profile_id == profile_id)
            .values(profile_image=profile_image)
        )
        with self.get_connection() as connection:
            connection.execute(stmt)

    def set_squeak_decryption_key(self, squeak_hash: bytes, secret_key: bytes) -> None:
        """ Set the decryption key of a squeak. """
        stmt = (
            self.squeaks.update()
            .where(self.squeaks.c.hash == squeak_hash.hex())
            .values(secret_key=secret_key.hex())
        )
        with self.get_connection() as connection:
            connection.execute(stmt)

    def set_squeak_liked(self, squeak_hash: bytes, liked: bool) -> None:
        """ Set the liked value of a squeak. """
        stmt = (
            self.squeaks.update()
            .where(self.squeaks.c.hash == squeak_hash.hex())
            .values(liked=liked)
        )
        with self.get_connection() as connection:
            connection.execute(stmt)

    def delete_squeak(self, squeak_hash: bytes) -> None:
        """ Delete a squeak. """
        delete_squeak_stmt = self.squeaks.delete().where(
            self.squeaks.c.hash == squeak_hash.hex()
        )
        with self.get_connection() as connection:
            connection.execute(delete_squeak_stmt)

    def insert_peer(self, squeak_peer: SqueakPeer) -> int:
        """ Insert a new squeak peer. """
        ins = self.peers.insert().values(
            peer_name=squeak_peer.peer_name,
            host=squeak_peer.address.host,
            port=squeak_peer.address.port,
            uploading=squeak_peer.uploading,
            downloading=squeak_peer.downloading,
        )
        with self.get_connection() as connection:
            res = connection.execute(ins)
            id = res.inserted_primary_key[0]
            return id

    def get_peer(self, peer_id: int) -> Optional[SqueakPeer]:
        """ Get a peer. """
        s = select([self.peers]).where(self.peers.c.peer_id == peer_id)
        with self.get_connection() as connection:
            result = connection.execute(s)
            row = result.fetchone()
            if row is None:
                return None
            return self._parse_squeak_peer(row)

    def get_peers(self) -> List[SqueakPeer]:
        """ Get all peers. """
        s = select([self.peers])
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            peers = [self._parse_squeak_peer(row) for row in rows]
            return peers

    def get_downloading_peers(self) -> List[SqueakPeer]:
        """ Get peers that are set to be downloading. """
        s = select([self.peers]).where(self.peers.c.downloading)
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            peers = [self._parse_squeak_peer(row) for row in rows]
            return peers

    def get_uploading_peers(self) -> List[SqueakPeer]:
        """ Get peers that are set to be uploading. """
        s = select([self.peers]).where(self.peers.c.uploading)
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            peers = [self._parse_squeak_peer(row) for row in rows]
            return peers

    def set_peer_downloading(self, peer_id: int, downloading: bool):
        """ Set a peer is downloading. """
        stmt = (
            self.peers.update()
            .where(self.peers.c.peer_id == peer_id)
            .values(downloading=downloading)
        )
        with self.get_connection() as connection:
            connection.execute(stmt)

    def set_peer_uploading(self, peer_id: int, uploading: bool):
        """ Set a peer is uploading. """
        stmt = (
            self.peers.update()
            .where(self.peers.c.peer_id == peer_id)
            .values(uploading=uploading)
        )
        with self.get_connection() as connection:
            connection.execute(stmt)

    def set_peer_name(self, peer_id: int, peer_name: str):
        """ Set a peer name. """
        stmt = (
            self.peers.update()
            .where(self.peers.c.peer_id == peer_id)
            .values(peer_name=peer_name)
        )
        with self.get_connection() as connection:
            connection.execute(stmt)

    def delete_peer(self, peer_id: int):
        """ Delete a peer. """
        delete_peer_stmt = self.peers.delete().where(self.peers.c.peer_id == peer_id)
        with self.get_connection() as connection:
            connection.execute(delete_peer_stmt)

    def insert_received_offer(self, received_offer: ReceivedOffer):
        """ Insert a new received offer. """
        ins = self.received_offers.insert().values(
            squeak_hash=received_offer.squeak_hash.hex(),
            payment_hash=received_offer.payment_hash.hex(),
            nonce=received_offer.nonce.hex(),
            payment_point=received_offer.payment_point.hex(),
            invoice_timestamp=received_offer.invoice_timestamp,
            invoice_expiry=received_offer.invoice_expiry,
            price_msat=received_offer.price_msat,
            payment_request=received_offer.payment_request,
            destination=received_offer.destination,
            lightning_host=received_offer.lightning_address.host,
            lightning_port=received_offer.lightning_address.port,
            peer_host=received_offer.peer_address.host,
            peer_port=received_offer.peer_address.port,
        )
        with self.get_connection() as connection:
            res = connection.execute(ins)
            received_offer_id = res.inserted_primary_key[0]
            return received_offer_id

    def get_received_offers_with_peer(self, squeak_hash: bytes) -> List[ReceivedOfferWithPeer]:
        """ Get offers with peer for a squeak hash. """
        s = (
            select([self.received_offers, self.peers])
            .select_from(
                self.received_offers.outerjoin(
                    self.peers,
                    self.peers.c.host == self.received_offers.c.peer_host,
                    self.peers.c.port == self.received_offers.c.peer_port,
                )
            )
            .where(self.received_offers.c.squeak_hash == squeak_hash.hex())
            .where(self.received_offer_is_not_paid)
            .where(self.received_offer_is_not_expired)
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            offers_with_peer = [
                self._parse_received_offer_with_peer(row) for row in rows]
            return offers_with_peer

    def get_offer_with_peer(self, received_offer_id: int) -> Optional[ReceivedOfferWithPeer]:
        """ Get offer with peer for an offer id. """
        s = (
            select([self.received_offers, self.peers])
            .select_from(
                self.received_offers.outerjoin(
                    self.peers,
                    self.peers.c.host == self.received_offers.c.peer_host,
                    self.peers.c.port == self.received_offers.c.peer_port,
                )
            )
            .where(self.received_offers.c.received_offer_id == received_offer_id)
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            row = result.fetchone()
            if row is None:
                return None
            offer_with_peer = self._parse_received_offer_with_peer(row)
            return offer_with_peer

    def get_received_offer_for_squeak_and_peer(
            self,
            squeak_hash: bytes,
            peer_address: PeerAddress,
    ) -> Optional[ReceivedOfferWithPeer]:
        """ Get offer with peer for a given peer address and squeak hash . """
        s = (
            select([self.received_offers, self.peers])
            .select_from(
                self.received_offers.outerjoin(
                    self.peers,
                    self.peers.c.host == self.received_offers.c.peer_host,
                    self.peers.c.port == self.received_offers.c.peer_port,
                )
            )
            .where(self.received_offers.c.squeak_hash == squeak_hash.hex())
            .where(self.received_offers.c.peer_host == peer_address.host)
            .where(self.received_offers.c.peer_port == peer_address.port)
            .where(self.received_offer_is_not_paid)
            .where(self.received_offer_is_not_expired)
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            row = result.fetchone()
            if row is None:
                return None
            offer_with_peer = self._parse_received_offer_with_peer(row)
            return offer_with_peer

    def delete_expired_received_offers(self):
        """ Delete all expired offers. """
        s = self.received_offers.delete().where(
            self.received_offer_should_be_deleted()
        )
        with self.get_connection() as connection:
            res = connection.execute(s)
            deleted_offers = res.rowcount
            return deleted_offers

    def delete_offers_for_squeak(self, squeak_hash: bytes):
        """ Delete all offers for a squeak hash. """
        s = self.received_offers.delete().where(
            self.received_offers.c.squeak_hash == squeak_hash.hex())
        with self.get_connection() as connection:
            res = connection.execute(s)
            deleted_offers = res.rowcount
            return deleted_offers

    def delete_offer(self, payment_hash: bytes):
        """ Delete a received offer by payment hash. """
        s = self.received_offers.delete().where(
            self.received_offers.c.payment_hash == payment_hash.hex()
        )
        with self.get_connection() as connection:
            connection.execute(s)

    def set_received_offer_paid(self, payment_hash: bytes, paid: bool) -> None:
        """ Set a received offer is paid. """
        stmt = (
            self.received_offers.update()
            .where(self.received_offers.c.payment_hash == payment_hash.hex())
            .values(paid=paid)
        )
        with self.get_connection() as connection:
            connection.execute(stmt)

    def insert_sent_payment(self, sent_payment: SentPayment):
        """ Insert a new sent payment. """
        ins = self.sent_payments.insert().values(
            peer_host=sent_payment.peer_address.host,
            peer_port=sent_payment.peer_address.port,
            squeak_hash=sent_payment.squeak_hash.hex(),
            payment_hash=sent_payment.payment_hash.hex(),
            secret_key=sent_payment.secret_key.hex(),
            price_msat=sent_payment.price_msat,
            node_pubkey=sent_payment.node_pubkey,
            valid=sent_payment.valid,
        )
        with self.get_connection() as connection:
            res = connection.execute(ins)
            sent_payment_id = res.inserted_primary_key[0]
            return sent_payment_id

    def get_sent_payments(self) -> List[SentPaymentWithPeer]:
        """ Get all sent payments. """
        s = (
            select([self.sent_payments, self.peers])
            .select_from(
                self.sent_payments.outerjoin(
                    self.peers,
                    self.peers.c.host == self.sent_payments.c.peer_host,
                    self.peers.c.port == self.sent_payments.c.peer_port,
                )
            )
            .order_by(
                self.sent_payments.c.created.desc(),
            )
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            sent_payments = [
                self._parse_sent_payment_with_peer(row) for row in rows]
            return sent_payments

    def get_sent_payment(self, sent_payment_id: int) -> Optional[SentPaymentWithPeer]:
        """ Get sent payment by id. """
        s = (
            select([self.sent_payments, self.peers])
            .select_from(
                self.sent_payments.outerjoin(
                    self.peers,
                    self.peers.c.host == self.sent_payments.c.peer_host,
                    self.peers.c.port == self.sent_payments.c.peer_port,
                )
            )
            .where(self.sent_payments.c.sent_payment_id == sent_payment_id)
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            row = result.fetchone()
            if row is None:
                return None
            return self._parse_sent_payment_with_peer(row)

    def insert_sent_offer(self, sent_offer: SentOffer):
        """ Insert a new sent offer. """
        ins = self.sent_offers.insert().values(
            squeak_hash=sent_offer.squeak_hash.hex(),
            payment_hash=sent_offer.payment_hash.hex(),
            secret_key=sent_offer.secret_key.hex(),
            nonce=sent_offer.nonce.hex(),
            price_msat=sent_offer.price_msat,
            payment_request=sent_offer.payment_request,
            invoice_timestamp=sent_offer.invoice_time,
            invoice_expiry=sent_offer.invoice_expiry,
            client_host=sent_offer.client_addr.host,
            client_port=sent_offer.client_addr.port,
        )
        with self.get_connection() as connection:
            res = connection.execute(ins)
            sent_offer_id = res.inserted_primary_key[0]
            return sent_offer_id

    def get_sent_offers(self) -> List[SentOffer]:
        """ Get all received payments. """
        s = select([self.sent_offers]).order_by(
            self.sent_offers.c.created.desc(),
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            sent_offers = [self._parse_sent_offer(row) for row in rows]
            return sent_offers

    def get_sent_offer_by_payment_hash(self, payment_hash: bytes) -> Optional[SentOffer]:
        """ Get a sent offer by preimage hash. """
        s = select([self.sent_offers]).where(
            self.sent_offers.c.payment_hash == payment_hash.hex()
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            row = result.fetchone()
            if row is None:
                return None
            sent_offer = self._parse_sent_offer(row)
            return sent_offer

    def get_sent_offer_by_squeak_hash_and_client(self, squeak_hash: bytes, client_address: PeerAddress) -> Optional[SentOffer]:
        """
        Get a sent offer by squeak hash and client address host. Only
        return sent offer if it's not expired and not paid.
        """
        s = (
            select([self.sent_offers])
            .where(self.sent_offers.c.squeak_hash == squeak_hash.hex())
            .where(self.sent_offers.c.client_host == client_address.host)
            .where(self.sent_offer_is_not_paid)
            .where(self.sent_offer_is_not_expired)
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            row = result.fetchone()
            if row is None:
                return None
            sent_offer = self._parse_sent_offer(row)
            return sent_offer

    def delete_sent_offer(self, payment_hash: bytes):
        """ Delete a sent offer by payment hash. """
        s = self.sent_offers.delete().where(
            self.sent_offers.c.payment_hash == payment_hash.hex()
        )
        with self.get_connection() as connection:
            connection.execute(s)

    def delete_expired_sent_offers(self, interval_s):
        """
        Delete all expired sent offers. Only delete sent
        offers that have been expired for more than interval_s seconds.
        """
        s = self.sent_offers.delete().where(
            self.sent_offer_should_be_deleted(interval_s)
        )
        with self.get_connection() as connection:
            res = connection.execute(s)
            deleted_sent_offers = res.rowcount
            return deleted_sent_offers

    def set_sent_offer_paid(self, payment_hash: bytes, paid: bool) -> None:
        """ Set a sent offer is paid. """
        stmt = (
            self.sent_offers.update()
            .where(self.sent_offers.c.payment_hash == payment_hash.hex())
            .values(paid=paid)
        )
        with self.get_connection() as connection:
            connection.execute(stmt)

    def get_latest_settle_index(self):
        """ Get the lnd settled index of the most recent received payment. """
        s = select(
            [func.max(self.received_payments.c.settle_index)],
        ).select_from(self.received_payments)
        with self.get_connection() as connection:
            result = connection.execute(s)
            row = result.fetchone()
            latest_index = row[0]
            return latest_index

    def insert_received_payment(self, received_payment: ReceivedPayment):
        """ Insert a new received payment. """
        ins = self.received_payments.insert().values(
            squeak_hash=received_payment.squeak_hash.hex(),
            payment_hash=received_payment.payment_hash.hex(),
            price_msat=received_payment.price_msat,
            settle_index=received_payment.settle_index,
            client_host=received_payment.client_addr.host,
            client_port=received_payment.client_addr.port,
        )
        with self.get_connection() as connection:
            try:
                res = connection.execute(ins)
                received_payment_id = res.inserted_primary_key[0]
                return received_payment_id
            except sqlalchemy.exc.IntegrityError:
                raise DuplicateReceivedPaymentError()

    def get_received_payments(self) -> List[ReceivedPayment]:
        """ Get all received payments. """
        s = select([self.received_payments]).order_by(
            self.received_payments.c.created.desc(),
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            rows = result.fetchall()
            received_payments = [
                self._parse_received_payment(row) for row in rows]
            return received_payments

    def clear_received_payment_settle_indices(self) -> None:
        """ Set settle_index to zero for all received payments. """
        stmt = (
            self.received_payments.update()
            .values(settle_index=0)
        )
        with self.get_connection() as connection:
            connection.execute(stmt)

    def yield_received_payments_from_index(self, start_index: int = 0) -> Iterator[ReceivedPayment]:
        """ Get all received payments. """
        s = (
            select([self.received_payments])
            .order_by(
                self.received_payments.c.received_payment_id.asc(),
            )
            .where(self.received_payments.c.received_payment_id > start_index)
        )
        with self.get_connection() as connection:
            result = connection.execute(s)
            for row in result:
                received_payment = self._parse_received_payment(row)
                yield received_payment

    def get_received_payment_summary(self) -> ReceivedPaymentSummary:
        """ Get received payment summary. """
        s = select([
            func.count().label("num_payments_received"),
            func.sum(self.received_payments.c.price_msat).label(
                "total_amount_received_msat"),
        ]).select_from(self.received_payments)
        with self.get_connection() as connection:
            result = connection.execute(s)
            row = result.fetchone()
            received_payment_summary = self._parse_received_payment_summary(
                row)
            return received_payment_summary

    def get_sent_payment_summary(self) -> SentPaymentSummary:
        """ Get sent payment summary. """
        s = select([
            func.count().label("num_payments_sent"),
            func.sum(self.sent_payments.c.price_msat).label(
                "total_amount_sent_msat"),
        ]).select_from(self.sent_payments)
        with self.get_connection() as connection:
            result = connection.execute(s)
            row = result.fetchone()
            sent_payment_summary = self._parse_sent_payment_summary(row)
            return sent_payment_summary

    def _parse_squeak_entry(self, row) -> SqueakEntry:
        secret_key_column = row["secret_key"]
        secret_key = (
            bytes.fromhex(secret_key_column) if
            secret_key_column else b""
        )
        squeak = CSqueak.deserialize(row["squeak"])
        if secret_key:
            squeak.SetDecryptionKey(secret_key)
        block_header_column = row["block_header"]
        block_header_bytes = (
            bytes(block_header_column) if
            block_header_column else None
        )
        block_header = (
            parse_block_header(block_header_bytes) if
            block_header_bytes else None
        )
        liked = row["liked"]
        return SqueakEntry(
            squeak=squeak,
            block_header=block_header,
            liked=liked,
        )

    def _parse_squeak_profile(self, row) -> SqueakProfile:
        private_key_column = row["private_key"]
        private_key = bytes(private_key_column) if private_key_column else None
        return SqueakProfile(
            profile_id=row["profile_id"],
            profile_name=row["profile_name"],
            private_key=private_key,
            address=row["address"],
            sharing=row["sharing"],
            following=row["following"],
            profile_image=row["profile_image"],
        )

    def _parse_squeak_entry_with_profile(self, row) -> SqueakEntryWithProfile:
        squeak_entry = self._parse_squeak_entry(row)
        if row["profile_id"] is None:
            squeak_profile = None
        else:
            squeak_profile = self._parse_squeak_profile(row)
        return SqueakEntryWithProfile(
            squeak_entry=squeak_entry,
            squeak_profile=squeak_profile,
        )

    def _parse_squeak_peer(self, row) -> SqueakPeer:
        return SqueakPeer(
            peer_id=row[self.peers.c.peer_id],
            peer_name=row["peer_name"],
            address=PeerAddress(
                host=row["host"],
                port=row["port"],
            ),
            uploading=row["uploading"],
            downloading=row["downloading"],
        )

    def _parse_received_offer(self, row) -> ReceivedOffer:
        return ReceivedOffer(
            received_offer_id=row["received_offer_id"],
            squeak_hash=bytes.fromhex(row["squeak_hash"]),
            payment_hash=bytes.fromhex(row["payment_hash"]),
            nonce=bytes.fromhex(row["nonce"]),
            payment_point=bytes.fromhex(row["payment_point"]),
            invoice_timestamp=row["invoice_timestamp"],
            invoice_expiry=row["invoice_expiry"],
            price_msat=row["price_msat"],
            payment_request=row["payment_request"],
            destination=row["destination"],
            lightning_address=LightningAddressHostPort(
                host=row["lightning_host"],
                port=row["lightning_port"],
            ),
            peer_address=PeerAddress(
                host=row["peer_host"],
                port=row["peer_port"],
            ),
        )

    def _parse_received_offer_with_peer(self, row) -> ReceivedOfferWithPeer:
        offer = self._parse_received_offer(row)
        if row[self.peers.c.peer_id] is None:
            peer = None
        else:
            peer = self._parse_squeak_peer(row)
        return ReceivedOfferWithPeer(
            received_offer=offer,
            peer=peer,
        )

    def _parse_sent_payment(self, row) -> SentPayment:
        return SentPayment(
            sent_payment_id=row["sent_payment_id"],
            created=row[self.sent_payments.c.created],
            peer_address=PeerAddress(
                host=row["peer_host"],
                port=row["peer_port"],
            ),
            squeak_hash=bytes.fromhex(row["squeak_hash"]),
            payment_hash=bytes.fromhex(row["payment_hash"]),
            secret_key=bytes.fromhex(row["secret_key"]),
            price_msat=row["price_msat"],
            node_pubkey=row["node_pubkey"],
            valid=row["valid"],
        )

    def _parse_sent_payment_with_peer(self, row) -> SentPaymentWithPeer:
        sent_payment = self._parse_sent_payment(row)
        if row[self.peers.c.peer_id] is None:
            peer = None
        else:
            peer = self._parse_squeak_peer(row)
        return SentPaymentWithPeer(
            sent_payment=sent_payment,
            peer=peer,
        )

    def _parse_sent_offer(self, row) -> SentOffer:
        return SentOffer(
            sent_offer_id=row["sent_offer_id"],
            squeak_hash=bytes.fromhex(row["squeak_hash"]),
            payment_hash=bytes.fromhex(row["payment_hash"]),
            secret_key=bytes.fromhex(row["secret_key"]),
            nonce=bytes.fromhex(row["nonce"]),
            price_msat=row["price_msat"],
            payment_request=row["payment_request"],
            invoice_time=row["invoice_timestamp"],
            invoice_expiry=row["invoice_expiry"],
            client_addr=PeerAddress(
                host=row["client_host"],
                port=row["client_port"],
            ),
        )

    def _parse_received_payment(self, row) -> ReceivedPayment:
        return ReceivedPayment(
            received_payment_id=row["received_payment_id"],
            created=row["created"],
            squeak_hash=bytes.fromhex(row["squeak_hash"]),
            payment_hash=bytes.fromhex(row["payment_hash"]),
            price_msat=row["price_msat"],
            settle_index=row["settle_index"],
            client_addr=PeerAddress(
                host=row["client_host"],
                port=row["client_port"],
            ),
        )

    def _parse_received_payment_summary(self, row) -> ReceivedPaymentSummary:
        return ReceivedPaymentSummary(
            num_received_payments=row["num_payments_received"],
            total_amount_received_msat=row["total_amount_received_msat"],
        )

    def _parse_sent_payment_summary(self, row) -> SentPaymentSummary:
        return SentPaymentSummary(
            num_sent_payments=row["num_payments_sent"],
            total_amount_sent_msat=row["total_amount_sent_msat"],
        )
