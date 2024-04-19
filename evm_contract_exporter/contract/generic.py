
import asyncio
import logging
from datetime import timedelta
from functools import cached_property
from typing import List, Optional

from async_property import async_cached_property
from brownie import chain, convert
from brownie.network.contract import ContractCall, ContractTx, OverloadedMethod
from y import Contract
from y.datatypes import Address

from evm_contract_exporter.contract import ContractExporterBase
from evm_contract_exporter.datastore import GenericContractTimeSeriesKeyValueStore
from evm_contract_exporter.exporters.method import ViewMethodExporter
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
        data = [d for view_method in _safe_views(contract) for d in unpack(view_method)]
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

def _list_functions(contract: Contract) -> List[ContractCall]:
    fns = []
    for item in contract.abi:
        if item["type"] != "function":
            continue
        attr_name = item["name"]
        if attr_name == "_name":
            # this conflicts with brownie's `_ContractBase._name` property, `contract._name` will not return a callable
            continue
        elif attr_name == "_owner":
            # this conflicts with brownie's `_ContractBase._owner` property, `contract._owner` will not return a callable
            continue
        elif attr_name == "info":
            # this conflicts with brownie's `_ContractBase.info` method, `contract.info` will not return a `ContractCall` object
            continue
        fn = getattr(contract, attr_name)
        if isinstance(fn, OverloadedMethod):
            fns.extend(_expand_overloaded(fn))
        elif isinstance(fn, (ContractCall, ContractTx)):
            fns.append(fn)
        else:
            raise TypeError(attr_name, fn, item)
    return fns

def _is_view_method(function: ContractCall) -> bool:
    return function.abi.get("stateMutability") == "view"

def _list_view_methods(contract: Contract) -> List[ContractCall]:
    no_overloaded = [function for function in _list_functions(contract)]
    return [function for function in _list_functions(contract) if _is_view_method(function)]

def _expand_overloaded(fn: OverloadedMethod) -> List[ContractCall]:
    expanded = []
    for method in fn.methods.values():
        if isinstance(method, (ContractCall, ContractTx)):
            expanded.append(method)
        else:
            logger.info('we dont yet support %s %s', fn, method)
    assert all(isinstance(e, (ContractCall, ContractTx)) for e in expanded), expanded
    return expanded


def _has_no_args(function: ContractCall) -> bool:
    return not function.abi["inputs"]



SKIP_METHODS = {
    "decimals",
    "eip712Domain",
    "metadata",
    "MAX_UINT",
    "UINT_MAX_VALUE",
    # these numbers are either too big to stuff into the default db or wont scale properly (or both).
    # You can manually do things with these if you need
    "getReserves", 
    "reserve0",
    "reserve1",
    "price0CumulativeLast",
    "price1CumulativeLast",
    "kLast",
    "currentCumulativePrices",
    "reserve0CumulativeLast",
    "reserve1CumulativeLast",
    "lastObservation",
    "DELEGATE_PROTOCOL_SWAP_FEES_SENTINEL",
}

def _exportable_return_value_type(function: ContractCall) -> bool:
    name = function._name.split('.')[1]
    if name in SKIP_METHODS:
        return False
    outputs = function.abi["outputs"]
    if not outputs:
        return False
    if len(outputs) == 1:
        output = outputs[0]
        if 'components' in output and output['internalType'].startswith('struct ') and all(c['name'] for c in output['components']):
            # if we are here the fn returns a single struct
            return True
        if (output_type := output["type"]) in EXPORTABLE_TYPES:
            return True
        if output_type in UNEXPORTABLE_TYPES or output_type.endswith(']'):
            return False
    elif len(outputs) > 1:
        if all(o["type"] in UNEXPORTABLE_TYPES for o in outputs):
            return False
        elif is_tuple_type(outputs): # NOTE lets see if this works --- and all(o["type"] in EXPORTABLE_TYPES for o in outputs):
            return True
        elif is_struct_type(outputs): # NOTE lets see if this works --- and all(o["type"] in EXPORTABLE_TYPES for o in outputs):
            #logger.info("TODO: support multi-return value methods with named return values")
            return True
    logger.info("cant export %s with outputs %s", function, outputs)
    return False

def _safe_views(contract: Contract) -> List[ContractCall]:
    """Returns a list of the view methods on `contract` that are suitable for exporting"""
    return [function for function in _list_view_methods(contract) if _has_no_args(function) and _exportable_return_value_type(function)]

def unpack(metric: AnyContractCallMetric) -> List[AnyContractCallMetric]:
    """
    If `metric` returns multiple values, we can't export it. We need to derive new metrics to represent each field.
    returns a list of exportable metrics derived from input `metric`
    """
    timeseries = _wrap_method(metric, True)
    unpacked = []
    if timeseries.metric._returns_array_type:
        logger.info('unable to export array type: %s', timeseries.metric)
    elif timeseries.metric._returns_tuple_type:
        member: TupleDerivedMetric
        for member in (timeseries.metric[i] for i in range(len(timeseries.metric._outputs))):
            if member._returns_array_type:
                logger.info("unable to export tuple member Contract('%s').%s with abi %s", member.address, member.key, member.abi)
            elif (abi_type := member.abi["type"]) in EXPORTABLE_TYPES:
                unpacked.append(member)
            elif abi_type == "tuple":
                unpacked.extend(unpack(member))
            elif abi_type not in UNEXPORTABLE_TYPES:
                logger.info('unable to export tuple member %s with abi %s', member, member.abi)
    elif timeseries.metric._returns_struct_type:
        outputs = timeseries.metric._outputs
        if len(outputs) == 1:
            outputs = outputs[0]['components']
        assert all(abi['name'] for abi in outputs), outputs
        for abi in outputs:
            struct_key = abi['name']
            derived_metric: StructDerivedMetric = timeseries.metric[struct_key]
            type_str: str = abi["type"]
            if derived_metric._returns_array_type:
                logger.info("unable to export struct member Contract('%s').%s with abi %s", derived_metric.address, derived_metric.key, derived_metric.abi)
            elif type_str in EXPORTABLE_TYPES:
                unpacked.append(derived_metric)
            elif type_str == "tuple":
                unpacked.extend(unpack(derived_metric))
            elif type_str not in UNEXPORTABLE_TYPES and not type_str.endswith("[]"):
                logger.info('unable to export struct member %s return type %s', derived_metric, type_str)
    else:
        unpacked.append(timeseries.metric)
    return unpacked

is_tuple_type = lambda outputs: all(not o["name"] for o in outputs)
is_struct_type = lambda outputs: all(o['name'] for o in outputs)