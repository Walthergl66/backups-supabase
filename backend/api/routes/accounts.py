"""API de cuentas de Supabase."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_current_user, require_admin
from services import accounts as accounts_srv
from services import audit as audit_srv

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("")
async def list_accounts(admin: dict = Depends(require_admin)):
    """Listado de cuentas Supabase (posible información sensible): solo admin."""
    return accounts_srv.list_accounts()


@router.post("")
async def create_account(request: Request, admin: dict = Depends(require_admin)):
    data = await request.json()
    try:
        account_id = accounts_srv.create_account(data.get("nombre", ""), data.get("pat", ""))
    except accounts_srv.AccountError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit_srv.log_action("web_cuenta_crear", "ok", web_user_id=admin["id"],
                         detalle=f"cuenta '{(data.get('nombre') or '').strip()}'")
    return {"id": account_id}


@router.get("/{account_id}")
async def get_account(account_id: int, admin: dict = Depends(require_admin)):
    account = accounts_srv.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Cuenta no encontrada.")
    return account


@router.put("/{account_id}")
async def update_account(account_id: int, request: Request, admin: dict = Depends(require_admin)):
    data = await request.json()
    try:
        accounts_srv.update_account(
            account_id,
            nombre=data.get("nombre") or None,
            pat=data.get("pat") or None,
        )
    except accounts_srv.AccountError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit_srv.log_action("web_cuenta_editar", "ok", web_user_id=admin["id"],
                         detalle=f"cuenta id {account_id}")
    return {"ok": True}


@router.delete("/{account_id}")
async def delete_account(account_id: int, admin: dict = Depends(require_admin)):
    try:
        accounts_srv.delete_account(account_id)
    except accounts_srv.AccountError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit_srv.log_action("web_cuenta_eliminar", "ok", web_user_id=admin["id"],
                         detalle=f"cuenta id {account_id}")
    return {"ok": True}