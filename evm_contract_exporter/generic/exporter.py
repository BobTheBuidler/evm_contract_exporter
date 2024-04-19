
import asyncio
import logging
from datetime import timedelta
from functools import cached_property
from typing import List, Optional

from async_property import async_cached_property
from brownie import chain, convert
from y import Contract
from y.datatypes import Address

from evm_contract_exporter.contract import ContractExporterBase
from evm_contract_exporter.datastore import GenericContractTimeSeriesKeyValueStore
from evm_contract_exporter.exporters.method import ViewMethodExporter
from evm_contract_exporter.generic.contract import safe_views
from evm_contract_exporter.processors.method import _wrap_method
from evm_contract_exporter.metric import AnyContractCallMetric, StructDerivedMetric, TupleDerivedMetric
from evm_contract_exporter.types import EXPORTABLE_TYPES, UNEXPORTABLE_TYPES, address


logger = logging.getLogger(__name__)

class GenericContractExporter(ContractExporterBase):
    """
    This exporter will export a full history of all of the contract's view methods which return a single numeric result, along with all numeric tuple/struct members.
    # NOTE: not implemented TODO: It will also export historical price data.
    """
    def __init__(
        self, 
        contract: Address, 
        *, 
        interval: timedelta = timedelta(days=1), 
        buffer: Optional[timedelta] = None,
        datastore: Optional[GenericContractTimeSeriesKeyValueStore] = None,
        concurrency: Optional[int] = 100,
        sync: bool = True
    ) -> None:
        super().__init__(chain.id, interval=interval, buffer=buffer, datastore=datastore, concurrency=concurrency, sync=sync)
        self.address = convert.to_address(contract)
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} contract={self.address} interval={self.interval}>"
    @cached_property
    def task(self) -> asyncio.Task:
        return asyncio.Task(self._await())
    @async_cached_property
    async def method_exporter(self) -> Optional[ViewMethodExporter]:
        contract = await Contract.coroutine(self.address)
        data = [d for view_method in safe_views(contract) for d in unpack(view_method)]
        if data:
            return ViewMethodExporter(
                *data, 
                interval=self.interval, 
                buffer=self.buffer, 
                datastore=self.datastore, 
                concurrency=self.concurrency, 
                sync=self.sync,
            )
        
    @classmethod
    def create_export_task(
        cls, 
        contract: address,
        *, 
        interval: timedelta = timedelta(days=1), 
        buffer: timedelta = timedelta(minutes=5),
    ) -> asyncio.Task:
        return cls(contract, interval=interval, buffer=buffer).task
    async def _await(self) -> None:
        if method_exporter := await self.method_exporter:
            await method_exporter

def unpack(metric: AnyContractCallMetric) -> List[AnyContractCallMetric]:
    """
    If `metric` returns multiple values, we can't export it. We need to derive new metrics to represent each field.
    returns a list of exportable metrics derived from input `metric`
    """
    timeseries = _wrap_method(metric, True)
    unpacked = []
    if timeseries.metric._returns_array_type:
        logger.warning('unable to export array type: %s', timeseries.metric)
    elif timeseries.metric._returns_struct_type:
        outputs = timeseries.metric._outputs
        if len(outputs) == 1:
            outputs = outputs[0]['components']
        assert all(abi['name'] for abi in outputs), outputs
        for abi in outputs:
            struct_key = abi['name']
            derived_metric: StructDerivedMetric = timeseries.metric[struct_key]
            abi_type: str = abi["type"]
            if derived_metric._returns_array_type:
                logger.warning("unable to export struct member Contract('%s').%s with dynamic array return type", derived_metric.address, derived_metric.key)
            elif derived_metric._returns_struct_type:
                unpacked.extend(unpack(derived_metric))
            elif abi_type in EXPORTABLE_TYPES:
                unpacked.append(derived_metric)
            elif abi_type == "tuple":
                logger.warning("unable to export struct member Contract('%s').%s with tuple return type abi %s", derived_metric, derived_metric.key, abi)
            elif abi_type not in UNEXPORTABLE_TYPES:
                logger.warning("unable to export struct member Contract('%s').%s return type %s", derived_metric, derived_metric.key, abi_type)
    elif timeseries.metric._returns_tuple_type:
        member: TupleDerivedMetric
        for member in (timeseries.metric[i] for i in range(len(timeseries.metric._outputs))):
            if member._returns_array_type:
                logger.warning("unable to export tuple member Contract('%s').%s with dynamic array return type", member.address, member.key)
            elif member._returns_struct_type:
                unpacked.extend(unpack(member))
            elif (abi_type := member.abi["type"]) in EXPORTABLE_TYPES:
                unpacked.append(member)
            elif abi_type == "tuple":
                logger.warning("unable to export tuple member Contract('%s').%s with tuple return type abi %s", member.address, member.key, abi)
            elif abi_type not in UNEXPORTABLE_TYPES:
                logger.warning("unable to export tuple member Contract('%s').%s with abi %s", member, member.key, member.abi)
    else:
        unpacked.append(timeseries.metric)
    return unpacked