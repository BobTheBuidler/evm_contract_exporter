
from datetime import datetime
from typing import TYPE_CHECKING

import a_sync
import dank_mids
import y
from brownie.network.contract import Contract, ContractCall

from evm_contract_exporter import types

if TYPE_CHECKING:
    from evm_contract_exporter.exporters.method import Scaley


_block_timestamp_semaphore = a_sync.PrioritySemaphore(500, name="block for timestamp semaphore")

async def get_block_at_timestamp(timestamp: datetime) -> int:
    """Returns the number of the last block minted before the exact moment of `timestamp`"""
    async with _block_timestamp_semaphore[0 - timestamp.timestamp()]:  # NOTE: We invert the priority to go high-to-low so we can get more recent data more quickly
        return await y.get_block_at_timestamp(timestamp)

@a_sync.Semaphore(100, "deploy block semaphore")
async def get_deploy_block(contract: types.address) -> int:
    """return the deploy block of `contract`"""
    return await y.contract_creation_block_async(contract)

def wrap_contract(contract: Contract, scale: "Scaley" = True) -> y.Contract:
    """Converts all `ContractCall` objects in `contract.__dict__` to `ContractCallMetric` objects with more functionality"""
    from evm_contract_exporter.metric import ContractCallMetric
    contract = dank_mids.patch_contract(contract)
    for k, v in contract.__dict__.items():
        if isinstance(v, ContractCall):
            # we cant use setattr here because brownie raises some error
            # lets hack our way around that right quick
            object.__setattr__(contract, k, ContractCallMetric(v, scale=scale))
    return contract
