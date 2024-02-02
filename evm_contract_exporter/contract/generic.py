

import asyncio
import logging
from datetime import timedelta
from functools import cached_property
from typing import List, Optional

from async_property import async_cached_property
from brownie import chain, convert
from brownie.exceptions import ContractNotFound
from brownie.network.contract import ContractCall, ContractTx, OverloadedMethod
from y import Contract, ContractNotVerified
from y.datatypes import Address

from evm_contract_exporter.contract import ContractExporterBase
from evm_contract_exporter.exporters.method import ViewMethodExporter
from evm_contract_exporter.types import EXPORTABLE_TYPES, UNEXPORTABLE_TYPES, address


logger = logging.getLogger(__name__)

class GenericContractExporter(ContractExporterBase):
    """
    This exporter will export a full history of all of the contract's view methods which return a single numeric result.
    It will also export historical price data.
    """
    def __init__(
        self, 
        contract: Address, 
        *, 
        interval: timedelta = timedelta(days=1), 
        buffer: timedelta = timedelta(minutes=5),
        sync: bool = True
    ) -> None:
        super().__init__(chain.id, interval=interval, buffer=buffer, sync=sync)
        self.address = convert.to_address(contract)
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} contract={self.address} interval={self.interval}>"
    @cached_property
    def task(self) -> asyncio.Task:
        return asyncio.Task(self._await())
    @async_cached_property
    async def method_exporter(self) -> Optional[ViewMethodExporter]:
        from evm_contract_exporter.exporters.method import _wrap_method
        contract = await Contract.coroutine(self.address)
        data = []
        for view_method in _safe_views(contract):
            timeseries = _wrap_method(view_method, True)
            if timeseries.metric._returns_tuple_type:
                derived_metrics = [timeseries.metric[i] for i in range(len(timeseries.metric._outputs))]
                data.extend(derived_metrics)
            elif timeseries.metric._returns_struct_type:
                outputs = timeseries.metric._outputs
                if len(outputs) == 1:
                    outputs = outputs[0]['components']
                assert all(abi['name'] for abi in outputs), outputs
                for abi in outputs:
                    struct_key = abi['name']
                    derived_metric = timeseries.metric[struct_key]
                    data.append(derived_metric)
            else:
                data.append(timeseries)
        if data:
            return ViewMethodExporter(*data, interval=self.interval, buffer=self.buffer, datastore=self.datastore, sync=self.sync)
    async def _await(self) -> None:
        try:
            if method_exporter := await self.method_exporter:
                await method_exporter
        except ContractNotFound:
            logger.error("%s is not a contract, skipping", self)
        except ContractNotVerified:
            logger.error("%s is not verified, skipping", self)
        except Exception as e:
            logger.exception("%s %s for %s, skipping", e.__class__.__name__, e, self)
    
    @classmethod
    def create_export_task(
        cls, 
        contract: address,
        *, 
        interval: timedelta = timedelta(days=1), 
        buffer: timedelta = timedelta(minutes=5),
    ) -> asyncio.Task:
        return cls(contract, interval=interval, buffer=buffer).task

def _list_functions(contract: Contract) -> List[ContractCall]:
    fns = []
    for item in contract.abi:
        if item["type"] != "function":
            continue
        if fn := getattr(contract, item["name"]):
            if isinstance(fn, OverloadedMethod):
                fns.extend(_expand_overloaded(fn))
            elif isinstance(fn, (ContractCall, ContractTx)):
                fns.append(fn)
            else:
                raise TypeError(fn)
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
        elif is_tuple_type(outputs) and all(o["type"] in EXPORTABLE_TYPES for o in outputs):
            return True
        elif is_struct_type(outputs) and all(o["type"] in EXPORTABLE_TYPES for o in outputs):
            #logger.info("TODO: support multi-return value methods with named return values")
            return True
    logger.info("cant export %s with outputs %s", function, outputs)
    return False

def _safe_views(contract: Contract) -> List[ContractCall]:
    """Returns a list of the view methods on `contract` that are suitable for exporting"""
    return [function for function in _list_view_methods(contract) if _has_no_args(function) and _exportable_return_value_type(function)]


is_tuple_type = lambda outputs: all(not o["name"] for o in outputs)
is_struct_type = lambda outputs: all(o['name'] for o in outputs)