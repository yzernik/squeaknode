import logging
import queue
import time


logger = logging.getLogger(__name__)

LND_CONNECT_RETRY_S = 10


class ReceivedPaymentsVerifier:
    def __init__(self, squeak_db, lightning_client):
        self.squeak_db = squeak_db
        self.lightning_client = lightning_client

    def verify_received_payment(self, invoice):
        logger.info("Verifying invoice: {}".format(invoice))
        if invoice.settled:
            preimage_hash = invoice.r_hash.hex()
            settle_index = invoice.settle_index
            self._mark_received_payment_paid(preimage_hash, settle_index)

    def process_subscribed_invoices(self):
        while True:
            self.try_processing()

    def try_processing(self):
        latest_settle_index = self._get_latest_settle_index() or 0
        logger.info("latest settle index: {}".format(latest_settle_index))
        try:
            for invoice in self.lightning_client.subscribe_invoices(
                    settle_index=latest_settle_index,
            ):
                self.verify_received_payment(invoice)
        except:
            logger.error(
                "Unable to subscribe invoices from lnd. Retrying in {} seconds".format(LND_CONNECT_RETRY_S),
                exc_info=True,
            )
            time.sleep(LND_CONNECT_RETRY_S)

    def _mark_received_payment_paid(self, preimage_hash, settle_index):
        logger.info("Marking received payment paid for preimage_hash: {} with settle_index: {}".format(
            preimage_hash,
            settle_index,
        ))
        self.squeak_db.mark_received_payment_paid(preimage_hash, settle_index)

    def _get_latest_settle_index(self):
        logger.info("Getting latest settle index from db...")
        return self.squeak_db.get_latest_received_payment_index()
