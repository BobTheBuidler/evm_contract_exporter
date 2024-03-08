
import logging
from datetime import timedelta
from typing import List, Optional, Union

from brownie import chain
from brownie.network.contract import _ContractMethod

from generic_exporters.timeseries import _WideTimeSeries, WideTimeSeries

from evm_contract_exporter.datastore import GenericContractTimeSeriesKeyValueStore
from evm_contract_exporter.exporters.metric import ContractMetricExporter
from evm_contract_exporter.metric import ContractCallDerivedMetric, ContractCallMetric
from evm_contract_exporter.scale import Scale
from evm_contract_exporter.timeseries import ContractCallTimeSeries

logger = logging.getLogger(__name__)

Method = Union[_ContractMethod, ContractCallMetric, ContractCallDerivedMetric]
Scaley = Union[bool, int, Scale]

class ViewMethodExporter(ContractMetricExporter):
    """Used to export `ContractCall` and `ContractTx` methods on a eth-brownie `Contract`"""
    def __init__(
        self, 
        *methods: Method,
        interval: timedelta = timedelta(days=1), 
        buffer: timedelta = timedelta(minutes=5), 
        scale: Scaley = False,
        datastore: Optional[GenericContractTimeSeriesKeyValueStore] = None,
        semaphore_value: Optional[int] = None,
        sync: bool = True,
    ) -> None:
        _validate_scale(scale)
        super().__init__(chain.id, _wrap_methods(methods, scale), interval=interval, buffer=buffer, datastore=datastore, semaphore_value=semaphore_value, sync=sync)

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
