import logging
from pathlib import Path

from typedconfig import Config
from typedconfig import group_key
from typedconfig import key
from typedconfig import section
from typedconfig.source import DictConfigSource
from typedconfig.source import EnvironmentConfigSource
from typedconfig.source import IniFileConfigSource

logger = logging.getLogger(__name__)


DEFAULT_NETWORK = "testnet"
DEFAULT_PRICE_MSAT = 10000
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_MAX_SQUEAKS_PER_ADDRESS_PER_BLOCK = 100
DEFAULT_SERVER_RPC_HOST = "0.0.0.0"
DEFAULT_SERVER_RPC_PORT = 8774
DEFAULT_ADMIN_RPC_HOST = "0.0.0.0"
DEFAULT_ADMIN_RPC_PORT = 8994
DEFAULT_WEBADMIN_HOST = "0.0.0.0"
DEFAULT_WEBADMIN_PORT = 12994
DEFAULT_BITCOIN_RPC_HOST = "localhost"
DEFAULT_BITCOIN_RPC_PORT = 8334
DEFAULT_BITCOIN_ZEROMQ_PORT = 28332
BITCOIN_RPC_PORT = {
    "mainnet": 8332,
    "testnet": 18332,
    "simnet": 18556,
}
DEFAULT_LND_PORT = 9735
DEFAULT_LND_RPC_PORT = 10009
DEFAULT_SQK_DIR = ".sqk"
DEFAULT_SQK_DIR_PATH = str(Path.home() / DEFAULT_SQK_DIR)
DEFAULT_LND_HOST = "localhost"
DEFAULT_SYNC_INTERVAL_S = 10
DEFAULT_SYNC_TIMEOUT_S = 10
DEFAULT_SYNC_BLOCK_INTERVAL = 2016
DEFAULT_SENT_OFFER_RETENTION_S = 86400
DEFAULT_OFFER_DELETION_INTERVAL_S = 10
DEFAULT_SUBSCRIBE_INVOICES_RETRY_S = 10
DEFAULT_SQUEAK_RETENTION_S = 604800
DEFAULT_SQUEAK_DELETION_INTERVAL_S = 10


@section('bitcoin')
class BitcoinConfig(Config):
    rpc_host = key(cast=str, required=False, default=DEFAULT_BITCOIN_RPC_HOST)
    rpc_port = key(cast=int, required=False, default=DEFAULT_BITCOIN_RPC_PORT)
    rpc_user = key(cast=str, required=False, default="")
    rpc_pass = key(cast=str, required=False, default="")
    rpc_use_ssl = key(cast=bool, required=False, default=False)
    rpc_ssl_cert = key(cast=str, required=False, default="")
    zeromq_port = key(cast=int, required=False,
                      default=DEFAULT_BITCOIN_ZEROMQ_PORT)


@section('lnd')
class LndConfig(Config):
    host = key(cast=str, required=False, default=DEFAULT_LND_HOST)
    external_host = key(cast=str, required=False, default="")
    port = key(cast=int, required=False, default=DEFAULT_LND_PORT)
    rpc_port = key(cast=int, required=False, default=DEFAULT_LND_RPC_PORT)
    tls_cert_path = key(cast=str, required=False, default="")
    macaroon_path = key(cast=str, required=False, default="")


@section('server')
class ServerConfig(Config):
    rpc_enabled = key(cast=bool, required=False, default=True)
    rpc_host = key(cast=str, required=False, default=DEFAULT_SERVER_RPC_HOST)
    rpc_port = key(cast=int, required=False, default=DEFAULT_SERVER_RPC_PORT)


@section('admin')
class AdminConfig(Config):
    rpc_enabled = key(cast=bool, required=False, default=False)
    rpc_host = key(cast=str, required=False, default=DEFAULT_ADMIN_RPC_HOST)
    rpc_port = key(cast=int, required=False, default=DEFAULT_ADMIN_RPC_PORT)


@section('webadmin')
class WebadminConfig(Config):
    enabled = key(cast=bool, required=False, default=False)
    host = key(cast=str, required=False, default=DEFAULT_WEBADMIN_HOST)
    port = key(cast=int, required=False, default=DEFAULT_WEBADMIN_PORT)
    username = key(cast=str, required=False, default="")
    password = key(cast=str, required=False, default="")
    use_ssl = key(cast=bool, required=False, default=False)
    login_disabled = key(cast=bool, required=False, default=False)
    allow_cors = key(cast=bool, required=False, default=False)


@section('core')
class CoreConfig(Config):
    network = key(cast=str, required=False, default=DEFAULT_NETWORK)
    default_peer_rpc_port = key(
        cast=int, required=False, default=DEFAULT_SERVER_RPC_PORT)
    price_msat = key(cast=int, required=False, default=DEFAULT_PRICE_MSAT)
    max_squeaks_per_address_per_block = key(
        cast=int, required=False, default=DEFAULT_MAX_SQUEAKS_PER_ADDRESS_PER_BLOCK)
    sqk_dir_path = key(cast=str, required=False, default=DEFAULT_SQK_DIR_PATH)
    log_level = key(cast=str, required=False, default=DEFAULT_LOG_LEVEL)
    sent_offer_retention_s = key(
        cast=int, required=False, default=DEFAULT_SENT_OFFER_RETENTION_S)
    subscribe_invoices_retry_s = key(
        cast=int, required=False, default=DEFAULT_SUBSCRIBE_INVOICES_RETRY_S)
    squeak_retention_s = key(
        cast=int, required=False, default=DEFAULT_SQUEAK_RETENTION_S)
    squeak_deletion_interval_s = key(
        cast=int, required=False, default=DEFAULT_SQUEAK_DELETION_INTERVAL_S)
    offer_deletion_interval_s = key(
        cast=int, required=False, default=DEFAULT_OFFER_DELETION_INTERVAL_S)


@section('sync')
class SyncConfig(Config):
    enabled = key(cast=bool, required=False, default=True)
    interval_s = key(cast=int, required=False, default=DEFAULT_SYNC_INTERVAL_S)
    timeout_s = key(cast=float, required=False, default=DEFAULT_SYNC_TIMEOUT_S)
    block_interval = key(cast=int, required=False,
                         default=DEFAULT_SYNC_BLOCK_INTERVAL)


@section('db')
class DbConfig(Config):
    connection_string = key(cast=str, required=False, default="")


class SqueaknodeConfig(Config):
    bitcoin = group_key(BitcoinConfig)
    lnd = group_key(LndConfig)
    server = group_key(ServerConfig)
    admin = group_key(AdminConfig)
    webadmin = group_key(WebadminConfig)
    core = group_key(CoreConfig)
    sync = group_key(SyncConfig)
    db = group_key(DbConfig)
    # description = key(cast=str, section_name="general")

    def __init__(self, config_path=None, dict_config=None):
        super().__init__()
        self.prefix = "SQUEAKNODE"
        self.config_path = config_path
        self.dict_config = dict_config

    def read(self):
        if self.dict_config is not None:
            self.add_source(DictConfigSource(self.dict_config))
        self.add_source(EnvironmentConfigSource(prefix=self.prefix))
        if self.config_path is not None:
            self.add_source(IniFileConfigSource(self.config_path))
        return super().read()
