
from os import path
from typed_envs import EnvVarFactory

_env_factory = EnvVarFactory("EVM_CONTRACT_EXPORTER")

DB_PROVIDER = _env_factory.create_env("DB_PROVIDER", str, default="sqlite", verbose=False)
# if you use sqlite as the provider, you can set this:
SQLITE_PATH = _env_factory.create_env("SQLITE_PATH", str, default=f"{path.expanduser( '~' )}/.evm_contract_exporter", verbose=False)
# otherwise, you'll set these:
DB_HOST = _env_factory.create_env("DB_HOST", str, default='', verbose=False)
DB_PORT = _env_factory.create_env("DB_PORT", str, default='', verbose=False)
DB_DATABASE = _env_factory.create_env("DB_DATABASE", str, default='', verbose=False)
DB_USER = _env_factory.create_env("DB_USER", str, default='', verbose=False)
DB_PASSWORD = _env_factory.create_env("DB_PASSWORD", str, default='', verbose=False)
