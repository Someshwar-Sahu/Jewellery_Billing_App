from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import get_session
from app.models.shop import ShopSettings, FinancialYear
from datetime import date

router    = APIRouter(prefix="/settings", tags=["Settings"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def settings_page(request: Request, session: Session = Depends(get_session)):
    shop = session.exec(select(ShopSettings)).first()
    fy   = session.exec(
        select(FinancialYear).where(FinancialYear.is_active == True)
    ).first()
    all_fy = session.exec(
        select(FinancialYear).order_by(FinancialYear.label.desc())
    ).all()
    return templates.TemplateResponse(
        request=request, name="settings/index.html",
        context={
            "shop":   shop,
            "fy":     fy,
            "all_fy": all_fy,
            "today":  date.today().isoformat(),
        }
    )


@router.post("/shop")
async def save_shop(request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    try:
        shop = session.exec(select(ShopSettings)).first()

        if not shop:
            # First time setup — create the row
            shop = ShopSettings(
                shop_name = data.get("shop_name", "My Shop"),
            )
            session.add(shop)
            session.flush()

        # Update all fields
        shop.shop_name       = data.get("shop_name")       or shop.shop_name
        shop.gstin           = data.get("gstin")           or None
        shop.address         = data.get("address")         or None
        shop.city            = data.get("city")            or None
        shop.state           = data.get("state")           or "Uttar Pradesh"
        shop.state_code      = data.get("state_code")      or "09"
        shop.phone           = data.get("phone")           or None
        shop.email           = data.get("email")           or None
        shop.bill_template   = data.get("bill_template")   or "template_dad"
        shop.bank_name       = data.get("bank_name")       or None
        shop.bank_account_no = data.get("bank_account_no") or None
        shop.bank_ifsc       = data.get("bank_ifsc")       or None
        shop.terms_line1     = data.get("terms_line1")     or None
        shop.terms_line2     = data.get("terms_line2")     or None

        session.add(shop)
        session.commit()
        return {"success": True}

    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})


@router.post("/financial-year")
async def save_fy(request: Request, session: Session = Depends(get_session)):
    """Create a new financial year or switch active FY."""
    data = await request.json()
    try:
        # Deactivate all existing FY first
        all_fy = session.exec(select(FinancialYear)).all()
        for fy in all_fy:
            fy.is_active = False
            session.add(fy)

        # Check if this label already exists
        existing = session.exec(
            select(FinancialYear).where(FinancialYear.label == data["label"])
        ).first()

        if existing:
            existing.is_active = True
            session.add(existing)
        else:
            new_fy = FinancialYear(
                label      = data["label"],
                start_date = data.get("start_date", ""),
                end_date   = data.get("end_date", ""),
                is_active  = True,
            )
            session.add(new_fy)

        session.commit()
        return {"success": True, "label": data["label"]}

    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})