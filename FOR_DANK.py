
from typing import TypeVar, Protocol, Awaitable, Coroutine, Generic
from typing_extensions import Concatenate, ParamSpec
_P = ParamSpec("_P")
_T = TypeVar("_T") #, bound=(str, int, bytes, tuple, ReturnValue))
Concatenate[bool, _P]


class _ContractCall(Protocol[_P, _T]):
    """
    This is a mypy helper that represents a brownie.network.contract.ContractCall object without behaving like one.
    When you see this used in the code, it's for type hinting purposes only. In production, you will have a ContractCall object.
    """
    @overload
    def __call__(self, *args: _P.args, decimals: int, **kwargs: _P.kwargs) -> Decimal:...
    @overload
    def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _T:...
    @overload
    async def coroutine(self, *args: _P.args, decimals: int, **kwargs: _P.kwargs) -> Decimal:...
    @overload
    async def coroutine(self, *args: _P.args, **kwargs: _P.kwargs) -> _T:...
    

class VaultV1(Contract):
    decimals: _ContractCall[[], types.uint16]
    pricePerShare: _ContractCall[[], types.uint256]
    async def __init__(self):
        abcd = await self.pricePerShare.coroutine()
    

@calc_decimals
def tett(*args, **kwargs) -> Any:
    ...

asdasda = tett()