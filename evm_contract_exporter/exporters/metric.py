
import logging
from datetime import timedelta
from typing import Optional, Union

from generic_exporters import QueryPlan

from evm_contract_exporter.timeseries import TimeSeries, WideTimeSeries
from evm_contract_exporter.datastore import GenericContractTimeSeriesKeyValueStore
from evm_contract_exporter.exporters._base import _ContractMetricExporterBase


logger = logging.getLogger(__name__)

class ContractMetricExporter(_ContractMetricExporterBase):
    """Use this class to export the history of one or more `Metric` objects to a `datastore` of your choice."""
    def __init__(
        self,
        chainid: int,
        timeseries: Union[TimeSeries, WideTimeSeries],
        *, 
        interval: timedelta = timedelta(days=1), 
        buffer: Optional[timedelta] = None,
        datastore: Optional[GenericContractTimeSeriesKeyValueStore] = None,
        semaphore_value: Optional[int] = None,
        sync: bool = True,
    ) -> None:
        if buffer:
            raise NotImplementedError('buffer')
        query: QueryPlan = timeseries[self.start_timestamp(sync=False):None:interval]
        super().__init__(chainid, query, datastore=datastore, semaphore_value=semaphore_value, sync=sync)
    