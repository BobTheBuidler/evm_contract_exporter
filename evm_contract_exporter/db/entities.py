
import errno
import logging
from datetime import datetime
from decimal import Decimal
from os import mkdir, path

from pony.orm import Database, LongStr, ObjectNotFound, Optional, PrimaryKey, Required, Set

from evm_contract_exporter.db.common import db_session, write_threads


logger = logging.getLogger(__name__)

db = Database()

class Address(db.Entity):
    chainid = Required(int)
    address = Required(str)
    PrimaryKey(chainid, address)

    original_funding_source = Optional("Address", lazy=True)
    wallet_notes = Optional(LongStr, lazy=True)

    wallets_funded = Set("Address")
    contracts_deployed = Set("Contract")
    time_series_kv_data = Set("ContractDataTimeSeriesKV")

    @classmethod
    @db_session
    def entity_exists(cls, chainid: int, address: address) -> bool:
        try:
            cls[chainid, address]
            logger.debug('%s exists in db for (%s, %s)', cls.__name__, chainid, address)
            return True
        except ObjectNotFound:
            logger.debug('%s does not exist in db for (%s, %s)', cls.__name__, chainid, address)
            return False
    
    @classmethod
    @db_session
    def insert_entity(cls, *args, **kwargs) -> None: #chainid: int, address: address, name: str, symbol: str, decimals: int) -> None:
        entity = cls(*args, **kwargs)
        if isinstance(entity, Token):
            logger.debug("New token %s found: %s %s", kwargs['symbol'], entity, kwargs['name'])
        else:
            logger.debug("inserted %s to db", entity)
        print(entity)


class Contract(Address):
    deployer = Optional(Address)
    deploy_block = Optional(int, lazy=True)
    deploy_timestamp = Optional(datetime, lazy=True)
    contract_notes = Optional(LongStr, lazy=True)
    is_verified = Required(bool, default=False, index=True, lazy=True)
    last_checked_verified = Optional(datetime, index=True, lazy=True)

    @classmethod
    async def set_non_verified(cls, chainid: int, address: str) -> None:
        await write_threads.run(cls._set_non_verified, chainid, address)

    @classmethod
    @db_session
    def _set_non_verified(cls, chainid: int, address: str) -> None:
        entity = cls[chainid, address]
        entity.is_non_verified = True
        entity.last_checked_verified = datetime.utcnow()


class Token(Contract):
    name = Required(str, lazy=True)
    symbol = Required(str, index=True, lazy=True)
    token_notes = Optional(LongStr, lazy=True)


class ERC20(Token):
    decimals = Required(int)


class ContractDataTimeSeriesKV(db.Entity):
    address = Required(Address, reverse="time_series_kv_data")
    metric = Required(str)
    timestamp = Required(datetime)
    PrimaryKey(address, metric, timestamp)

    blockno = Required(int)
    value = Required(Decimal)

# TODO: make configurable
def _ensure_default_storage_path_exists() -> None:
    try:
        lib_storage_dir = f"{path.expanduser( '~' )}/.evm_contract_exporter"
        mkdir(lib_storage_dir)
        #mkdir(f"{lib_storage_dir}/grafana_data")
        #mkdir(f"{lib_storage_dir}/grafana_provisioning")
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

# TODO: make configurable
_ensure_default_storage_path_exists()
db.bind(
    provider = "sqlite",
    filename = f"{path.expanduser( '~' )}/.evm_contract_exporter/evm_contract_exporter.sqlite",
    create_db = True,
)

db.generate_mapping(create_tables=True)
