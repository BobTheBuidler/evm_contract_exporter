
from datetime import datetime
from decimal import Decimal

from generic_exporters import Metric
from y import get_price

from evm_contract_exporter import utils
from evm_contract_exporter.exporters.metric import ContractMetricExporter
from evm_contract_exporter.types import address


class Price(Metric):
    def __init__(self, address: address) -> None:
        self.address = address
    async def produce(self, timestamp: datetime) -> Decimal:
        block = utils.get_block_at_timestamp(timestamp)
        return Decimal(await get_price(self.address, block, skip_cache=True, silent=True, sync=False))


class PriceExporter(ContractMetricExporter):
    metric_name = "price"
    async def _produce(self, block: int) -> Decimal:
        return Decimal(await get_price(self.address, block, skip_cache=True, silent=True, sync=False))
