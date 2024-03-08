
from datetime import timedelta
from typing import Optional

from brownie import chain

from evm_contract_exporter.datastore import GenericContractTimeSeriesKeyValueStore
from evm_contract_exporter.exporters.metric import ContractMetricExporter
from evm_contract_exporter.processors.method import Method, Scaley, _validate_scale, _wrap_methods


class ViewMethodExporter(ContractMetricExporter):
    """Used to export `ContractCall` and `ContractTx` methods on a eth-brownie `Contract`"""
    def __init__(
        self, 
        *methods: Method,
        interval: timedelta = timedelta(days=1), 
        buffer: Optional[timedelta] = None, 
        scale: Scaley = False,
        datastore: Optional[GenericContractTimeSeriesKeyValueStore] = None,
        semaphore_value: Optional[int] = None,
        sync: bool = True,
    ) -> None:
        _validate_scale(scale)
        super().__init__(
            chainid=chain.id, 
            timeseries=_wrap_methods(methods, scale), 
            interval=interval, 
            buffer=buffer, 
            datastore=datastore, 
            semaphore_value=semaphore_value, 
            sync=sync,
        )