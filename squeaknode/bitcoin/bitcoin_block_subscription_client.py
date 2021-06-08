import binascii
import logging
import struct

import zmq.asyncio

logger = logging.getLogger(__name__)


class BitcoinBlockSubscriptionClient:
    """Get an iterator of new bitcoin blocks."""

    def __init__(
        self,
        host: str,
        port: int,
    ) -> None:
        self.zmqContext = zmq.Context()
        self.zmqSubSocket = self.zmqContext.socket(zmq.SUB)
        self.zmqSubSocket.setsockopt(zmq.RCVHWM, 0)
        self.zmqSubSocket.setsockopt_string(zmq.SUBSCRIBE, "hashblock")
        self.zmqSubSocket.setsockopt_string(zmq.SUBSCRIBE, "hashtx")
        self.zmqSubSocket.setsockopt_string(zmq.SUBSCRIBE, "rawblock")
        self.zmqSubSocket.setsockopt_string(zmq.SUBSCRIBE, "rawtx")
        self.zmqSubSocket.connect("tcp://{}:{}".format(host, port))

    def get_blocks(self) -> None:
        while True:
            print("Getting blocks...")
            topic, body, seq = self.zmqSubSocket.recv_multipart()
            sequence = "Unknown"
            if len(seq) == 4:
                sequence = str(struct.unpack('<I', seq)[-1])
            if topic == b"hashblock":
                print('- HASH BLOCK (' + sequence + ') -')
                print(binascii.hexlify(body))
            elif topic == b"hashtx":
                print('- HASH TX  (' + sequence + ') -')
                print(binascii.hexlify(body))
            elif topic == b"rawblock":
                print('- RAW BLOCK HEADER (' + sequence + ') -')
                print(binascii.hexlify(body[:80]))
            elif topic == b"rawtx":
                print('- RAW TX (' + sequence + ') -')
                print(binascii.hexlify(body))
            elif topic == b"sequence":
                hash = binascii.hexlify(body[:32])
                label = chr(body[32])
                mempool_sequence = None if len(
                    body) != 32 + 1 + 8 else struct.unpack("<Q", body[32 + 1:])[0]
                print('- SEQUENCE (' + sequence + ') -')
                print(hash, label, mempool_sequence)

    def stop_processing(self):
        self.zmqContext.term()
