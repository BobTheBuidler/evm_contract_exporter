
import asyncio
import logging
from abc import abstractmethod, abstractproperty
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import cached_property
from typing import Any, Dict, List, Optional, Tuple, Type, Union, overload

import generic_exporters
import inflection
from async_lru import alru_cache
from brownie import convert
from brownie.convert.datatypes import ReturnValue
from brownie.network.contract import ContractCall
from datetime import timedelta
from y import ERC20, contract_creation_block_async, get_block_at_timestamp

from evm_contract_exporter import _exceptions, _math, scale, types
from evm_contract_exporter.timeseries import TimeSeries


TUPLE_TYPE = tuple
ARRAY_TYPE = list

logger = logging.getLogger(__name__)


# NOTE: is this needed? 
class _MetricBase(generic_exporters.Metric):
    """This base class is a `generic_exporters.Metric` object that relates to a specific on-chain wallet `address`"""
    @abstractproperty
    def address(self) -> types.address:
        ...

class Metric(_MetricBase):
    """This class is a `generic_exporters.Metric` object that relates to a specific on-chain wallet `address`"""
    def __init__(self, address: types.address) -> None:
        super().__init__()
        self.__address = types.address(convert.to_address(address))
    @property
    def address(self) -> types.address:
        return self.__address

class _ContractCallMetricBase(_MetricBase):
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
        elif isinstance(self._scale, (int, scale.Scale)):
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
            return await self._scale.produce(None)  # type: ignore [arg-type]
        return Decimal(self._scale)
    @abstractproperty
    def address(self) -> types.address:
        """Returns the address of the contract with the `decimals` method we will use to calculate the scale when autoscaling is enabled"""
    @abstractproperty
    def _scale(self) -> Union[bool, int, scale.Scale]:
        """Returns your subclass implementation's scaling specification for this `_ScaledContractMetricBase`"""
    @abstractproperty
    def _output_type(self) -> Type:
        """Returns the output type returned by the ContractCall"""


class ContractCallMetric(ContractCall, _ContractCallMetricBase):
    """A hybrid between a `ContractCall` and a `Metric`. Will function as you would expect from any `ContractCall` object, but can also be used as an exportable `Metric` in `evm_contract_exporter`"""
    def __init__(self, original_call: ContractCall, *args, scale: Union[bool, int, scale.Scale] = False, key: str = '') -> None:
        super().__init__(original_call._address, original_call.abi, original_call._name, original_call._owner, original_call.natspec)
        _MetricBase.__init__(self)
        if not isinstance(original_call, ContractCall):
            raise TypeError(f'`original_call` must be `ContractCall`. You passed {original_call}')
        self._original_call = original_call
        self._args = args
        if key and not isinstance(key, str):
            raise TypeError(f'`key` must be a string. You passed {key}')
        self._key = key
        if not isinstance(scale, bool) and not self._can_scale:
            raise ValueError(f"{self} is not scalable. output type: {self._output_type or self._outputs}")
        self._cache: Dict[datetime, Tuple[int, asyncio.Task]] = {}
        self.__scale = scale
    def __repr__(self) -> str:
        orig = ContractCall.__repr__(self)
        cut = 1+len(type(self).__name__)
        return orig[:cut] + f" {self.address}" + orig[cut:]
    @property
    def address(self) -> types.address:
        """Returns the address associated with the `ContractCall` used to init this `ContractCallMetric`. This is the address that will be queried on-chain when computing this `ContractCallMetric`."""
        return self._address
    @property
    def _scale(self) -> Union[bool, int, scale.Scale]:
        """Returns the user's scaling specification for this `ContractCallMetric`"""
        return self.__scale
    @cached_property
    def key(self) -> str:
        return self._key or inflection.underscore(self._name.split('.')[1])
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
        if await get_block_at_timestamp(timestamp, sync=False) < await contract_creation_block_async(self.address):
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
                block = await get_block_at_timestamp(timestamp)
                retval = await self.coroutine(*self._args, block_identifier=block)
                if self._should_scale:
                    if isinstance(retval, ReturnValue):
                        logger.warning("attempted to scale %s, debug!  method: %s  should_scale: %s  output_type: %s  outputs: %s", retval, self._original_call, self._should_scale, self._output_type, self._outputs)
                    else:
                        retval /= await self.get_scale()
                # Force the db to accept booleans. Sqlite accepts them fine but postgres needs them wrapped.
                return Decimal(retval) if self._output_type is bool else retval
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
            try:
                return tuple(types.lookup(self._outputs[i]["type"]) for i in range(len(self._outputs)))
            except _exceptions.FixMe:
                # TODO: do this better
                return tuple((...,))
        if self._returns_array_of_structs:
            # TODO: do this better
            return list((...,))
        raise NotImplementedError(self, self._outputs)
    @cached_property
    def _should_wrap_output(self) -> bool:
        return not isinstance(self._output_type, (TUPLE_TYPE, ARRAY_TYPE))
    @cached_property
    def _returns_array_type(self) -> bool:
        return len(self._outputs) == 1 and self._outputs[0]["type"].endswith("[]")
    @cached_property
    def _returns_tuple_type(self) -> bool:
        return len(self._outputs) > 1 and all(not o["name"] for o in self._outputs)
    @cached_property
    def _returns_struct_type(self) -> bool:
        len_outputs = len(self._outputs)
        if len_outputs == 1:
            output = self._outputs[0]
            if 'internalType' in output:
                internal_type: str = output['internalType']
                return all([
                    internal_type.startswith('struct '),
                    "[]" not in internal_type,
                    components := output.get('components', []),
                    all(c['name'] for c in components),
                ])
        return len_outputs > 1 and all(o['name'] for o in self._outputs)
    @cached_property
    def _returns_array_of_structs(self) -> bool:
        output = self._outputs[0]
        if 'internalType' not in output:
            return False
        return all([
            output.get('internalType', '').startswith('struct '),
            components := output.get('components', []),
            all(c['name'] for c in components),
        ])

import a_sync
a_sync.ProcessingQueue


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
        try:
            value = Decimal(self._extract(call_response)) 
        except (InvalidOperation, ValueError) as e:
            if hasattr(call_response, "to_dict"):
                raise Exception(e, call_response.to_dict(), self, self._output_type)
            raise e.__class__(e, self._extract(call_response), call_response, self, self.abi)
        if self._should_scale:
            value /= await self.get_scale()
        return value
    @cached_property
    def address(self) -> types.address:
        return self._call.address
    @cached_property
    def _returns_array_type(self) -> bool:
        return self.abi['type'].endswith('[]')
    @cached_property
    def _returns_struct_type(self) -> bool:
        if self._returns_array_type:
            return False
        if 'internalType' in self.abi:
            return all([
                self.abi['type'] != "tuple",
                self.abi['internalType'].startswith('struct '),
                components := self.abi.get('components', []),
                all(c['name'] for c in components),
            ])
        return len(self.abi) > 1 and all(o['name'] for o in self._outputs)
    @property
    def _output_type(self) -> Type:
        if self._returns_array_type:
            return list
        try:
            return types.lookup(self.abi['type'])
        except _exceptions.FixMe:
            raise _exceptions.FixMe(f'cannot export {self.__class__.__name__} with tuple return type', self.abi)
    @property
    def _scale(self) -> Union[bool, int, scale.Scale]:
        return self._call._scale
    @abstractproperty
    def abi(self) -> dict:...
    @abstractmethod
    def _extract(self, response_data) -> Any:...
    @property
    def _outputs(self) -> List[dict]:
        try:
            return self.abi['components']
        except KeyError as e:
            raise KeyError(str(e), self.abi) from None


class TupleDerivedMetric(ContractCallDerivedMetric):
    """
    A `Metric` derived from a `ContractCallMetric` with a tuple response type. You should not init these manually.
    Usage Example:
    ```
    contract = Contract('0x123...')
    methodWithTupleResponse = ContractCallMetric(contract.methodWithTupleResponse)
    derived = methodWithTupleResponse[0]
    
    >>> isinstance(derived, TupleDerivedMetric)
    True
    ```
    """
    def __init__(self, call: ContractCallMetric, index: int) -> None:
        super().__init__(call)
        self._index = index
    @cached_property
    def key(self) -> str:
        return inflection.underscore(self._call._name.split('.')[1]) + f"[{self._index}]"
    @property
    def abi(self) -> dict:
        return self._call._outputs[self._index]
    def _extract(self, response_data: ReturnValue) -> Any:
        return response_data[self._index]


class StructDerivedMetric(ContractCallDerivedMetric):
    """
    A `Metric` derived from a `ContractCallMetric` with a struct response type. You should not init these manually.
    Usage Example:
    ```
    contract = Contract('0x123...')
    methodWithStructResponse = ContractCallMetric(contract.methodWithStructResponse)
    derived = methodWithStructResponse[struct_key]
    
    >>> isinstance(derived, StructDerivedMetric)
    True
    ```
    """
    def __init__(self, call: ContractCallMetric, abi: dict) -> None:
        super().__init__(call)
        self._abi = abi
        self._struct_key = self._abi['name']
    @property
    def abi(self) -> dict:
        return self._abi
    @cached_property
    def key(self) -> str:
        return inflection.underscore(self._call._name.split('.')[1]) + f".{inflection.underscore(self._struct_key)}"
    def _extract(self, response_data: ReturnValue) -> Any:
        try:
            return response_data.dict()[self._struct_key]
        except KeyError as e:
            if response_data.dict() == {} and response_data:
                raise ValueError(f"`response.dict()` is empty but response for {self._call} exists.\nabi: {self._call._outputs}\nresponse: {response_data}")
            # reraise KeyError with some extra info
            raise KeyError(str(e), response_data.dict(), response_data) from e


AnyContractCallMetric = Union[ContractCallMetric, StructDerivedMetric, TupleDerivedMetric]
