
import logging
from datetime import datetime, timedelta
from typing import List, Union

from brownie import chain
from brownie.network.contract import _ContractMethod

from generic_exporters.timeseries import _WideTimeSeries, WideTimeSeries
from generic_exporters.processors.exporters.datastores.timeseries._base import TimeSeriesDataStoreBase

from evm_contract_exporter import _exceptions
from evm_contract_exporter._address import ContractCallTimeSeries
from evm_contract_exporter.exporters.metric import ContractMetricExporter
from evm_contract_exporter.metric import ContractCallDerivedMetric, ContractCallMetric
from evm_contract_exporter.scale import Scale


REVERT = -1

logger = logging.getLogger(__name__)

Method = Union[_ContractMethod, ContractCallMetric, ContractCallDerivedMetric]
Scaley = Union[bool, int, Scale]

class ViewMethodExporter(ContractMetricExporter):
    """Used to export `ContractCall` and `ContractTx` methods on a eth-brownie `Contract`"""
    _semaphore_value = 500_000 # effectively doesnt exist at this level # TODO: dev something so we can make this None
    def __init__(
        self, 
        *methods: Method,
        interval: timedelta = timedelta(days=1), 
        buffer: timedelta = timedelta(minutes=5), 
        scale: Scaley = False, 
        datastore: TimeSeriesDataStoreBase = None,
        sync: bool = True,
    ) -> None:
        _validate_scale(scale)
        super().__init__(chain.id, _wrap_methods(methods, scale), interval=interval, datastore=datastore, buffer=buffer, sync=sync)
    
    async def ensure_data(self, ts: datetime) -> None:
        try:
            await super().ensure_data(ts, sync=False)
        except Exception as e:
            if not _exceptions._is_revert(e):
                raise e
            logger.debug("%s reverted with %s %s", self, e.__class__.__name__, e)
            await self.datastore.push(self.metric.key, ts, REVERT, self)

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
