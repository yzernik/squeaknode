import datetime
import logging

from sqlalchemy import BigInteger
from sqlalchemy import Binary
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import func
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import TypeDecorator


logger = logging.getLogger(__name__)


class TZDateTime(TypeDecorator):
    impl = DateTime

    def process_bind_param(self, value, dialect):
        if value is not None:
            if not value.tzinfo:
                raise TypeError("tzinfo is required")
            value = value.astimezone(datetime.timezone.utc).replace(
                tzinfo=None
            )
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value


class SLBigInteger(BigInteger):
    pass


@compiles(SLBigInteger, 'sqlite')
def bi_c_sqlite(element, compiler, **kw):
    return "INTEGER"


@compiles(SLBigInteger)
def bi_c(element, compiler, **kw):
    return compiler.visit_BIGINT(element, **kw)


class Models:
    def __init__(self, schema=None):
        self.schema = schema
        self.metadata = MetaData(schema=schema)

        self.squeaks = Table(
            "squeak",
            self.metadata,
            Column("hash", String(64), primary_key=True),
            Column("created", TZDateTime,
                   server_default=func.now(), nullable=False),
            Column("squeak", Binary, nullable=False),
            Column("hash_reply_sqk", String(64), nullable=False),
            Column("hash_block", String(64), nullable=False),
            Column("n_block_height", Integer, nullable=False),
            Column("n_time", Integer, nullable=False),
            Column("author_address", String(35), index=True, nullable=False),
            Column("secret_key", String(64), nullable=True),
            Column("block_header", Binary, nullable=False),
            Column("liked_time", TZDateTime,
                   default=None, nullable=True),
        )

        self.profiles = Table(
            "profile",
            self.metadata,
            Column("profile_id", Integer, primary_key=True),
            Column("created", TZDateTime,
                   server_default=func.now(), nullable=False),
            Column("profile_name", String, unique=True, nullable=False),
            Column("private_key", Binary, nullable=True),
            Column("address", String(35), unique=True, nullable=False),
            Column("sharing", Boolean, nullable=False),
            Column("following", Boolean, nullable=False),
            Column("profile_image", Binary, nullable=True),
            sqlite_autoincrement=True,
        )

        self.peers = Table(
            "peer",
            self.metadata,
            Column("peer_id", Integer, primary_key=True),
            Column("created", TZDateTime,
                   server_default=func.now(), nullable=False),
            Column("peer_name", String, nullable=False),
            Column("host", String, nullable=False),
            Column("port", Integer, nullable=False),
            Column("uploading", Boolean, nullable=False),
            Column("downloading", Boolean, nullable=False),
            UniqueConstraint('host', 'port',
                             name='uq_peer_host_port'),
            sqlite_autoincrement=True,
        )

        self.received_offers = Table(
            "received_offer",
            self.metadata,
            Column("received_offer_id", SLBigInteger, primary_key=True),
            Column("created", TZDateTime,
                   server_default=func.now(), nullable=False),
            Column("squeak_hash", String(64), nullable=False),
            Column("payment_hash", String(64), unique=True, nullable=False),
            Column("nonce", String(64), nullable=False),
            Column("payment_point", String(66), nullable=False),
            Column("invoice_timestamp", Integer, nullable=False),
            Column("invoice_expiry", Integer, nullable=False),
            Column("price_msat", Integer, nullable=False),
            Column("payment_request", String, nullable=False),
            Column("destination", String(66), nullable=False),
            Column("lightning_host", String, nullable=False),
            Column("lightning_port", Integer, nullable=False),
            Column("peer_host", String, nullable=False),
            Column("peer_port", Integer, nullable=False),
            Column("paid", Boolean, nullable=False, default=False),
            sqlite_autoincrement=True,
        )

        self.sent_payments = Table(
            "sent_payment",
            self.metadata,
            Column("sent_payment_id", SLBigInteger, primary_key=True),
            Column("created", TZDateTime,
                   server_default=func.now(), nullable=False),
            Column("peer_host", String, nullable=False),
            Column("peer_port", Integer, nullable=False),
            Column("squeak_hash", String(64), nullable=False),
            Column("payment_hash", String(64), unique=True, nullable=False),
            Column("secret_key", String(64), nullable=False),
            Column("price_msat", Integer, nullable=False, default=0),
            Column("node_pubkey", String(66), nullable=False),
            Column("valid", Boolean, nullable=False),
            sqlite_autoincrement=True,
        )

        self.sent_offers = Table(
            "sent_offer",
            self.metadata,
            Column("sent_offer_id", SLBigInteger, primary_key=True),
            Column("created", TZDateTime,
                   server_default=func.now(), nullable=False),
            Column("squeak_hash", String(64), nullable=False),
            Column("payment_hash", String(64), unique=True, nullable=False),
            Column("secret_key", String(64), nullable=False),
            Column("nonce", String(64), nullable=False),
            Column("price_msat", Integer, nullable=False, default=0),
            Column("payment_request", String, nullable=False),
            Column("invoice_timestamp", Integer, nullable=False),
            Column("invoice_expiry", Integer, nullable=False),
            Column("client_host", String, nullable=False),
            Column("client_port", Integer, nullable=False),
            Column("paid", Boolean, nullable=False, default=False),
            sqlite_autoincrement=True,
        )

        self.received_payments = Table(
            "received_payment",
            self.metadata,
            Column("received_payment_id", SLBigInteger, primary_key=True),
            Column("created", TZDateTime,
                   server_default=func.now(), nullable=False),
            Column("squeak_hash", String(64), nullable=False),
            Column("payment_hash", String(64), unique=True, nullable=False),
            Column("price_msat", Integer, nullable=False),
            Column("settle_index", SLBigInteger, nullable=False),
            Column("client_host", String, nullable=False),
            Column("client_port", Integer, nullable=False),
            sqlite_autoincrement=True,
        )
