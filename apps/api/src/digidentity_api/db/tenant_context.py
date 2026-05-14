from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from digidentity_api.db.errors import TenantContextError

_current_tenant: ContextVar[UUID | None] = ContextVar("current_tenant", default=None)

# Default factory — impostato all'avvio app; overridabile nei test
_default_factory: async_sessionmaker | None = None


def set_default_session_factory(factory: async_sessionmaker) -> None:
    global _default_factory
    _default_factory = factory


def current_tenant_id() -> UUID | None:
    return _current_tenant.get()


@asynccontextmanager
async def with_tenant(
    tenant_id: UUID,
    *,
    session_factory: async_sessionmaker | None = None,
) -> AsyncGenerator[AsyncSession]:
    if _current_tenant.get() is not None:
        raise TenantContextError(
            f"nested tenant context not allowed "
            f"(active: {_current_tenant.get()}, requested: {tenant_id})"
        )

    factory = session_factory or _default_factory
    if factory is None:
        raise TenantContextError(
            "no session factory configured — call set_default_session_factory()"
        )

    token = _current_tenant.set(tenant_id)
    try:
        async with factory() as session:
            async with session.begin():
                # SET LOCAL non accetta parametri bind in asyncpg:
                # il valore viene sanitizzato (solo caratteri UUID validi) e
                # interpolato direttamente nella stringa SQL.
                tid_str = str(tenant_id)
                await session.execute(text(f"SET LOCAL app.tenant_id = '{tid_str}'"))
                yield session
    finally:
        _current_tenant.reset(token)
