from sqlalchemy.ext.asyncio import AsyncSession

from digidentity_api.db.errors import TenantContextError
from digidentity_api.db.tenant_context import current_tenant_id


class TenantAwareRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _assert_tenant_context(self) -> None:
        if current_tenant_id() is None:
            raise TenantContextError("no active tenant context — wrap operation in with_tenant()")
