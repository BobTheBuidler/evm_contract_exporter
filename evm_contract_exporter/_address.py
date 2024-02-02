
from typing import Union

from brownie import convert
from generic_exporters import Metric, TimeSeries
from y.contracts import contract_creation_block_async

from evm_contract_exporter import types, utils
from evm_contract_exporter.metric import _ContractCallMetricBase
from evm_contract_exporter.scale import Scale

# NOTE: is this needed? 

class _AddressKeyedMetric(Metric):
    def __init__(self, address: types.address) -> None:
        super().__init__()
        self.address = convert.to_address(address)

class _AddressKeyedTimeSeries(TimeSeries):
    metric: _AddressKeyedMetric
    def __init__(self, metric: _AddressKeyedMetric, sync: bool = True) -> None:
        super().__init__(metric, sync=sync)
    @property
    def address(self) -> types.address:
        return self.metric.address

class ContractCallTimeSeries(_AddressKeyedTimeSeries):
    metric: _ContractCallMetricBase
    def __init__(
        self, 
        metric: _ContractCallMetricBase, 
        *, 
        #scale: Union[bool, int, Scale] = False, 
        sync: bool = True,
    ) -> None:
        super().__init__(metric, sync)
        '''
        self._scale = scale
        try:
            if self._scale and not self.metric._can_scale:
                self._scale = False
        except AttributeError:
            self._scale = False
        '''
    def __repr__(self) -> str:
        metric_repr = repr(self.metric)
        return f"<{self.__class__.__name__} {metric_repr[metric_repr.find('0x'):]}"