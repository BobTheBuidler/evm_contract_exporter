
from typing import List

from brownie import Contract
from brownie.network.contract import ContractCall, ContractTx, OverloadedMethod

from evm_contract_exporter.generic._methods import _call

def safe_views(contract: Contract) -> List[ContractCall]:
    """Returns a list of the view methods on `contract` that are suitable for exporting"""
    return [function for function in list_view_methods(contract) if _call.has_no_args(function) and _call.exportable_return_value_type(function)]

def list_view_methods(contract: Contract) -> List[ContractCall]:
    return [function for function in list_functions(contract) if _call.is_view_method(function)]

def list_functions(contract: Contract) -> List[ContractCall]:
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
            fns.extend(_call.expand_overloaded(fn))
        elif isinstance(fn, (ContractCall, ContractTx)):
            fns.append(fn)
        else:
            raise TypeError(attr_name, fn, item)
    return fns

