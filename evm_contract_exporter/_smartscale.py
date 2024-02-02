
from typing import TYPE_CHECKING

from brownie import convert
from generic_exporters import _constant

from evm_contract_exporter import types

if TYPE_CHECKING:
    from evm_contract_exporter import SmartScale


class SmartScaleSingletonMeta(_constant.ConstantSingletonMeta):
    def __call__(cls, contract_address: types.address) -> "SmartScale":
        return super().__call__(types.address(convert.to_address(contract_address)))
    