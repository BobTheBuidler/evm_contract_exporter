
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import y
from brownie import chain
from y.exceptions import yPriceMagicError
from evm_contract_exporter.datastore import GenericContractTimeSeriesKeyValueStore

from evm_contract_exporter import types
from evm_contract_exporter.exporters import ContractMetricExporter
from evm_contract_exporter.metric import Metric
from evm_contract_exporter.timeseries import WideTimeSeries


logger = logging.getLogger(__name__)

class Price(Metric):
    key = "ypm_price"
    async def produce(self, timestamp: datetime) -> Decimal:
        block = await y.get_block_at_timestamp(timestamp)
        if not block:
            raise ValueError(block)
        retval = await y.get_price(self.address, block, sync=False)
        if isinstance(retval, yPriceMagicError) and isinstance(retval.exception, y.PriceError):
            logger.info("%s %s at %s: returning 0 due to PriceError", self.address, self.key, timestamp)
            return Decimal(0)
        logger.info("%s %s at %s: %s", self.address, self.key, timestamp, retval)
        if isinstance(retval, Exception):
            raise retval
        return Decimal(retval)

class PriceExporter(ContractMetricExporter):
    def __init__(
        self, 
        *addresses: types.address, 
        interval: timedelta = timedelta(days=1), 
        buffer: Optional[timedelta] = None, 
        datastore: Optional[GenericContractTimeSeriesKeyValueStore] = None, 
        semaphore_value: Optional[int] = None, 
        sync: bool = True,
    ) -> None:
        metrics = [Price(address) for address in addresses]
        timeseries = WideTimeSeries(*metrics)
        super().__init__(chain.id, timeseries, interval=interval, buffer=buffer, datastore=datastore, semaphore_value=semaphore_value, sync=sync)