
import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, AsyncIterable, Coroutine, Dict, List, Optional, Tuple, Union

import a_sync
from brownie.convert.datatypes import ReturnValue
from generic_exporters import QueryPlan, TimeSeriesExporter
from multicall.utils import raise_if_exception_in

from evm_contract_exporter.datastore import GenericContractTimeSeriesKeyValueStore
from evm_contract_exporter.processors._base import _ContractMetricProcessorBase
from evm_contract_exporter.metric import Metric


logger = logging.getLogger(__name__)

class _ContractMetricExporterBase(_ContractMetricProcessorBase, TimeSeriesExporter):
    """A base class to adapt generic_exporter's `_TimeSeriesExporterBase` for evm analysis needs. Inherit from this class to create your bespoke metric exporters."""
    datastore: GenericContractTimeSeriesKeyValueStore
    def __init__(
        self,
        chainid: int,
        query_plan: QueryPlan, 
        *,
        datastore: Optional[GenericContractTimeSeriesKeyValueStore] = None, 
        semaphore_value: Optional[int] = None, 
        sync: bool = True,
    ) -> None:
        if datastore is not None and not isinstance(datastore, GenericContractTimeSeriesKeyValueStore):
            raise TypeError(f"`datastore` must be an instance of `GenericContractTimeSeriesKeyValueStore`, you passed {datastore}")
        _ContractMetricProcessorBase.__init__(self, chainid, query_plan, semaphore_value=semaphore_value, sync=sync)
        self.datastore = datastore or GenericContractTimeSeriesKeyValueStore.get_for_chain(chainid)
    
    async def data_exists(self, ts: datetime) -> List[bool]:  # type: ignore [override]
        return await asyncio.gather(*[self.datastore.data_exists(field.address, field.key, ts) for field in self.query.metrics])

    async def ensure_data(self, ts: datetime) -> None:
        if semaphore := self._semaphore:
            async with semaphore[0-ts.timestamp()]:
                await self._ensure_data(ts)
        else:
            await self._ensure_data(ts)
    
    async def _ensure_data(self, ts: datetime) -> None:
        exists = await self.data_exists(ts, sync=False)
        if all(exists):
            logger.debug('complete data for %s at %s already exists in datastore', self, ts)
            return
        elif any(exists):
            coros: Dict[Metric, Coroutine[Any, Any, Decimal]] = {field: field.produce(ts, sync=False) for field, field_exists in zip(self.query.metrics, exists) if not field_exists}
            data: AsyncIterable[Tuple[Metric, Union[Decimal, Exception]]] = a_sync.as_completed(coros, return_exceptions=True, aiter=True)
        else:
            logger.debug('no data exists for %s, exporting...', self)
            tasks = self.query[ts].tasks
            await tasks._init_loader
            data = a_sync.as_completed(tasks, return_exceptions=True, aiter=True)
        insert_tasks = {}
        async for metric, result in data:
            if isinstance(result, ReturnValue):
                # TODO: find where these are comign from and stop them earlier
                raise TypeError(metric, metric._output_type, result)
            if result is None:
                # TODO: backport None support
                continue
            insert_tasks[metric] = asyncio.create_task(self.datastore.push(metric.address, metric.key, ts, result))
        raise_if_exception_in(await a_sync.gather(insert_tasks, return_exceptions=True))
