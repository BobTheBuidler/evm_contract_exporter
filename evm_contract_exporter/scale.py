
from datetime import datetime
from decimal import Decimal

from async_property import async_cached_property
from generic_exporters import Constant
from y import ERC20

from evm_contract_exporter import _smartscale, types


class Scale(Constant):
    """A `Constant` that represents a scaling factor for an unscaled (u)int value returned from a `ContractCall`"""
    sync=False
    def __init__(self, decimals: int) -> None:
        super().__init__(10 ** decimals)
    def __call__(self, *_, **__) -> Decimal:
        return self.value
    async def coroutine(self, *_, **__) -> Decimal:
        return self.value

class SmartScale(Scale, metaclass=_smartscale.SmartScaleSingletonMeta):
    """A `Scale` object that is initialized with a contract address instead of a `decimals` value"""
    sync=False
    def __init__(self, contract_address: types.address) -> None:
        self.contract = contract_address
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} contract={self.contract}>"
    @async_cached_property
    async def value(self) -> Decimal:
        return Decimal(await ERC20(self.contract, asynchronous=True).scale)
    async def coroutine(self, *_, **__) -> Decimal:
        return await self.value
    async def produce(self, timestamp: datetime) -> Decimal:
        return await self.value
