import logging
import threading

from squeaknode.bitcoin.bitcoin_block_subscription_client import BitcoinBlockSubscriptionClient

logger = logging.getLogger(__name__)


class SubscribeBlocksWorker:
    def __init__(
            self,
            block_subscription_client: BitcoinBlockSubscriptionClient,
            stopped: threading.Event,
    ):
        self.block_subscription_client = block_subscription_client
        self.stopped = stopped

    def start_running(self):
        threading.Thread(
            target=self.subscribe_blocks,
            daemon=True,
        ).start()

    def subscribe_blocks(self):
        self.block_subscription_client.get_blocks()
