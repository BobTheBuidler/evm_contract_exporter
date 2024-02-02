
# TODO:generic + price example
import asyncio
import logging
from datetime import timedelta

from brownie.exceptions import ContractNotFound
from evm_contract_exporter.contract.generic import GenericContractExporter
from evm_contract_exporter.examples import PriceExporter
from evm_contract_exporter.types import address
from y.exceptions import ContractNotVerified


logger = logging.getLogger(__name__)

class GenericContractExporterWithPrice(GenericContractExporter):
    def __init__(self, contract: address, chainid: int, *, interval: timedelta = ..., buffer: timedelta = ...) -> None:
        super().__init__(contract, chainid, interval=interval, buffer=buffer)
        self.price_exporter = PriceExporter(contract, interval=interval, buffer=self.buffer, datastore=self.datastore)
        
    async def _await(self) -> None:
        try:
            await asyncio.gather(*await self.method_exporters, self.price_exporter)
        except ContractNotFound:
            logger.info("%s is not a contract, skipping", self)
        except ContractNotVerified:
            logger.info("%s is not verified, skipping", self)
        except Exception as e:
            logger.exception("%s %s for %s, skipping", e.__class__.__name__, e, self)