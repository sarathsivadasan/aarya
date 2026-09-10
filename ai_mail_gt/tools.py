import logging
import threading
from functools import wraps
from odoo import api
from odoo.modules.registry import Registry
from odoo.sql_db import BaseCursor

_logger = logging.getLogger(__name__)


def after_commit(_func=None, *, wait: bool = False):
    """Decorator to execute the wrapped method *after* the current
    PostgreSQL transaction is **committed**, in a dedicated Python
    *thread*.

    Parameters
    ----------
    wait : bool, default ``False``
        * ``True``  - run in a background thread **and** ``join`` the thread,
          blocking the caller until the job is finished.
        * ``False`` - fire-and-forget: start the background thread and return
          immediately (the default behaviour).

    Usage examples
    --------------
    >>> @after_commit  # same as @after_commit(wait=False)
    ... def _update_solr(self):
    ...     pass

    >>> @after_commit(wait=True)
    ... def _heavy_export(self):
    ...     pass
    """

    def decorator(func):
        @wraps(func)
        def wrapped(self, *args, **kwargs):
            assert isinstance(self.env.cr, BaseCursor)
            dbname = self.env.cr.dbname
            context = self.env.context
            uid = self.env.uid
            su = self.env.su

            def _job():
                db_registry = Registry(dbname)
                try:
                    with db_registry.cursor() as cr:
                        env = api.Environment(cr, uid, context, su=su)
                        func(self.with_env(env), *args, **kwargs)
                except Exception as e:
                    _logger.warning("Error running %s after commit for record %s", func.__name__, self)
                    _logger.exception(e)

            @self.env.cr.postcommit.add
            def _execute_after_commit():
                thread = threading.Thread(target=_job, name=f"{func.__name__}_postcommit_thread", daemon=True)
                thread.start()
                if wait:
                    thread.join()

        return wrapped

    # Support both @after_commit and @after_commit(wait=True) syntaxes
    if _func is None:
        return decorator
    return decorator(_func)
