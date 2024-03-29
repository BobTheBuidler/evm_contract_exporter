
import errno
import logging
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from os import mkdir

from brownie import chain
from pony.orm import (Database, LongStr, ObjectNotFound, Optional, PrimaryKey,
                      Required, Set, TransactionIntegrityError, commit, db_session, select)

from evm_contract_exporter import ENVIRONMENT_VARIABLES as ENVS
from evm_contract_exporter import types
from evm_contract_exporter.db import common


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
    @common.db_session
    def entity_exists(cls, chainid: int, address: types.address) -> bool:
        try:
            cls[chainid, address]
            logger.debug('%s exists in db for (%s, %s)', cls.__name__, chainid, address)
            return True
        except ObjectNotFound:
            logger.debug('%s does not exist in db for (%s, %s)', cls.__name__, chainid, address)
            return False
    
    @classmethod
    @lru_cache(maxsize=500)
    @common.db_session
    def insert_entity(cls, *args, **kwargs) -> None: #chainid: int, address: address, name: str, symbol: str, decimals: int) -> None:
        try:
            entity = cls(*args, **kwargs)
            commit()
        except TransactionIntegrityError:
            logger.debug("another thread has already added %s ")
            return
        if isinstance(entity, Token):
            logger.debug("New token %s found: %s %s", kwargs['symbol'], entity, kwargs['name'])
        else:
            logger.debug("inserted %s to db", entity)


class Contract(Address):
    deployer = Optional(Address)
    deploy_block = Optional(int, lazy=True)
    deploy_timestamp = Optional(datetime, lazy=True)
    contract_notes = Optional(LongStr, lazy=True)
    is_verified = Required(bool, default=False, index=True, lazy=True)
    last_checked_verified = Optional(datetime, index=True, lazy=True)

    @classmethod
    async def set_non_verified(cls, chainid: int, address: str) -> None:
        await common.write_threads.run(cls._set_non_verified, chainid, address)

    @classmethod
    @common.db_session
    def _set_non_verified(cls, chainid: int, address: str) -> None:
        entity = cls[chainid, address]
        entity.is_verified = False
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
    value = Required(Decimal, precision=38, scale=18)


def _ensure_storage_path_exists(sqlite_path: str) -> None:
    try:
        mkdir(sqlite_path)
        #mkdir(f"{lib_storage_dir}/grafana_data")
        #mkdir(f"{lib_storage_dir}/grafana_provisioning")
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

# TODO: make configurable
if ENVS.DB_PROVIDER == "sqlite":
    _ensure_storage_path_exists(ENVS.SQLITE_PATH)  # type: ignore [arg-type]
    db.bind(
        provider = "sqlite",
        filename = f"{ENVS.SQLITE_PATH}/evm_contract_exporter.sqlite",
        create_db = True,
    )
else:
    connection_settings = {
        'provider': str(ENVS.DB_PROVIDER),
        'host': str(ENVS.DB_HOST),
        'user': str(ENVS.DB_USER),
        'password': str(ENVS.DB_PASSWORD),
        'database': str(ENVS.DB_DATABASE),
    }
    if ENVS.DB_PORT:
        connection_settings['port'] = int(ENVS.DB_PORT)  # type: ignore [call-overload]
    db.bind(**connection_settings)

db.generate_mapping(create_tables=True)

with db_session:
    known_entities_at_startup = select(a.address for a in Address if a.chainid == chain.id)[:]