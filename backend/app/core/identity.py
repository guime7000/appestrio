"""Self-identification for `backend`'s own device-row bootstrap (item 9)
-- a small, deliberate duplication of `lora-daemon`'s own
`parse_device_identity_from_hostname` (see appestrio/lora-daemon/
lora_daemon/devices.py), not a shared import: the two packages are kept
decoupled on purpose, and this is the one place in `backend` that
actually needs it (unlike item 7's local agenda evaluator, which turned
out not to need any hostname parsing at all -- see
app/services/agenda_evaluator.py's docstring).

Only ever meaningful when `Settings.IS_MASTER` is true and this
particular master Pi is *also* a `lumestrio` (dual role, per
raspestrio's own `--srv`/`-c` split) -- a pure-server-only master whose
hostname doesn't match the `<device_type><number>` convention simply
gets `None` back, non-fatally, same spirit as the `lora-daemon` side.
"""

import os

from app.models.devices import DeviceType

_HOSTNAME_ENV_OVERRIDE = "LORA_HOSTNAME"


def resolve_own_device_identity(hostname: str | None = None) -> tuple[DeviceType, int] | None:
    """Parses `hostname` (or `LORA_HOSTNAME`/`socket.gethostname()` if not
    given) as `<device_type><number>` (e.g. "lumestrio0" ->
    (DeviceType.LUMESTRIO, 0)). Returns `None` instead of raising when it
    doesn't match -- this is advisory, not a hard requirement.
    """
    if hostname is None:
        hostname = os.environ.get(_HOSTNAME_ENV_OVERRIDE)
        if not hostname:
            import socket

            hostname = socket.gethostname()
    short_hostname = hostname.split(".", 1)[0]
    for device_type in DeviceType:
        prefix = device_type.value
        if short_hostname.startswith(prefix):
            suffix = short_hostname[len(prefix) :]
            if suffix.isdigit():
                return device_type, int(suffix)
    return None
