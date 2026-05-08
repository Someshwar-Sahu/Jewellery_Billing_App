from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import get_session
from app.models.products import Product, ProductGroup

router    = APIRouter(prefix="/products", tags=["Products"])
templates = Jinja2Templates(directory="app/templates")

# ── LIST ──────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def product_list(request: Request, session: Session = Depends(get_session)):
    products = session.exec(
        select(Product).order_by(Product.metal_type, Product.name)
    ).all()
    groups = {g.id: g for g in session.exec(select(ProductGroup)).all()}
    return templates.TemplateResponse(
        request=request, name="products/list.html",
        context={"products": products, "groups": groups}
    )


# ── CREATE ────────────────────────────────────────────────────────────────────

@router.get("/create", response_class=HTMLResponse)
def create_form(request: Request, session: Session = Depends(get_session)):
    groups = session.exec(select(ProductGroup).order_by(ProductGroup.name)).all()
    return templates.TemplateResponse(
        request=request, name="products/create.html",
        context={"groups": groups}
    )


@router.post("/create")
async def create_submit(request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    try:
        product = Product(
            name               = data["name"],
            group_id           = int(data["group_id"]) if data.get("group_id") else None,
            hsn_code           = data.get("hsn_code") or "7113",
            purity             = data.get("purity")   or None,
            metal_type         = data.get("metal_type", "gold"),
            gst_rate           = float(data.get("gst_rate", 3.0)),
            making_charge_rate = float(data["making_charge_rate"]) if data.get("making_charge_rate") else None,
            huid               = data.get("huid") or None,
            description        = data.get("description") or None,
            is_active          = True,
        )
        session.add(product)
        session.commit()
        session.refresh(product)
        return {"success": True, "product_id": product.id}
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})


# ── EDIT ──────────────────────────────────────────────────────────────────────

@router.get("/{product_id}/edit", response_class=HTMLResponse)
def edit_form(product_id: int, request: Request, session: Session = Depends(get_session)):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    groups = session.exec(select(ProductGroup).order_by(ProductGroup.name)).all()
    return templates.TemplateResponse(
        request=request, name="products/edit.html",
        context={"product": product, "groups": groups}
    )


@router.post("/{product_id}/edit")
async def edit_submit(product_id: int, request: Request, session: Session = Depends(get_session)):
    data    = await request.json()
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        product.name               = data["name"]
        product.group_id           = int(data["group_id"]) if data.get("group_id") else None
        product.hsn_code           = data.get("hsn_code") or "7113"
        product.purity             = data.get("purity")   or None
        product.metal_type         = data.get("metal_type", "gold")
        product.gst_rate           = float(data.get("gst_rate", 3.0))
        product.making_charge_rate = float(data["making_charge_rate"]) if data.get("making_charge_rate") else None
        product.huid               = data.get("huid")        or None
        product.description        = data.get("description") or None
        product.is_active          = data.get("is_active", True)
        session.add(product)
        session.commit()
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})


# ── SEARCH (JSON — called by invoice.js for item autocomplete) ─────────────────

@router.get("/search")
def search_products(q: str = "", session: Session = Depends(get_session)):
    """
    Returns matching active products as JSON.
    Called live from the bill form as user types in item name field.
    """
    stmt = select(Product).where(Product.is_active == True)
    if q:
        stmt = stmt.where(Product.name.contains(q))
    products = session.exec(stmt.order_by(Product.name).limit(10)).all()
    return [
        {
            "id":                p.id,
            "name":              p.name,
            "purity":            p.purity,
            "metal_type":        p.metal_type,
            "gst_rate":          p.gst_rate,
            "hsn_code":          p.hsn_code,
            "making_charge_rate":p.making_charge_rate,
            "huid":              p.huid,
        }
        for p in products
    ]


# ── GROUP CREATE (quick add from product form) ─────────────────────────────────

@router.post("/groups/create")
async def create_group(request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    try:
        group = ProductGroup(name=data["name"])
        session.add(group)
        session.commit()
        session.refresh(group)
        return {"success": True, "group_id": group.id, "name": group.name}
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})