
import asyncio
from datetime import datetime
from decimal import Decimal
from functools import cached_property
from typing import TYPE_CHECKING, Any, Optional, Union, overload
from generic_exporters import Constant, Metric
from generic_exporters.metric import _AdditionMetric, _SubtractionMetric, _MathResultMetricBase, _MultiplicationMetric, _TrueDivisionMetric, _FloorDivisionMetric, _PowerMetric

from evm_contract_exporter import types
from evm_contract_exporter._port_to_dank import calc_decimals

if TYPE_CHECKING:
    from evm_contract_exporter.metric import ContractCallMetric, ContractCallDerivedMetric


CallRelated = Union["ContractCallMetric", "ContractCallDerivedMetric"]

class _ContractCallMathResultMetricBase(_MathResultMetricBase):
    """A base class that represents a Metric that is the result of a maths operation performed on two other `ContractCallMetric` objects"""
    metric0: CallRelated
    metric1: Metric
    address: Optional[types.address]
    def __init__(self, metric0: Union[CallRelated, Constant], metric1: Union[CallRelated, Constant]) -> None:
        from evm_contract_exporter.metric import ContractCallMetric, ContractCallDerivedMetric
        ContractMetric = (ContractCallMetric, ContractCallDerivedMetric)
        if isinstance(metric0, ContractMetric) and not isinstance(metric1, ContractMetric):
            self.address = metric0.address
        elif not isinstance(metric0, ContractMetric) and isinstance(metric1, ContractMetric):
            self.address = metric1.address
        elif not isinstance(metric0, ContractMetric) and not isinstance(metric1, ContractMetric):
            self.address = None
        elif isinstance(metric0, ContractMetric) and isinstance(metric1, ContractMetric):
            self.address = metric0.address if metric0.address == metric1.address else None
        super().__init__(metric0, metric1)
    @overload
    def __call__(*args, decimals: int, **kwargs) -> Decimal:...
    @calc_decimals
    def __call__(self, decimals: Optional[int] = None, **kwargs) -> Any:
        """Functions like a `ContractCall.__call__` api. It won't accept args though as its passing the block thru to 2 different calls."""
        return self._do_math(self.metric0(**kwargs), self.metric1(**kwargs))
    def __init_subclass__(cls) -> None:
        cls.__doc__ += "\n\nYou can create and use them as shown below"
        cls.__doc__ += "\n```"
        cls.__doc__ += f"\ncontract.idkWhatThisIs = contract.totalSupply {cls._symbol} contract.lockedSupply"
        cls.__doc__ += "\ncontract.idkWhatThisIs(block_identifier=123, decimals=18)"

        cls.__doc__ += "\n\n>>> 1234"
        cls.__doc__ += "\n```"
        super().__init_subclass__()
    @cached_property
    def key(self) -> str:
        return super().key if self.address is None else f"{super().key}[{self.address}]"
    async def produce(self, timestamp: datetime) -> Decimal:
        return self._do_math(*await asyncio.gather(self.metric0.produce(timestamp, sync=False), self.metric1.produce(timestamp, sync=False)))
    @overload
    async def coroutine(*args, decimals: int, **kwargs) -> Decimal:...
    @calc_decimals
    async def coroutine(self, *args, decimals: Optional[int] = None, **kwargs) -> Any:
        """Functions like a dank_mids patched `ContractCall.coroutine` api without arg support."""
        retval = self._do_math(*await asyncio.gather(self.metric0.coroutine(**kwargs), self.metric1.coroutine(**kwargs)))
        return retval if decimals is None else retval / Decimal(10) ** decimals
    def _calc_decimals(self, retval: int, decimals: Optional[int]):
        return (retval / Decimal(10) ** decimals) if decimals else retval
    


class _ContractCallAdditionMetric(_ContractCallMathResultMetricBase, _AdditionMetric):
    """
    An `_ContractCallAdditionMetric` is a `Metric` that queries two input `Metrics` at any given timestamp, adds their outputs, and returns the sum.
    
    They are created by the library when you add two `ContractCallMetric` objects. You should not need to interact with this class directly.
    """
    
class _ContractCallSubtractionMetric(_ContractCallMathResultMetricBase, _SubtractionMetric):
    """
    A `_ContractCallSubtractionMetric` is a `Metric` that queries two input `Metrics` at any given timestamp, subtracts their outputs, and returns the difference.
    
    They are created by the library when you subtract two `ContractCallMetric` objects. You should not need to interact with this class directly.
    """
    
class _ContractCallMultiplicationMetric(_ContractCallMathResultMetricBase, _MultiplicationMetric):
    """A `_ContractCallMultiplicationMetric` is a `Metric` that queries two input `Metrics` at any given timestamp, multiplies their outputs, and returns the product.
    
    They are created by the library when you multiply two `ContractCallMetric` objects. You should not need to interact with this class directly.
    """
    
class _ContractCallTrueDivisionMetric(_ContractCallMathResultMetricBase, _TrueDivisionMetric):
    """A `_ContractCallTrueDivisionMetric` is a `Metric` that queries two input `Metrics` at any given timestamp, divides their outputs, and returns the true quotient.
    
    They are created by the library when you divide two `ContractCallMetric` objects. You should not need to interact with this class directly.
    """
    
class _ContractCallFloorDivisionMetric(_ContractCallMathResultMetricBase, _FloorDivisionMetric):
    """A `_ContractCallFloorDivisionMetric` is a `Metric` that queries two input `Metrics` at any given timestamp, divides their outputs, and returns the floored quotient.
    
    They are created by the library when you divide two `ContractCallMetric` objects. You should not need to interact with this class directly.
    """
    
class _ContractCallPowerMetric(_ContractCallMathResultMetricBase, _PowerMetric):
    """A `_ContractCallPowerMetric` is a `Metric` that queries two input `Metrics` at any given timestamp, raises the output of the first to the power of the output of the second, and returns the exponentiation.
    
    They are created by the library when you exponentiate two `ContractCallMetric` objects. You should not need to interact with this class directly.
    """

classes = (
    _ContractCallAdditionMetric, 
    _ContractCallSubtractionMetric, 
    _ContractCallMultiplicationMetric,
    _ContractCallTrueDivisionMetric,
    _ContractCallFloorDivisionMetric,
    _ContractCallPowerMetric,
)