
from brownie import convert
from generic_exporters import Metric

from evm_contract_exporter import types

# NOTE: is this needed? 

class _AddressKeyedMetric(Metric):
    """This helper class is a `Metric` object that relates to a specific wallet address"""
    def __init__(self, address: types.address) -> None:
        super().__init__()
        self.address = convert.to_address(address)
