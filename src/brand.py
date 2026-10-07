"""Brand constants and the legacy env-name alias shim.

Stdlib only and importing nothing else from ``src/``, so it is safe to import
before anything else (``src/constants.py`` calls ``apply_env_aliases()`` first).
"""
import os

BRAND_NAME = "Maven"
BRAND_SLUG = "maven"
ENV_PREFIX = "MAVEN_AI_"
LEGACY_ENV_PREFIX = "ODYSSEUS_"
UPSTREAM_NAME = "Odysseus"
UPSTREAM_URL = "https://github.com/odysseus-dev/odysseus"

_DEFAULT_SOURCE_URL = "https://github.com/AliArfa852/maven"
# AGPL section 13 "source" link.
SOURCE_URL = os.environ.get(ENV_PREFIX + "SOURCE_URL") or _DEFAULT_SOURCE_URL


def apply_env_aliases(environ=os.environ):
    """Make ``MAVEN_AI_X`` and ``ODYSSEUS_X`` mirror each other.

    For every suffix present under either prefix the new name wins when both
    are set, and both names end up holding the winning value. Idempotent.
    Never logs or prints values.
    """
    for key in list(environ.keys()):
        if key.startswith(ENV_PREFIX):
            suffix = key[len(ENV_PREFIX):]
            winner = environ[key]
        elif key.startswith(LEGACY_ENV_PREFIX):
            suffix = key[len(LEGACY_ENV_PREFIX):]
            if (ENV_PREFIX + suffix) in environ:
                continue  # new name wins; handled via its own key
            winner = environ[key]
        else:
            continue
        if not suffix:
            continue
        environ[ENV_PREFIX + suffix] = winner
        environ[LEGACY_ENV_PREFIX + suffix] = winner


def legacy_env_name(name):
    """``MAVEN_AI_X`` -> ``ODYSSEUS_X``."""
    if not name.startswith(ENV_PREFIX):
        raise ValueError(f"expected a {ENV_PREFIX}* name, got {name!r}")
    return LEGACY_ENV_PREFIX + name[len(ENV_PREFIX):]


def maven_env(name, default=None, environ=None):
    """Read a ``MAVEN_AI_*`` setting, falling back to its legacy ``ODYSSEUS_*`` name.

    ``name`` is the full new name, so call sites stay greppable for it. The new
    name wins whenever it is set, even to an empty string (D-0-3), which is the
    same rule apply_env_aliases follows; this works whether or not that shim has
    run yet, so it is safe in modules read before src.constants.
    """
    legacy = legacy_env_name(name)
    env = os.environ if environ is None else environ
    if name in env:
        return env[name]
    return env.get(legacy, default)
