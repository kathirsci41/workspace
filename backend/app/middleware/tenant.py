"""
Tenant middleware — stubs tenant_id as 'default' for all requests.
When multi-user lands: extract tenant from JWT and set here.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.tenant_id = "default"
        return await call_next(request)


def get_tenant_id(request: Request) -> str:
    return getattr(request.state, "tenant_id", "default")
