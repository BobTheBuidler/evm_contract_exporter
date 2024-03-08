
import asyncio
import logging
from datetime import datetime, timezone
from functools import cached_property
from typing import Optional

import a_sync
import eth_retry
from generic_exporters import QueryPlan
from generic_exporters.processors._base import _TimeSeriesProcessorBase
from generic_exporters.plan import TimeDataRow
from y.time import get_block_timestamp_async

from evm_contract_exporter import utils


logger = logging.getLogger(__name__)

class _ContractMetricProcessorBase(_TimeSeriesProcessorBase):
    def __init__(
        self, 
        chainid: int, 
        query: QueryPlan, 
        *, 
        semaphore_value: Optional[int] = None, 
        sync: bool = True,
    ) -> None:
        if not isinstance(chainid, int):
            raise TypeError(f"`chainid` must be an integer. You passed {semaphore_value}")
        if not len({field.address for field in query.metrics}) == 1:
            raise ValueError("all metrics must share an address")
        if semaphore_value is not None and not isinstance(semaphore_value, int):
            raise TypeError(f"`semaphore_value` must be int or None. You passed {semaphore_value}")
        super().__init__(query, sync=sync)
        self.chainid = chainid
        self._semaphore_value = semaphore_value
    def __repr__(self) -> str:
        return f"<{type(self).__name__} for {self.query}>"
    @cached_property
    def _semaphore(self) -> Optional[a_sync.PrioritySemaphore]:
        if self._semaphore_value:
            return a_sync.PrioritySemaphore(self._semaphore_value, name=self.__class__.__name__)
        return None
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
        if semaphore := self._semaphore: 
            async with semaphore[0 - timestamp.timestamp()]:
                return await self._produce(timestamp)
        else:
            return await self._produce(timestamp)
    async def _produce(self, timestamp: datetime) -> TimeDataRow:
        block = await utils.get_block_at_timestamp(timestamp)
        logger.debug("%s producing %s block %s", self, timestamp, block)
        # NOTE: only works with one field for now
        retval = await self.query[timestamp]
        logger.debug("%s produced %s at %s block %s", self, retval, timestamp, block)
        return retval