"""CRUD de cuentas de Supabase desde la interfaz web."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request

from admin_web import deps
from admin_web.views import render
from services import accounts as accounts_srv
from services import audit as audit_srv

router = APIRouter(tags=["accounts"])


@router.get("/accounts")
async def list_accounts(request: Request):
    deps.require_user(request)
    ctx = {"accounts": accounts_srv.list_accounts()}
    return render(request, "accounts/list.html", ctx)


@router.get("/accounts/new")
async def new_account(request: Request):
    deps.require_user(request)
    return render(request, "accounts/form.html", {"account": None})


@router.get("/accounts/{account_id}/edit")
async def edit_account(request: Request, account_id: int):
    deps.require_user(request)
    account = accounts_srv.get_account(account_id)
    if account is None:
        return deps.redirect("/accounts", err="Cuenta no encontrada.")
    return render(request, "accounts/form.html", {"account": account})


@router.post("/accounts/create")
async def create_account(
    request: Request,
    nombre: str = Form(""),
    pat: str = Form(""),
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)
    try:
        account_id = accounts_srv.create_account(nombre, pat)
        audit_srv.log_action("web_cuenta_crear", "ok", web_user_id=admin["id"],
                             detalle=f"cuenta '{nombre.strip()}'")
    except accounts_srv.AccountError as exc:
        return deps.redirect("/accounts", err=str(exc))
    return deps.redirect("/accounts", ok=f"Cuenta creada (id {account_id}).")


@router.post("/accounts/{account_id}/update")
async def update_account(
    request: Request,
    account_id: int,
    nombre: str = Form(""),
    pat: str = Form(""),
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)
    try:
        accounts_srv.update_account(account_id, nombre=nombre, pat=pat)
        audit_srv.log_action("web_cuenta_editar", "ok", web_user_id=admin["id"],
                             detalle=f"cuenta id {account_id}")
    except accounts_srv.AccountError as exc:
        return deps.redirect("/accounts", err=str(exc))
    return deps.redirect("/accounts", ok="Cuenta actualizada.")


@router.post("/accounts/{account_id}/delete")
async def delete_account(
    request: Request,
    account_id: int,
    confirm: str = Form(""),
):
    admin = deps.require_admin(request)
    await deps.check_csrf(request)
    if confirm.lower() != "si":
        return deps.redirect("/accounts", err="Confirma la eliminación escribiendo 'si'.")
    try:
        accounts_srv.delete_account(account_id)
        audit_srv.log_action("web_cuenta_eliminar", "ok", web_user_id=admin["id"],
                             detalle=f"cuenta id {account_id}")
    except accounts_srv.AccountError as exc:
        return deps.redirect("/accounts", err=str(exc))
    return deps.redirect("/accounts", ok="Cuenta eliminada.")