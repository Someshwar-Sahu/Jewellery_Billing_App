from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
from app.database import get_session
from app.models.parties import Party
from app.schemas.party import PartyCreate, PartyUpdate
from app.services.party_service import (
    create_party, update_party, get_party_summary, search_parties,
    settle_opening_balance,
)
from datetime import date

router    = APIRouter(prefix="/parties", tags=["Parties"])
templates = Jinja2Templates(directory="app/templates")


# ── LIST ──────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def party_list(
    request: Request,
    q: str = "",
    type: str = "",
    session: Session = Depends(get_session)
):
    parties = search_parties(session, query=q, type_filter=type)
    return templates.TemplateResponse(
        request=request, name="parties/list.html",
        context={"parties": parties, "q": q, "type_filter": type}
    )


# ── CREATE ────────────────────────────────────────────────────────────────────

@router.get("/create", response_class=HTMLResponse)
def create_party_form(request: Request, type: str = "customer"):
    return templates.TemplateResponse(
        request=request, name="parties/create.html",
        context={"prefill_type": type}
    )


@router.post("/create")
async def create_party_submit(request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    try:
        party_data = PartyCreate(
            type                 = data.get("type", "customer"),
            name                 = data["name"],
            phone                = data.get("phone") or None,
            email                = data.get("email") or None,
            address              = data.get("address") or None,
            city                 = data.get("city") or None,
            state                = data.get("state") or None,
            gstin                = data.get("gstin") or None,
            credit_limit         = float(data["credit_limit"]) if data.get("credit_limit") else None,
            credit_days          = int(data["credit_days"])    if data.get("credit_days")   else None,
            opening_balance      = float(data["opening_balance"]) if data.get("opening_balance") else None,
            opening_balance_type = data.get("opening_balance_type") or None,
            notes                = data.get("notes") or None,
        )
        party = create_party(session, party_data)
        return {"success": True, "party_id": party.id, "name": party.name}
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"success": False, "error": e.detail})
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})


# ── DETAIL ────────────────────────────────────────────────────────────────────

@router.get("/{party_id}", response_class=HTMLResponse)
def party_detail(party_id: int, request: Request, session: Session = Depends(get_session)):
    summary = get_party_summary(session, party_id)
    summary["today"] = date.today().isoformat()
    return templates.TemplateResponse(
        request=request, name="parties/detail.html",
        context=summary
    )

# ── SETTLE OPENING BALANCE ────────────────────────────────────────────────────

@router.post("/{party_id}/settle-opening-balance")
async def settle_opening_balance_endpoint(
    party_id: int, request: Request, session: Session = Depends(get_session)
):
    from datetime import date
    data         = await request.json()
    amount       = float(data.get("amount", 0))
    mode         = data.get("mode", "cash")
    reference_no = data.get("reference_no") or None
    notes        = data.get("notes") or None
    date_raw     = data.get("settlement_date")
    settlement_date = date.fromisoformat(date_raw) if date_raw else None

    try:
        result = settle_opening_balance(
            session         = session,
            party_id        = party_id,
            amount          = amount,
            mode            = mode,
            settlement_date = settlement_date,
            reference_no    = reference_no,
            notes           = notes,
        )
        return result
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"success": False, "error": e.detail})
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})

# ── EDIT ──────────────────────────────────────────────────────────────────────

@router.get("/{party_id}/edit", response_class=HTMLResponse)
def edit_party_form(party_id: int, request: Request, session: Session = Depends(get_session)):
    party = session.get(Party, party_id)
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    return templates.TemplateResponse(
        request=request, name="parties/edit.html",
        context={"party": party}
    )


@router.post("/{party_id}/edit")
async def edit_party_submit(party_id: int, request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    try:
        update_data = PartyUpdate(
            name         = data.get("name"),
            phone        = data.get("phone") or None,
            email        = data.get("email") or None,
            address      = data.get("address") or None,
            city         = data.get("city") or None,
            state        = data.get("state") or None,
            gstin        = data.get("gstin") or None,
            credit_limit = float(data["credit_limit"]) if data.get("credit_limit") else None,
            credit_days  = int(data["credit_days"])    if data.get("credit_days")   else None,
            notes        = data.get("notes") or None,
        )
        party = update_party(session, party_id, update_data)
        return {"success": True, "party_id": party.id}
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"success": False, "error": e.detail})
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})
