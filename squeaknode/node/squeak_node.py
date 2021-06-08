import logging
import threading
from pathlib import Path

from squeak.params import SelectParams

from squeaknode.admin.squeak_admin_server_handler import SqueakAdminServerHandler
from squeaknode.admin.squeak_admin_server_servicer import SqueakAdminServerServicer
from squeaknode.admin.webapp.app import SqueakAdminWebServer
from squeaknode.bitcoin.bitcoin_block_subscription_client import BitcoinBlockSubscriptionClient
from squeaknode.bitcoin.bitcoin_core_bitcoin_client import BitcoinCoreBitcoinClient
from squeaknode.config.config import SqueaknodeConfig
from squeaknode.core.squeak_core import SqueakCore
from squeaknode.db.db_engine import get_engine
from squeaknode.db.db_engine import get_sqlite_connection_string
from squeaknode.db.squeak_db import SqueakDb
from squeaknode.lightning.lnd_lightning_client import LNDLightningClient
from squeaknode.node.payment_processor import PaymentProcessor
from squeaknode.node.process_received_payments_worker import ProcessReceivedPaymentsWorker
from squeaknode.node.squeak_controller import SqueakController
from squeaknode.node.squeak_deletion_worker import SqueakDeletionWorker
from squeaknode.node.squeak_offer_expiry_worker import SqueakOfferExpiryWorker
from squeaknode.node.squeak_peer_sync_worker import SqueakPeerSyncWorker
from squeaknode.node.squeak_rate_limiter import SqueakRateLimiter
from squeaknode.node.subscribe_blocks_worker import SubscribeBlocksWorker
from squeaknode.server.squeak_server_handler import SqueakServerHandler
from squeaknode.server.squeak_server_servicer import SqueakServerServicer
from squeaknode.sync.squeak_sync_controller import SqueakSyncController

logger = logging.getLogger(__name__)


class SqueakNode:

    def __init__(self, config: SqueaknodeConfig):
        self.config = config
        self.stopped = threading.Event()
        self._initialize()

    def _initialize(self):
        # load the network
        network = self.config.core.network
        SelectParams(network)

        # load the db
        squeak_db = load_db(self.config, network)
        squeak_db.init()

        # load the lightning client
        lightning_client = load_lightning_client(self.config)

        # load the bitcoin client
        bitcoin_client = load_bitcoin_client(self.config)

        squeak_core = SqueakCore(
            bitcoin_client,
            lightning_client,
        )
        squeak_rate_limiter = SqueakRateLimiter(
            squeak_db,
            self.config.core.max_squeaks_per_address_per_block,
        )
        payment_processor = PaymentProcessor(
            squeak_db,
            squeak_core,
            self.config.core.subscribe_invoices_retry_s,
        )

        block_subscription_client = BitcoinBlockSubscriptionClient(
            self.config.bitcoin.rpc_host,
            self.config.bitcoin.zeromq_port,
        )

        squeak_controller = SqueakController(
            squeak_db,
            squeak_core,
            squeak_rate_limiter,
            payment_processor,
            self.config,
        )

        sync_controller = SqueakSyncController(
            squeak_controller,
            self.config.sync.block_interval,
            self.config.sync.timeout_s,
        )

        admin_handler = load_admin_handler(
            lightning_client,
            squeak_controller,
            sync_controller,
        )

        self.admin_rpc_server = load_admin_rpc_server(
            self.config,
            admin_handler,
            self.stopped,
        )

        self.admin_web_server = load_admin_web_server(
            self.config,
            admin_handler,
            self.stopped,
        )

        self.sync_worker = load_sync_worker(
            self.config,
            sync_controller,
        )

        self.squeak_offer_expiry_worker = SqueakOfferExpiryWorker(
            squeak_controller,
            self.config.core.offer_deletion_interval_s,
        )
        self.sent_offers_worker = ProcessReceivedPaymentsWorker(
            payment_processor,
            self.stopped,
        )
        self.squeak_deletion_worker = SqueakDeletionWorker(
            squeak_controller,
            self.config.core.squeak_deletion_interval_s,
        )
        self.subscribe_blocks_worker = SubscribeBlocksWorker(
            block_subscription_client,
            self.stopped,
        )

        handler = load_handler(squeak_controller)
        self.server = load_rpc_server(
            self.config,
            handler,
            self.stopped,
        )

    def start_running(self):
        # start admin rpc server
        if self.config.admin.rpc_enabled:
            start_admin_rpc_server(self.admin_rpc_server)

        # start admin web server
        if self.config.webadmin.enabled:
            start_admin_web_server(self.admin_web_server)

        # start sync worker
        if self.config.sync.enabled:
            start_sync_worker(self.sync_worker)

        self.squeak_offer_expiry_worker.start_running()
        self.sent_offers_worker.start_running()
        self.squeak_deletion_worker.start_running()
        self.subscribe_blocks_worker.start_running()

        # start peer rpc server
        if self.config.server.rpc_enabled:
            start_peer_web_server(self.server)

    def stop_running(self):
        self.stopped.set()


def load_lightning_client(config) -> LNDLightningClient:
    return LNDLightningClient(
        config.lnd.host,
        config.lnd.rpc_port,
        config.lnd.tls_cert_path,
        config.lnd.macaroon_path,
    )


def load_rpc_server(config, handler, stopped_event) -> SqueakServerServicer:
    return SqueakServerServicer(
        config.server.rpc_host,
        config.server.rpc_port,
        handler,
        stopped_event,
    )


def load_admin_rpc_server(config, handler, stopped_event) -> SqueakAdminServerServicer:
    return SqueakAdminServerServicer(
        config.admin.rpc_host,
        config.admin.rpc_port,
        handler,
        stopped_event,
    )


def load_admin_web_server(config, handler, stopped_event) -> SqueakAdminWebServer:
    return SqueakAdminWebServer(
        config.webadmin.host,
        config.webadmin.port,
        config.webadmin.username,
        config.webadmin.password,
        config.webadmin.use_ssl,
        config.webadmin.login_disabled,
        config.webadmin.allow_cors,
        handler,
        stopped_event,
    )


def load_sync_worker(config, sync_controller) -> SqueakPeerSyncWorker:
    return SqueakPeerSyncWorker(
        sync_controller,
        config.sync.interval_s,
    )


def load_handler(squeak_controller):
    return SqueakServerHandler(squeak_controller)


def load_admin_handler(lightning_client, squeak_controller, sync_controller):
    return SqueakAdminServerHandler(
        lightning_client,
        squeak_controller,
        sync_controller,
    )


def load_sqk_dir_path(config):
    sqk_dir = config.core.sqk_dir_path
    return Path(sqk_dir)


def load_db(config, network):
    connection_string = config.db.connection_string
    logger.info("connection string: {}".format(connection_string))
    logger.info("connection string type: {}".format(type(connection_string)))
    if not connection_string:
        sqk_dir = load_sqk_dir_path(config)
        logger.info(
            "Getting connection string from sqk dir: {}".format(sqk_dir))
        connection_string = get_sqlite_connection_string(sqk_dir, network)
    logger.info("Getting engine from connection string: {}".format(
        connection_string))
    engine = get_engine(connection_string)
    return SqueakDb(engine)


def load_bitcoin_client(config):
    return BitcoinCoreBitcoinClient(
        config.bitcoin.rpc_host,
        config.bitcoin.rpc_port,
        config.bitcoin.rpc_user,
        config.bitcoin.rpc_pass,
        config.bitcoin.rpc_use_ssl,
        config.bitcoin.rpc_ssl_cert,
    )


def start_admin_rpc_server(rpc_server):
    logger.info("Starting admin RPC server...")
    thread = threading.Thread(
        target=rpc_server.serve,
        args=(),
    )
    thread.start()


def load_admin_web_server_enabled(config):
    return config.webadmin.enabled


def start_admin_web_server(admin_web_server):
    logger.info("Starting admin web server...")
    thread = threading.Thread(
        target=admin_web_server.serve,
        args=(),
    )
    thread.start()


def start_peer_web_server(peer_web_server):
    logger.info("Starting peer web server...")
    thread = threading.Thread(
        target=peer_web_server.serve,
        args=(),
    )
    thread.start()


def start_sync_worker(sync_worker):
    logger.info("Starting sync worker...")
    thread = threading.Thread(
        target=sync_worker.start_running,
        args=(),
    )
    thread.start()
