import argparse
import logging
import signal
import sys
import threading
import time

from configparser import ConfigParser

from squeak.params import SelectParams
from squeak.core.signing import CSigningKey

from squeaknode.common.blockchain_client import BlockchainClient
from squeaknode.common.lightning_client import LightningClient
from squeaknode.common.btcd_blockchain_client import BTCDBlockchainClient
from squeaknode.common.lnd_lightning_client import LNDLightningClient
from squeaknode.client.rpc.route_guide_server import RouteGuideServicer
from squeaknode.common.rpc.squeak_server_servicer import SqueakServerServicer
from squeaknode.client.clientsqueaknode import SqueakNodeClient
from squeaknode.client.db import SQLiteDBFactory
from squeaknode.client.db import initialize_db
from squeaknode.server.squeak_server_handler import SqueakServerHandler


def load_lightning_client(config) -> LightningClient:
    return LNDLightningClient(
        config['lnd']['rpc_host'],
        config['lnd']['rpc_port'],
        config['lnd']['network'],
    )


def start_rpc_server(handler):
    print('Calling start_rpc_server...', flush=True)
    server = SqueakServerServicer(handler)
    # thread = threading.Thread(
    #     target=server.serve,
    #     args=(),
    # )
    # thread.daemon = True
    # thread.start()
    # return server, thread
    server.serve()


def load_handler(lightning_client):
    return SqueakServerHandler(
        lightning_client,
    )


def sigterm_handler(_signo, _stack_frame):
    # Raises SystemExit(0):
    sys.exit(0)


def parse_args():
    parser = argparse.ArgumentParser(
        description="squeaknode runs a node using squeak protocol. ",
    )
    parser.add_argument(
        '--config',
        dest='config',
        type=str,
        help='Path to the config file.',
    )
    parser.add_argument(
        '--log-level',
        dest='log_level',
        type=str,
        default='info',
        help='Logging level',
    )
    subparsers = parser.add_subparsers(help='sub-command help')

    # # create the parser for the "init-db" command
    # parser_init_db = subparsers.add_parser('init-db', help='init-db help')
    # parser_init_db.set_defaults(func=init_db)

    # create the parser for the "run-server" command
    parser_run_server = subparsers.add_parser('run-server', help='run-server help')
    parser_run_server.set_defaults(func=run_server)

    return parser.parse_args()


def main():
    print("Running main() in server...", flush=True)
    logging.basicConfig(level=logging.ERROR)
    args = parse_args()

    # Set the log level
    level = args.log_level.upper()
    print("level: " + level)
    logging.getLogger().setLevel(level)

    # Get the config object
    config = ConfigParser()
    config.read(args.config)

    args.func(config)


# def init_db(config):
#     db_factory = load_db_factory(config)
#     with db_factory.make_conn() as conn:
#         initialize_db(conn)
#     print("Initialized the database.")


def run_server(config):
    print('network:', config['DEFAULT']['network'], flush=True)
    SelectParams(config['DEFAULT']['network'])

    print('starting lightning client here...', flush=True)
    # lightning_client = load_lightning_client(config)
    # db_factory = load_db_factory(config)
    # node = load_client(blockchain_client, lightning_client, signing_key, db_factory)
    handler = load_handler(None)

    # start rpc server
    start_rpc_server(handler)
    # rpc_server, rpc_server_thread = start_rpc_server(handler)
    # print("rpc server started...", flush=True)

    # signal.signal(signal.SIGTERM, sigterm_handler)

    # print("sleeping....", flush=True)
    # try:
    #     while True:
    #         time.sleep(1)
    # finally:
    #     print("Shutting down...", flush=True)


if __name__ == '__main__':
    main()
