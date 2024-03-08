
from typing import Union, final

import generic_exporters

from evm_contract_exporter import types
from evm_contract_exporter.metric import _MetricBase, AnyContractCallMetric


class TimeSeries(generic_exporters.TimeSeries):  # type: ignore [misc]
    metric: _MetricBase
    def __init__(self, metric: _MetricBase, sync: bool = True) -> None:
        super().__init__(metric, sync=sync)
    @property
    def address(self) -> types.address:
        return self.metric.address
    
class ContractCallTimeSeries(TimeSeries):  # type: ignore [misc]
    # TODO maybe just combine this into `TimeSeries`
    metric: "AnyContractCallMetric"
    def __repr__(self) -> str:
        metric_repr = repr(self.metric)
        return f"<{self.__class__.__name__} {metric_repr[metric_repr.find('0x'):]}"
    
SingleProcessable = Union[_MetricBase, TimeSeries]

@final
class WideTimeSeries(generic_exporters.WideTimeSeries):  # type: ignore [misc]
    def __init__(self, *timeserieses: SingleProcessable, sync: bool = True) -> None:
        for x in timeserieses:
            if not isinstance(x, (TimeSeries, _MetricBase)):
                raise TypeError(f"`x` must be a `TimeSeries` or a `Metric` object. You passed {x}")
        super().__init__(*(TimeSeries(x) for x in timeserieses if isinstance(x, _MetricBase)), sync=sync)
