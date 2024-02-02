
import asyncio
import logging
from abc import abstractmethod, abstractproperty
from datetime import datetime
from decimal import Decimal
from functools import cached_property
from typing import Any, Dict, List, Optional, Tuple, Type, Union, overload

import inflection
from async_lru import alru_cache
from brownie.convert.datatypes import ReturnValue
from brownie.network.contract import ContractCall
from datetime import timedelta
from generic_exporters import Metric, TimeSeries
from y import ERC20, get_block_at_timestamp

from evm_contract_exporter import _exceptions, _math, scale, types, utils


logger = logging.getLogger(__name__)

class _ContractCallMetricBase(Metric):
    """A base class for any `Metric` that returns the response from a contract call, or one of its values if multiple are returned"""
    __math_classes__ = _math.classes
    @cached_property
    def _can_scale(self) -> bool:
        """Returns True if the output type is numeric and can be scaled down, False otherwise."""
        return issubclass(self._output_type, int)
    @cached_property
    def _should_scale(self) -> bool:
        """Returns True if we should scale the output of this `_ScaledContractMetricBase`, False if we should not."""
        if isinstance(self._scale, bool):
            return (
                # NOTE: If autoscaling is enabled, and the output type is a numeric type that is typically scaled, we scale.
                True if self._scale is True and self._output_type in [types.int256, types.uint256]
                # NOTE: If scaling is disabled, of course we do not scale.
                else False
            )
        elif isinstance(self._scale, int):
            # NOTE: If the user provides a specific scaling factor, we always honor it. Good luck.
            return True
        # NOTE: Otherwise, wtf scaling value is this?
        raise TypeError(f"{self.__class__.__name__}._scale must be either `bool` or `int`")
    @alru_cache(maxsize=None)
    async def get_scale(self) -> Optional[Decimal]:
        """Returns the scaling factor to use for scaling the outputs of this `_ScaledContractMetricBase`"""
        if self._scale is False:
            raise ValueError(f"{self} does not scale")
        elif self._scale is True:
            return Decimal(await ERC20(self.address, asynchronous=True).scale)
        elif isinstance(self._scale, scale.Scale):
            return self._scale.produce(None)
        return Decimal(self._scale)
    @abstractproperty
    def address(self) -> int:
        """Returns the address of the contract with the `decimals` method we will use to calculate the scale when autoscaling is enabled"""
    @abstractproperty
    def _scale(self) -> int:
        """Returns your subclass implementation's scaling specification for this `_ScaledContractMetricBase`"""
    @abstractproperty
    def _output_type(self) -> Type:
        """Returns the output type returned by the ContractCall"""


class ContractCallMetric(ContractCall, _ContractCallMetricBase):
    """A hybrid between a `ContractCall` and a `Metric`. Will function as you would expect from any `ContractCall` object, but can also be used as an exportable `Metric` in `evm_contract_exporter`"""
    def __init__(self, original_call: ContractCall, *args, scale: Union[bool, int, scale.Scale] = False) -> None:
        super().__init__(original_call._address, original_call.abi, original_call._name, original_call._owner, original_call.natspec)
        Metric.__init__(self)
        self._args = args
        if not isinstance(scale, bool) and not self._can_scale:
            raise ValueError(f"{self} is not scalable. output type: {self._output_type or self._outputs}")
        self._original_call = original_call
        self._cache: Dict[datetime, Tuple[int, asyncio.Task]] = {}
        self.__scale = scale
    def __repr__(self) -> str:
        orig = ContractCall.__repr__(self)
        cut = 1+len(type(self).__name__)
        return orig[:cut] + f" {self.address}" + orig[cut:]
    @property
    def address(self) -> str:
        """Returns the address associated with the `ContractCall` used to init this `ContractCallMetric`. This is the address that will be queried on-chain when computing this `ContractCallMetric`."""
        return self._address
    @property
    def _scale(self) -> Union[bool, int, scale.Scale]:
        """Returns the user's scaling specification for this `ContractCallMetric`"""
        return self.__scale
    @cached_property
    def key(self) -> str:
        return inflection.underscore(self._name.split('.')[1])
    @overload
    def __getitem__(self, key: "slice[datetime, datetime, timedelta]", end: Optional[datetime], interval: timedelta = timedelta(days=1)) -> TimeSeries:
        ...
    @overload
    def __getitem__(self, key: int) -> "TupleDerivedMetric":
        ...
    @overload
    def __getitem__(self, key: str) -> "StructDerivedMetric":
        ...
    def __getitem__(self, key: Union[int, str, "slice[datetime, datetime, timedelta]"]) -> Union[TimeSeries, "TupleDerivedMetric", "StructDerivedMetric"]:
        if isinstance(key, slice):
            return super().__getitem__(key)
        len_outputs = len(self._outputs)
        if isinstance(key, int):
            if not len_outputs > 1:
                raise TypeError(f"`{self.__class__.__name__}[{self._output_type.__name__}]` object is not subscriptable")
            if key >= len_outputs:
                raise IndexError(f"{self} return type does not have a {key}th index")
            return TupleDerivedMetric(self, key)
        elif isinstance(key, str):
            if not key:
                raise ValueError("You passed an empty string. You can't look up a named field without the name. Come on.")
            if len_outputs == 1:
                output = self._outputs[0]
                if not output['internalType'].startswith('struct '):
                    raise TypeError(f"`{self.__class__.__name__}[{self._output_type.__name__}]` object is not subscriptable")
                outputs = output['components']
            else:
                outputs = self._outputs
            for abi in outputs:
                if abi['name'] == key:
                    return StructDerivedMetric(self, abi)
            raise KeyError(f"{self} return type has no key {key}. outputs: {outputs}")
        raise TypeError(key, "must be `int`, `str`, or `slice[datetime, datetime, timedelta]`")
    async def coroutine(self, *args, **kwargs) -> Any:
        """Maintains the async monkey-patching done by dank_mids on the original ContractCall object"""
        retval = await self._original_call.coroutine(*args, **kwargs)
        return self._output_type(retval) if self._should_wrap_output else retval
    async def produce(self, timestamp: datetime) -> Optional[Decimal]:
        if await get_block_at_timestamp(timestamp, sync=False) < await utils.get_deploy_block(self.address):
            logger.debug("%s was not yet deployed at %s", self, timestamp)
            return None
        if self._dependants:
            if timestamp not in self._cache:
                self._cache[timestamp] = [self._dependants, asyncio.create_task(self.__produce(timestamp))]
            result = await self._cache[timestamp][1]
            self._cache[timestamp][0] -= 1
            if self._cache[timestamp][0] <= 0:
                self._cache.pop(timestamp)
            return result
        return await self.__produce(timestamp)
    async def __produce(self, timestamp: datetime) -> Decimal:
        while True:
            try:
                block = await utils.get_block_at_timestamp(timestamp)
                retval = await self.coroutine(*self._args, block_identifier=block)
                if self._should_scale:
                    if isinstance(retval, ReturnValue):
                        logger.warning("attempted to scale %s, debug!  method: %s  should_scale: %s  output_type: %s  outputs: %s", retval, self._original_call, self._should_scale, self._output_type, self._outputs)
                    else:
                        scale = await self.get_scale()
                        retval /= scale
                return retval
            except Exception as e:
                if '429' not in str(e):
                    raise e
                await asyncio.sleep(1)
    @property
    def _outputs(self) -> List[dict]:
        return self.abi['outputs']
    @cached_property
    def _output_type(self) -> Union[Type, Tuple[Type, ...]]:
        """Returns None if there is more than 1 output value for this method"""
        if len(self._outputs) == 1 and 'components' not in self._outputs[0]:
            try:
                return types.lookup(self._outputs[0]['type'])
            except _exceptions.FixMe:
                raise _exceptions.FixMe("cannot export tuple type", self._outputs)
        if self._returns_tuple_type or self._returns_struct_type:
            return tuple(types.lookup(self._outputs[i]["type"]) for i in range(len(self._outputs)))
        raise NotImplementedError(self, self._outputs)
    @cached_property
    def _should_wrap_output(self) -> bool:
        return not isinstance(self._output_type, tuple)
    @cached_property
    def _returns_tuple_type(self) -> bool:
        return len(self._outputs) > 1 and all(not o["name"] for o in self._outputs)
    @cached_property
    def _returns_struct_type(self) -> bool:
        len_outputs = len(self._outputs)
        if len_outputs == 1:
            output = self._outputs[0]
            return 'components' in output and output['internalType'].startswith('struct ') and all(c['name'] for c in output['components'])
        return len_outputs > 1 and all(o['name'] for o in self._outputs)
    


class ContractCallDerivedMetric(_ContractCallMetricBase):
    _returns_tuple_type = _returns_struct_type = False
    def __init__(self, call: ContractCallMetric) -> None:
        super().__init__()
        self._call = call
        self._call._dependants += 1
    def __call__(self, *args, **kwargs):
        return self._extract(self._call(*args, **kwargs))
    async def coroutine(self, *args, **kwargs):
        return self._extract(await self._call.coroutine(*args, **kwargs))
    async def produce(self, timestamp: datetime) -> Decimal:
        call_response = await self._call.produce(timestamp, sync=False)
        value = Decimal(self._extract(call_response)) 
        if self._should_scale:
            value /= await self.get_scale()
        return value
    @cached_property
    def address(self) -> types.address:
        return self._call.address
    @property
    def _scale(self) -> Union[bool, int, scale.Scale]:
        return self._call._scale
    @abstractmethod
    def _extract(self, response_data) -> Any:
        ...


class TupleDerivedMetric(ContractCallDerivedMetric):
    def __init__(self, call: ContractCallMetric, index: int) -> None:
        super().__init__(call)
        self._index = index
    @cached_property
    def key(self) -> str:
        return inflection.underscore(self._call._name.split('.')[1]) + f"[{self._index}]"
    async def produce(self, timestamp: datetime) -> Decimal:
        tup = await self._call.produce(timestamp, sync=False)
        value = Decimal(self._extract(tup))
        if self._should_scale:
            value /= await self.get_scale()
        return value
    @property
    def _output_type(self) -> Type:
        return types.lookup(self._call._outputs[self._index]['type'])
    def _extract(self, response_data: ReturnValue) -> Any:
        return response_data[self._index]


class StructDerivedMetric(ContractCallDerivedMetric):
    def __init__(self, call: ContractCallMetric, abi: dict) -> None:
        super().__init__(call)
        self._abi = abi
        self._struct_key = self._abi['name']
    @cached_property
    def key(self) -> str:
        return inflection.underscore(self._call._name.split('.')[1]) + f".{self._struct_key}"
    @property
    def _output_type(self) -> Type:
        return types.lookup(self._abi['type'])
    def _extract(self, response_data: ReturnValue) -> Any:
        return response_data.dict()[self._struct_key]
