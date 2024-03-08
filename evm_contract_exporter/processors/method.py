
from datetime import timedelta
from typing import List, Optional, Union

from brownie import chain
from brownie.network.contract import _ContractMethod

from generic_exporters.timeseries import _WideTimeSeries, WideTimeSeries

from evm_contract_exporter.metric import ContractCallDerivedMetric, ContractCallMetric
from evm_contract_exporter.processors._base import _ContractMetricProcessorBase
from evm_contract_exporter.scale import Scale
from evm_contract_exporter.timeseries import ContractCallTimeSeries


Method = Union[_ContractMethod, ContractCallMetric, ContractCallDerivedMetric]
Scaley = Union[bool, int, Scale]

class ViewMethodProcessor(_ContractMetricProcessorBase):
    def __init__(
        self, 
        *methods: Method, 
        interval: timedelta = timedelta(days=1), 
        buffer: Optional[timedelta] = None, 
        scale: Scaley = False, 
        semaphore_value: Optional[int], 
        sync: bool = True,
    ) -> None:
        if buffer:
            raise NotImplementedError('buffer')
        _validate_scale(scale)
        timeseries = _wrap_methods(methods, scale)
        query = timeseries[self.start_timestamp(sync=False), None, interval]
        super().__init__(chain.id, query, semaphore_value=semaphore_value, sync=sync)

def _validate_scale(scale: Scaley) -> None:
    if isinstance(scale, bool):
        pass
    elif not isinstance(scale, int):
        raise TypeError("scale must be an integer")
    elif not str(scale).endswith('00'): # NOTE: we assume tokens with decimal 1 are shit
        raise ValueError("you must provided the scaled decimal value, not the return value from decimals()")
    
def _wrap_methods(methods: List[Method], scale: Scaley) -> Union[ContractCallTimeSeries, _WideTimeSeries[ContractCallTimeSeries]]:
    if len(methods) == 0:
        raise ValueError("you must provide one or more methods")
    if len(methods) == 1:
        return _wrap_method(methods[0], scale)
    return WideTimeSeries(*[_wrap_method(method, scale) for method in methods])

def _wrap_method(method: Union[Method, ContractCallTimeSeries], scale: Scaley) -> ContractCallTimeSeries:
    if isinstance(method, ContractCallTimeSeries):
        return method
    if isinstance(method, (ContractCallMetric, ContractCallDerivedMetric)):
        metric = method
    elif isinstance(method, _ContractMethod):
        metric = ContractCallMetric(method, scale=scale)
    else:
        raise TypeError(method)
    return ContractCallTimeSeries(metric)
