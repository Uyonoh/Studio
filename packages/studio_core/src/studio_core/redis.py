"""Redis connection helpers shared by the API and worker services.

Managed Redis services (including Render Key Value) close idle client
connections. Two redis-py defaults make this fatal for ARQ workers:

* pooled connections are not health-checked before reuse
  (``health_check_interval`` defaults to ``0``);
* connection errors are not retried (``retry_on_error`` is empty).

The first command issued after an idle period therefore hits a socket the
server already closed and raises ``ConnectionError: Connection closed by
server``. ARQ's polling loop does not catch that error, so the worker process
exits.

These helpers build pools/settings that:

* send a PING on idle connections before reusing them;
* reconnect and retry a command when a pooled connection was closed between
  the health check and the write;
* enable TCP keepalive so intermediaries are less likely to drop idle sockets.
"""

from __future__ import annotations

from typing import Any

from arq.connections import ArqRedis, RedisSettings
from redis.asyncio import ConnectionPool
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError

# Ping an idle connection before reusing it. Render Key Value (and most
# managed providers) close connections that have been idle for a few minutes;
# 30s keeps us comfortably inside that window.
DEFAULT_HEALTH_CHECK_INTERVAL = 30
DEFAULT_RETRY_ATTEMPTS = 5
DEFAULT_SOCKET_CONNECT_TIMEOUT = 5
DEFAULT_RETRY_BASE_DELAY = 0.05
DEFAULT_RETRY_MAX_DELAY = 1.0


def _retry_policy(attempts: int) -> Retry:
    return Retry(
        ExponentialBackoff(base=DEFAULT_RETRY_BASE_DELAY, cap=DEFAULT_RETRY_MAX_DELAY),
        retries=attempts,
    )


def _pool_kwargs(
    *,
    health_check_interval: int,
    retry_attempts: int,
    max_connections: int | None,
) -> dict[str, Any]:
    return {
        "health_check_interval": health_check_interval,
        "retry_on_error": [RedisConnectionError],
        "retry": _retry_policy(retry_attempts),
        "socket_keepalive": True,
        "socket_connect_timeout": DEFAULT_SOCKET_CONNECT_TIMEOUT,
        "max_connections": max_connections,
    }


def create_redis_settings(
    url: str,
    *,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    max_connections: int | None = None,
) -> RedisSettings:
    """Return ARQ settings with connection retries enabled.

    Used where ARQ builds its own pool (for example ``arq --check``) or where
    a caller only needs settings rather than a pool.
    """
    settings = RedisSettings.from_dsn(url)
    settings.retry_on_error = [RedisConnectionError]
    settings.retry_on_timeout = True
    settings.retry = _retry_policy(retry_attempts)
    settings.max_connections = max_connections
    return settings


def create_redis_pool(
    url: str,
    *,
    health_check_interval: int = DEFAULT_HEALTH_CHECK_INTERVAL,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    max_connections: int | None = None,
) -> ArqRedis:
    """Build an ARQ Redis pool that survives idle connection drops.

    Creating the pool performs no I/O; connections are opened lazily on first
    use, so this is safe to call at import time.
    """
    connection_pool: ConnectionPool[Any] = ConnectionPool.from_url(
        url,
        **_pool_kwargs(
            health_check_interval=health_check_interval,
            retry_attempts=retry_attempts,
            max_connections=max_connections,
        ),
    )
    return ArqRedis(connection_pool=connection_pool)
