
import pony.orm
from generic_exporters.processors.exporters.datastores.default import read_threads, write_threads
from y._db.common import retry_locked

db_session = lambda fn: retry_locked(pony.orm.db_session(fn))