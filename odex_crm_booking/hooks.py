import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Detect the real booking model and wire Booking -> CRM Lead.

    Never blocks the install: if detection fails the CRM side still works and
    the link can be (re)built later from CRM > Configuration > Booking Integration.
    """
    try:
        with env.cr.savepoint():
            result = env["odex.crm.booking.bridge"]._setup_integration()
            _logger.info("odex_crm_booking: booking integration %s", result)
    except Exception:  # noqa: BLE001 - install must not fail on detection
        _logger.exception("odex_crm_booking: booking integration setup failed; "
                          "re-run it from CRM > Configuration > Booking Integration")
