
from decimal import Decimal

from tests.evm_contract_exporter.fixtures import *

test_val = Decimal(10 ** 18)

def test_scale(scale):
    assert scale.value == test_val
    assert scale.produce(None, sync=True) == test_val

def test_smart_scale(weth_smart_scale):
    assert weth_smart_scale.produce(None, sync=True) == test_val
