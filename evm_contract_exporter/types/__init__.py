
from functools import lru_cache
from typing import List, Type

from evm_contract_exporter import _exceptions
from evm_contract_exporter.types.int import *
from evm_contract_exporter.types.uint import *


class address(str):
    ...

class _bytes(bytes):
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({super().__repr__()})"

class bytes1(_bytes):
    ...

class bytes4(_bytes):
    ...
    
class bytes32(_bytes):
    ...

EXPORTABLE_TYPES = {
    "bool": bool,
    "int8": int8,
    "int16": int16,
    "int24": int24,
    "int32": int32,
    "int48": int48,
    "int64": int64,
    "int96": int96,
    "int104": int104,
    "int112": int112,
    "int128": int128,
    "int192": int192,
    "int256": int256,
    "uint8": uint8,
    "uint16": uint16,
    "uint24": uint24,
    "uint32": uint32,
    "uint48": uint48,
    "uint64": uint64,
    "uint96": uint96,
    "uint104": uint104,
    "uint112": uint112,
    "uint128": uint128,
    "uint192": uint192,
    "uint256": uint256,
}

UNEXPORTABLE_TYPES = {
    "string": str,
    "bytes": bytes,
    "bytes1": bytes1,
    "bytes4": bytes4,
    "bytes32": bytes32,
    "address": address,
}

@lru_cache(maxsize=None)
def lookup(evm_type: str) -> Type:
    if not isinstance(evm_type, str):
        raise TypeError(f"`type` must be a string. You passed {evm_type}.")
    if is_array := evm_type.endswith('[]'):
        evm_type = evm_type[:-2]
    if not (py_type := EXPORTABLE_TYPES.get(evm_type) or UNEXPORTABLE_TYPES.get(evm_type)):
        raise _exceptions.FixMe(evm_type, "This just needs to be added to `evm_contract_exporter/types/__init__.py`")
    return List[py_type] if is_array else py_type
