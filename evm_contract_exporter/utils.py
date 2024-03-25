
import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, List, NoReturn

import a_sync
import dank_mids
import y
from async_lru import alru_cache
from brownie.network.contract import Contract, ContractCall

from evm_contract_exporter import types

if TYPE_CHECKING:
    from evm_contract_exporter.exporters.method import Scaley

BLOCK_AT_TIMESTAMP_CONCURRENCY = 500
DEPLOY_BLOCK_CONCURRENCY = 100

_deploy_block_queue: a_sync.Queue[types.address] = a_sync.Queue()
_block_timestamp_semaphore = a_sync.PrioritySemaphore(BLOCK_AT_TIMESTAMP_CONCURRENCY, name="block for timestamp semaphore")

async def get_block_at_timestamp(timestamp: datetime) -> int:
    """Returns the number of the last block minted before the exact moment of `timestamp`"""
    async with _block_timestamp_semaphore[0 - timestamp.timestamp()]:  # NOTE: We invert the priority to go high-to-low so we can get more recent data more quickly
        return await y.get_block_at_timestamp(timestamp)

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

@alru_cache(maxsize=1)
async def start_deploy_block_workers() -> List["asyncio.Task[NoReturn]"]:
    return [asyncio.create_task(_deploy_block_worker()) for _ in range(DEPLOY_BLOCK_CONCURRENCY)]

async def _deploy_block_worker() -> NoReturn:
    while True:
        contract_address = await _deploy_block_queue.get()
        await y.contract_creation_block_async(contract_address)
