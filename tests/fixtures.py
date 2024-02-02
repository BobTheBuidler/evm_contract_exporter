import pytest
import y

from evm_contract_exporter import Scale, SmartScale

@pytest.fixture
def scale():
    return Scale(18)

@pytest.fixture
def weth():
    return y.weth

@pytest.fixture
def weth_smart_scale(weth):
    return SmartScale(weth.address)
