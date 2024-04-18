
import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from functools import cached_property
from typing import Dict, Optional

import a_sync
import eth_retry
from generic_exporters import QueryPlan
from generic_exporters.processors._base import _TimeSeriesProcessorBase
from y import contract_creation_block_async, get_block_at_timestamp
from y.time import get_block_timestamp_async

from evm_contract_exporter import types, utils
from evm_contract_exporter.metric import Metric


logger = logging.getLogger(__name__)

class _ContractMetricProcessorBase(_TimeSeriesProcessorBase):
    def __init__(
        self, 
        chainid: int, 
        query: QueryPlan, 
        *, 
        concurrency: Optional[int] = None, 
        sync: bool = True,
    ) -> None:
        if not isinstance(chainid, int):
            raise TypeError(f"`chainid` must be an integer. You passed {chainid}")
        if not len({field.address for field in query.metrics}) == 1:
            raise ValueError("all metrics must share an address")
        _TimeSeriesProcessorBase.__init__(self, query, concurrency=concurrency, sync=sync)
        self.chainid = chainid
        #self._queue = a_sync.ProcessingQueue(self._produce, self.concurrency)
    def __repr__(self) -> str:
        return f"<{type(self).__name__} for {self.query}>"
    @cached_property
    def _semaphore(self) -> Optional[a_sync.PrioritySemaphore]:
        # TODO: refactor this out now that generic_exporters uses Queue for memory management
        if self.concurrency:
            return a_sync.PrioritySemaphore(self.concurrency, name=self.__class__.__name__)
        return None
    @eth_retry.auto_retry
    async def start_timestamp(self) -> datetime:
        earliest_deploy_block = await self._earliest_deploy_block()
        deploy_timestamp = datetime.fromtimestamp(await get_block_timestamp_async(earliest_deploy_block), tz=timezone.utc)
        iseconds = self.query.interval.total_seconds()
        rounded_down = datetime.fromtimestamp(deploy_timestamp.timestamp() // iseconds * iseconds, tz=timezone.utc)
        start_timestamp = rounded_down + self.query.interval
        logger.debug("rounded %s to %s (interval %s)", deploy_timestamp, start_timestamp, self.query.interval)
        return start_timestamp
    """
    async def produce(self, timestamp: datetime) -> Dict[Metric, Decimal]:
        # NOTE: we fetch this before we enter the semaphore to ensure its cached in memory when we need to use it and we dont block unnecessarily
        await utils.get_block_at_timestamp(timestamp)
        return await self._queue(timestamp)
    async def _produce(self, timestamp: datetime) -> Dict[Metric, Decimal]:
        block = await get_block_at_timestamp(timestamp)
        logger.debug("%s producing %s block %s", self, timestamp, block)
        # NOTE: only works with one field for now
        retval = await self.query[timestamp]
        logger.debug("%s produced %s at %s block %s", self, retval, timestamp, block)
        return retval
    """
    async def _earliest_deploy_block(self) -> int:
        await self._load_deploy_blocks_to_memory()
        return min(await asyncio.gather(*[contract_creation_block_async(field.address) for field in self.query.metrics]))
    async def _load_deploy_blocks_to_memory(self) -> None:
        """ensure the deploy block for all relevant contracts is cached in memory before proceeding"""
        await utils.start_deploy_block_workers()
        contract: types.address
        for contract in {field.address for field in self.query.metrics}:
            utils._deploy_block_queue.put_nowait(contract)
        await utils._deploy_block_queue.join()