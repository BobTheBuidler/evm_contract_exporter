
# NOTE: The stuff in this file probably is better suited in dank's brownie patch. TODO: move there eventually

import asyncio
from decimal import Decimal
from functools import wraps
from typing import Any, Awaitable, Callable, Coroutine, Protocol, TypeVar, Union, overload

from typing_extensions import ParamSpec


_P = ParamSpec("_P")
_T = TypeVar("_T")

@overload
def calc_decimals(fn: Callable[_P, Awaitable[_T]]) -> "AsyncDecimalsWrappedCallable[_P, _T]":...
@overload
def calc_decimals(fn: Callable[_P, _T]) -> "DecimalsWrappedCallable[_P, _T]":...
@overload
def calc_decimals(fn: Callable[_P, Awaitable[_T]]) -> "AsyncDecimalsWrappedCallable[_P, _T]":...
def calc_decimals(fn: Union[Callable[_P, Coroutine[Any, Any, _T]], Callable[_P, _T]]) -> Callable:
    if asyncio.iscoroutinefunction(fn):
        @wraps(fn)
        async def decimals_wrap(*args, **kwargs) -> _T:
            if decimals := kwargs.pop('decimals', None):
                return await fn(*args, **kwargs) / Decimal(10) ** decimals
            return await fn(*args, **kwargs)
    else:
        @wraps(fn)
        def decimals_wrap(*args, **kwargs) -> _T:
            if decimals := kwargs.get('decimals'):
                return fn(*args, **kwargs) / Decimal(10) ** decimals
            return fn(*args, **kwargs)
    return decimals_wrap


class DecimalsWrappedCallable(Protocol[_P, _T]):
    @overload
    def __call__(self, *args: _P.args, decimals: int, **kwargs: _P.kwargs) -> Decimal:...
    @overload
    def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _T:...

class AsyncDecimalsWrappedCallable(Protocol[_P, _T]):
    @overload
    async def __call__(self, *args: _P.args, decimals: int, **kwargs: _P.kwargs) -> Decimal:...
    @overload
    async def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _T:...
