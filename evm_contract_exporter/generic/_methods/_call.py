
import logging
from typing import List

from brownie.network.contract import ContractCall, ContractTx, OverloadedMethod

from evm_contract_exporter import types
from evm_contract_exporter.generic._methods import _abi, _skip

logger = logging.getLogger(__name__)


def is_view_method(function: ContractCall) -> bool:
    return function.abi.get("stateMutability") == "view"

def has_no_args(function: ContractCall) -> bool:
    return not function.abi["inputs"]

def exportable_return_value_type(function: ContractCall) -> bool:
    name = function._name.split('.')[1]
    if name in _skip.SKIP_METHODS:
        return False
    outputs = function.abi["outputs"]
    if not outputs:
        return False
    if len(outputs) == 1:
        output = outputs[0]
        if 'components' in output and output['internalType'].startswith('struct ') and all(c['name'] for c in output['components']):
            # if we are here the fn returns a single struct
            return True
        if (output_type := output["type"]) in types.EXPORTABLE_TYPES:
            return True
        if output_type in types.UNEXPORTABLE_TYPES or output_type.endswith(']'):
            return False
    elif len(outputs) > 1:
        if all(o["type"] in types.UNEXPORTABLE_TYPES for o in outputs):
            return False
        elif _abi.is_tuple_type(outputs): # NOTE lets see if this works --- and all(o["type"] in EXPORTABLE_TYPES for o in outputs):
            return True
        elif _abi.is_struct_type(outputs): # NOTE lets see if this works --- and all(o["type"] in EXPORTABLE_TYPES for o in outputs):
            #logger.info("TODO: support multi-return value methods with named return values")
            return True
    logger.info("cant export %s with outputs %s", function, outputs)
    return False

def expand_overloaded(fn: OverloadedMethod) -> List[ContractCall]:
    expanded = []
    for method in fn.methods.values():
        if isinstance(method, (ContractCall, ContractTx)):
            expanded.append(method)
        else:
            logger.info('we dont yet support %s %s', fn, method)
    assert all(isinstance(e, (ContractCall, ContractTx)) for e in expanded), expanded
    return expanded