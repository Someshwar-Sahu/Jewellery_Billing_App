from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import get_session
from app.models.shop import ShopSettings
from datetime import date

router = APIRouter(prefix="/rough-bill", tags=["Rough Bill"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
def rough_bill_form(request: Request, session: Session = Depends(get_session)):
    """Render the data entry form for a Rough bill"""
    return templates.TemplateResponse(
        request=request, name="rough_bills/index.html",
        context={},
    )

@router.post("/print", response_class=HTMLResponse)
async def print_rough_bill(request: Request, session: Session = Depends(get_session)):
    """"Stateless print endpoint. Takes JSON, return HTML. No DB saving"""
    data = await request.json()

    shop = session.exec(select(ShopSettings)).first()

    return templates.TemplateResponse(
        request=request, name="rough_bills/print.html",
        context={
            "shop": shop,
            "customer_name": data.get("customer_name", ""),
            "customer_address": data.get("customer_address", ""),
            "bill_date": date.fromisoformat(data.get("bill_date", "")).strftime("%d/%m/%Y") if data.get("bill_date") else "",
            "items": data.get("items", []),
            "grand_total": data.get("grand_total", 0),
        }
    )