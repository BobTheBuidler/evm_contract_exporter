
from os import path
from typed_envs import EnvVarFactory

_env_factory = EnvVarFactory("EVM_CONTRACT_EXPORTER")

DB_PROVIDER = _env_factory.create_env("DB_PROVIDER", str, default="sqlite")
SQLITE_PATH = _env_factory.create_env("SQLITE_PATH", str, default=f"{path.expanduser( '~' )}/.evm_contract_exporter")