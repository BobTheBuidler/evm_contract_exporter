
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Union

import a_sync
import eth_retry
from generic_exporters import TimeSeriesExporter
from generic_exporters.plan import TimeDataRow
from generic_exporters.timeseries import _WideTimeSeries
from multicall.utils import raise_if_exception_in
from y.time import get_block_timestamp_async

from evm_contract_exporter import utils
from evm_contract_exporter._address import _AddressKeyedTimeSeries
from evm_contract_exporter.datastore import GenericContractTimeSeriesKeyValueStore


logger = logging.getLogger(__name__)


class ContractMetricExporter(TimeSeriesExporter):
    datastore: GenericContractTimeSeriesKeyValueStore
    """A base class to adapt generic_exporter's TimeSeriesExporterBase for evm analysis needs. Inherit from this class to create your bespoke metric exporters."""
    _semaphore_value = 1
    def __init__(
        self,
        chainid: int,
        timeseries: Union[_AddressKeyedTimeSeries, _WideTimeSeries[_AddressKeyedTimeSeries]],
        *, 
        interval: timedelta = timedelta(days=1), 
        buffer: timedelta = timedelta(minutes=5),
        datastore: Optional["GenericContractTimeSeriesKeyValueStore"] = None,
        sync: bool = True,
    ) -> None:
        datastore = datastore or GenericContractTimeSeriesKeyValueStore(chainid)
        if not len({field.address for field in timeseries.metrics}) == 1:
            raise ValueError("all metrics must share an address")
        query = timeseries[self.start_timestamp(sync=False):None:interval]
        super().__init__(query, datastore, buffer=buffer, sync=sync)
        self.chainid = chainid
        self.semaphore = a_sync.Semaphore(self._semaphore_value, name=self.query)
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} for {self.query}>"
    
    async def data_exists(self, ts: datetime) -> List[bool]:
        return await asyncio.gather(*[self.datastore.data_exists(field.address, field.key, ts) for field in self.query.metrics])

    async def ensure_data(self, ts: datetime) -> None:
        exists = await self.data_exists(ts, sync=False)
        if all(exists):
            logger.debug('complete data for %s at %s already exists in datastore', self, ts)
            return
        elif any(exists):
            data = await a_sync.gather(
                {
                    field: field.produce(ts, sync=False) 
                    for field, field_exists
                    in zip(self.query.metrics, exists)
                    if not field_exists
                }, 
                return_exceptions=True,
            )
            raise_if_exception_in(data.values())
        else:
            logger.debug('no data exists for %s, exporting...', self)
            data: TimeDataRow = await self.produce(ts, sync=False)
        if data:
            raise_if_exception_in(
                await asyncio.gather(
                    *[self.datastore.push(field.address, field.key, ts, value) for field, value in data.items() if value is not None], 
                    return_exceptions=True,
                )
            )

    @eth_retry.auto_retry
    async def start_timestamp(self) -> datetime:
        earliest_deploy_block = min(await asyncio.gather(*[utils.get_deploy_block(field.address) for field in self.query.metrics]))
        deploy_timestamp = datetime.fromtimestamp(await get_block_timestamp_async(earliest_deploy_block), tz=timezone.utc)
        iseconds = self.query.interval.total_seconds()
        rounded_down = datetime.fromtimestamp(deploy_timestamp.timestamp() // iseconds * iseconds, tz=timezone.utc)
        start_timestamp = rounded_down + self.query.interval
        logger.debug("rounded %s to %s (interval %s)", deploy_timestamp, start_timestamp, self.query.interval)
        return start_timestamp
    
    async def produce(self, timestamp: datetime) -> TimeDataRow:
        # NOTE: we fetch this before we enter the semaphore to ensure its cached in memory when we need to use it and we dont block unnecessarily
        block = await utils.get_block_at_timestamp(timestamp)
        async with self.semaphore:
            logger.debug("%s producing %s block %s", self, timestamp, block)
            # NOTE: only works with one field for now
            retval = await self.query[timestamp]
            logger.debug("%s produced %s at %s block %s", self, retval, timestamp, block)
            return retval
