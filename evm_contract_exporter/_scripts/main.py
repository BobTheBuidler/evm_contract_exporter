
import argparse
import asyncio
import logging
import os
import re
from datetime import timedelta
from typing import Dict

import brownie
from tqdm.asyncio import tqdm_asyncio


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser(
    description="Runs the EVM Contract Exporter until stopped",
)

parser.add_argument(
    '--contract',
    type=str,
    help='The address of a contract to export. You can pass multiple, ie. `--contract 0x123 0x234 0x345`',
    required=True,
    nargs='+',
)
parser.add_argument(
    '--network', 
    type=str,
    help='The brownie network identifier for the rpc you wish to use. default: mainnet',
    default='mainnet', 
)
parser.add_argument(
    '--interval', 
    type=str,
    help='The time interval between datapoints. default: 1d',
    default='1d', 
)
parser.add_argument(
    '--daemon', 
    type=bool,
    help='TODO: If True, starts a daemon process instead of running in your terminal. Not currently supported.',
    default=False, 
)
parser.add_argument(
    '--grafana-port',
    type=int,
    help='The port that will be used by grafana',
    default=3000,
)
parser.add_argument(
    '--renderer-port',
    type=int,
    help='The port that will be used by grafana',
    default=8091,
)

args = parser.parse_args()

os.environ['GF_PORT'] = str(args.grafana_port)
os.environ['RENDERER_PORT'] = str(args.renderer_port)

# TODO: run forever arg
def main():
    from evm_contract_exporter._docker import docker_compose
    asyncio.get_event_loop().run_until_complete(docker_compose.ensure_containers(export)())

async def export():
    from evm_contract_exporter import GenericContractExporter
    from evm_contract_exporter.types import address
    tasks: Dict[address, asyncio.Task] = {}
    # TODO: define multi-contract Exporter object
    for contract in args.contract:
        tasks[contract] = GenericContractExporter(contract, interval=_parse_timedelta(args.interval)).task
    await tqdm_asyncio.gather(*tasks.values())

def _parse_timedelta(value: str) -> timedelta:
    regex = re.compile(r'(\d+)([dhms]?)')
    result = regex.findall(value)

    days, hours, minutes, seconds = 0, 0, 0, 0

    for val, unit in result:
        val = int(val)
        if unit == 'd':
            days = val
        elif unit == 'h':
            hours = val
        elif unit == 'm':
            minutes = val
        elif unit == 's':
            seconds = val

    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

if __name__ == "__main__":
    os.environ['BROWNIE_NETWORK_ID'] = args.network
    brownie.project.run(__file__)
