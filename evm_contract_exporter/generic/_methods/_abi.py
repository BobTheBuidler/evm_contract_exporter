

from typing import Callable, List, TypedDict

class _MethodABI(TypedDict, total=True):
    name: str
    internalType: str
    type: str

class MethodABI(_MethodABI, total=False):
    ...

is_tuple_type: Callable[[List[MethodABI]], bool] = lambda outputs: all(not o["name"] for o in outputs)
is_struct_type: Callable[[List[MethodABI]], bool] = lambda outputs: all(o['name'] for o in outputs)