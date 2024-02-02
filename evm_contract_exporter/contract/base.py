
import logging
from abc import abstractmethod
from datetime import timedelta

import a_sync

from evm_contract_exporter._exceptions import FixMe
from evm_contract_exporter.datastore import GenericContractTimeSeriesKeyValueStore
from evm_contract_exporter.types import address


logger = logging.getLogger(__name__)

class ContractExporterBase(a_sync.ASyncGenericBase):
    """TODO: maybe refactor out"""
    def __init__(
        self, 
        chainid: int, 
        *, 
        interval: timedelta = timedelta(days=1), 
        buffer: timedelta = timedelta(minutes=5),
        sync: bool = True,
    ) -> None:
        self.chainid = chainid
        self.interval = interval
        self.buffer = buffer
        self.datastore = GenericContractTimeSeriesKeyValueStore(chainid)
        self.sync = sync
    def __await__(self):
        try:
            return self._await().__await__()
        except FixMe as e:
            logger.warning('bob has to fix me: %s', e)
        except AttributeError:
            raise NotImplementedError
    @abstractmethod
    async def _await(self) -> None:
        ...
