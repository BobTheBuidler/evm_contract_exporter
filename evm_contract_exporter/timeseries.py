
from typing import TYPE_CHECKING, Union, final

import generic_exporters
from generic_exporters.timeseries import _WideTimeSeries

from evm_contract_exporter import types

if TYPE_CHECKING:
    from evm_contract_exporter.metric import _MetricBase, AnyContractCallMetric


class TimeSeries(generic_exporters.TimeSeries):  # type: ignore [misc]
    """
    An object representing the infinite series of values for a particular `Metric` across the time axis. 
    NOTE: Imagine a line chart with a single line that has yet to be drawn.
    """
    metric: "_MetricBase"
    def __init__(self, metric: "_MetricBase", sync: bool = True) -> None:
        super().__init__(metric, sync=sync)
    @property
    def address(self) -> types.address:
        return self.metric.address
    
class ContractCallTimeSeries(TimeSeries):  # type: ignore [misc]
    # TODO maybe just combine this into `TimeSeries`
    """
    An object representing the infinite series of values for a particular `AnyContractCallMetric` across the time axis. 
    NOTE: Imagine a line chart with a single line that has yet to be drawn.
    """
    metric: "AnyContractCallMetric"
    def __repr__(self) -> str:
        metric_repr = repr(self.metric)
        return f"<{self.__class__.__name__} {metric_repr[metric_repr.find('0x'):]}"
    
SingleProcessable = Union["_MetricBase", TimeSeries]

@final
class WideTimeSeries(_WideTimeSeries[SingleProcessable]):
    """
    A collection of `TimeSeries` objects
    NOTE: Imagine a line chart with multiple lines that have yet to be drawn
    """
    def __init__(self, *timeserieses: SingleProcessable, sync: bool = True) -> None:
        from evm_contract_exporter.metric import _MetricBase
        for x in timeserieses:
            if not isinstance(x, (TimeSeries, _MetricBase)):
                raise TypeError(f"`x` must be a `TimeSeries` or a `Metric` object. You passed {x}")
        super().__init__(*(TimeSeries(x) if isinstance(x, _MetricBase) else x for x in timeserieses), sync=sync)
