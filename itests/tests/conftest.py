import pytest

import grpc

from lnd_lightning_client import LNDLightningClient

from proto import lnd_pb2 as ln
from proto import lnd_pb2_grpc as lnrpc
from proto import (
    squeak_admin_pb2,
    squeak_admin_pb2_grpc,
    squeak_server_pb2,
    squeak_server_pb2_grpc,
)


@pytest.fixture
def server_stub():
    with grpc.insecure_channel(
        "sqkserver:8774"
    ) as server_channel:
        yield squeak_server_pb2_grpc.SqueakServerStub(server_channel)

@pytest.fixture
def admin_stub():
    with grpc.insecure_channel(
            "sqkserver:8994"
    ) as admin_channel:
        yield squeak_admin_pb2_grpc.SqueakAdminStub(admin_channel)
