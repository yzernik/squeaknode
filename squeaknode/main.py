import argparse
import logging
import sys
import threading
from pathlib import Path

from squeak.params import SelectParams

from squeaknode.admin.squeak_admin_server_handler import SqueakAdminServerHandler
from squeaknode.admin.squeak_admin_server_servicer import SqueakAdminServerServicer
from squeaknode.admin.webapp.app import SqueakAdminWebServer
from squeaknode.bitcoin.bitcoin_blockchain_client import BitcoinBlockchainClient
from squeaknode.config.config import SqueaknodeConfig
from squeaknode.core.squeak_controller import SqueakController
from squeaknode.core.squeak_core import SqueakCore
from squeaknode.db.db_engine import get_engine
from squeaknode.db.db_engine import get_sqlite_connection_string
from squeaknode.db.squeak_db import SqueakDb
from squeaknode.lightning.lnd_lightning_client import LNDLightningClient
from squeaknode.node.received_payments_subscription_client import (
    OpenReceivedPaymentsSubscriptionClient,
)
from squeaknode.node.squeak_memory_whitelist import SqueakMemoryWhitelist
from squeaknode.node.squeak_node import SqueakNode
from squeaknode.node.squeak_peer_sync_worker import SqueakPeerSyncWorker
from squeaknode.node.squeak_rate_limiter import SqueakRateLimiter
from squeaknode.server.squeak_server_handler import SqueakServerHandler
from squeaknode.server.squeak_server_servicer import SqueakServerServicer
from squeaknode.sync.squeak_sync_controller import SqueakSyncController


logger = logging.getLogger(__name__)


def load_lightning_client(config) -> LNDLightningClient:
    return LNDLightningClient(
        config.lnd.host,
        config.lnd.rpc_port,
        config.lnd.tls_cert_path,
        config.lnd.macaroon_path,
    )


def load_rpc_server(config, handler) -> SqueakServerServicer:
    return SqueakServerServicer(
        config.server.rpc_host,
        config.server.rpc_port,
        handler,
    )


def load_admin_rpc_server(config, handler) -> SqueakAdminServerServicer:
    return SqueakAdminServerServicer(
        config.admin.rpc_host,
        config.admin.rpc_port,
        handler,
    )


def load_admin_web_server(config, handler) -> SqueakAdminWebServer:
    return SqueakAdminWebServer(
        config.webadmin.host,
        config.webadmin.port,
        config.webadmin.username,
        config.webadmin.password,
        config.webadmin.use_ssl,
        config.webadmin.login_required,
        config.webadmin.allow_cors,
        handler,
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


def load_blockchain_client(config):
    return BitcoinBlockchainClient(
        config.bitcoin.rpc_host,
        config.bitcoin.rpc_port,
        config.bitcoin.rpc_user,
        config.bitcoin.rpc_pass,
        config.bitcoin.rpc_use_ssl,
        config.bitcoin.rpc_ssl_cert,
    )


def sigterm_handler(_signo, _stack_frame):
    # Raises SystemExit(0):
    sys.exit(0)


def start_admin_rpc_server(rpc_server):
    logger.info("Starting admin RPC server...")
    thread = threading.Thread(
        target=rpc_server.serve,
        args=(),
    )
    thread.daemon = True
    thread.start()


def load_admin_web_server_enabled(config):
    return config.webadmin.enabled


def start_admin_web_server(admin_web_server):
    logger.info("Starting admin web server...")
    thread = threading.Thread(
        target=admin_web_server.serve,
        args=(),
    )
    thread.daemon = True
    thread.start()


def start_sync_worker(sync_worker):
    logger.info("Starting sync worker...")
    thread = threading.Thread(
        target=sync_worker.start_running,
        args=(),
    )
    thread.daemon = True
    thread.start()


def parse_args():
    parser = argparse.ArgumentParser(
        description="squeaknode runs a node using squeak protocol. ",
    )
    parser.add_argument(
        "--config",
        dest="config",
        type=str,
        help="Path to the config file.",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        type=str,
        default="info",
        help="Logging level",
    )
    # subparsers = parser.add_subparsers(help="sub-command help")

    # # create the parser for the "run-server" command
    # parser_run_server = subparsers.add_parser(
    #     "run-server", help="run-server help")
    # parser_run_server.set_defaults(func=run_server)

    # return parser.parse_args()

    parser.set_defaults(func=run_node)
    return parser.parse_args()


def main():
    logging.basicConfig(level=logging.ERROR)
    args = parse_args()

    # Set the log level
    level = args.log_level.upper()
    logging.getLogger().setLevel(level)

    logger.info("Starting squeaknode...")
    config = SqueaknodeConfig(args.config)
    config.read()
    logger.info("config: {}".format(config))
    logger.info("bitcoin rpc host: {}, rpc port: {}, rpc user: {}, rpc pass: {}, rpc use_ssl: {}, rpc ssl cert: {}".format(
        config.bitcoin.rpc_host,
        config.bitcoin.rpc_port,
        config.bitcoin.rpc_user,
        config.bitcoin.rpc_pass,
        config.bitcoin.rpc_use_ssl,
        config.bitcoin.rpc_ssl_cert,
    ))

    # Set the log level again
    level = config.core.log_level
    logging.getLogger().setLevel(level)

    args.func(config)


def run_node(config):
    # load the network
    network = config.core.network
    SelectParams(network)

    # load the db
    squeak_db = load_db(config, network)
    squeak_db.init()

    # load the lightning client
    lightning_client = load_lightning_client(config)

    # load the blockchain client
    blockchain_client = load_blockchain_client(config)

    squeak_core = SqueakCore(
        blockchain_client,
        lightning_client,
    )
    squeak_rate_limiter = SqueakRateLimiter(
        squeak_db,
        config.core.max_squeaks_per_address_per_hour,
    )
    squeak_whitelist = SqueakMemoryWhitelist(
        squeak_db,
    )

    squeak_controller = SqueakController(
        squeak_db,
        squeak_core,
        squeak_whitelist,
        squeak_rate_limiter,
        config,
    )

    # Create and start the squeak node
    squeak_node = SqueakNode(
        squeak_controller,
    )
    squeak_node.start_running()

    sync_controller = SqueakSyncController(
        squeak_controller,
        config.sync.block_range,
    )

    admin_handler = load_admin_handler(
        lightning_client, squeak_controller, sync_controller)

    # start admin rpc server
    if config.admin.rpc_enabled:
        admin_rpc_server = load_admin_rpc_server(config, admin_handler)
        start_admin_rpc_server(admin_rpc_server)

    # start admin web server
    if config.webadmin.enabled:
        admin_web_server = load_admin_web_server(config, admin_handler)
        start_admin_web_server(admin_web_server)

    # start sync worker
    if config.sync.enabled:
        sync_worker = load_sync_worker(config, sync_controller)
        start_sync_worker(sync_worker)

    # start rpc server
    handler = load_handler(squeak_controller)
    server = load_rpc_server(config, handler)
    server.serve()


if __name__ == "__main__":
    main()
