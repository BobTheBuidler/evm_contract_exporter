
import asyncio
import logging
from datetime import datetime
from typing import List, Optional

import a_sync
from brownie.convert.datatypes import ReturnValue
from generic_exporters import QueryPlan
from generic_exporters.processors.exporters._base import _TimeSeriesExporterBase
from generic_exporters.plan import TimeDataRow
from multicall.utils import raise_if_exception_in

from evm_contract_exporter.datastore import GenericContractTimeSeriesKeyValueStore
from evm_contract_exporter.processors._base import _ContractMetricProcessorBase


logger = logging.getLogger(__name__)

class _ContractMetricExporterBase(_ContractMetricProcessorBase, _TimeSeriesExporterBase):
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
        super().__init__(chainid, query_plan, semaphore_value=semaphore_value, sync=sync)
        self.datastore = datastore or GenericContractTimeSeriesKeyValueStore.get_for_chain(chainid)
    
    async def data_exists(self, ts: datetime) -> List[bool]:  # type: ignore [override]
        return await asyncio.gather(*[self.datastore.data_exists(field.address, field.key, ts) for field in self.query.metrics])

    async def ensure_data(self, ts: datetime) -> None:
        if semaphore := self.semaphore:
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
            data = await a_sync.gather(
                {
                    field: field.produce(ts, sync=False) 
                    for field, field_exists
                    in zip(self.query.metrics, exists)
                    if not field_exists
                }, 
                return_exceptions=True,
            )
        else:
            logger.debug('no data exists for %s, exporting...', self)
            data: TimeDataRow = await self._produce(ts)
        if data:
            raise_if_exception_in(
                await asyncio.gather(
                    *[
                        self.datastore.push(field.address, field.key, ts, value) 
                        for field, value in data.items() 
                        if value is not None
                        # TODO: find where these are comign from and stop them earlier
                        and not isinstance(value, ReturnValue)
                    ],
                    return_exceptions=True,
                )
            )
            for field, value in data.items():
                if isinstance(value, ReturnValue):
                    raise TypeError(field, field._output_type, value)