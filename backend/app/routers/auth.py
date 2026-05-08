from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
import bcrypt

from app.database import get_session
from app.models.shop import User
from app.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])
templates = Jinja2Templates(directory="app/templates")

def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def _verify(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

@router.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request, session: Session = Depends(get_session)):
    existing = session.exec(select(User)).first()
    if existing:
        return RedirectResponse(url="/auth/login", status_code=302)
    return templates.TemplateResponse(request=request, name="auth/setup.html", context={})

@router.post("/setup")
async def setup_page(request: Request, session: Session = Depends(get_session)):
    existing = session.exec(select(User)).first()
    if existing:
        return JSONResponse(status_code=400, content={"success": False, "error": "Setup already complete."})

    data = await request.json()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    confirm = (data.get("confirm") or "").strip()

    if not username or len(username) < 3:
        return JSONResponse(status_code=400, content={"success": False, "error": "Username must be at least 3 characters."})
    if not password or len(password) < 6:
        return JSONResponse(status_code=400, content={"success": False, "error": "Password must be at least 6 characters."})
    if password != confirm:
        return JSONResponse(status_code=400, content={"success": False, "error": "Passwords do not match."})

    user = User(username=username, password_hash=_hash(password), role="owner",)
    session.add(user)
    session.commit()
    session.refresh(user)

    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["role"] = user.role

    return {"success": True, "redirect": "/invoices"}

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, session: Session = Depends(get_session)):
    if request.session.get("username"):
        return RedirectResponse(url="/invoices", status_code=302)
    
    existing = session.exec(select(User)).first()

    if not existing:
        return RedirectResponse(url="/auth/setup", status_code=302)

    next_url = request.query_params.get("next", "/invoices")
    return templates.TemplateResponse(
        request=request, name="auth/login.html",
        context={"next": next_url},
    )

@router.post("/login")
async def login_submit(request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    next_url = data.get("next", "/invoices")

    if not username or not password:
        return JSONResponse(status_code=400, content={"success": False, "error": "Username and password are required."})
    
    user = session.exec(select(User).where(User.username == username)).first()

    if not user or not _verify(password, user.password_hash):
        return JSONResponse(status_code=401, content={"success": False, "error": "Incorrect username or password."})

    request.session["user_id"] = user.id
    request.session["username"] = user.username 
    request.session["role"] = user.role

    return {"success": True, "redirect": next_url}

@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=302)

@router.post("/change-password")
async def change_password(request: Request, session: Session = Depends(get_session)):
    current = get_current_user(request)
    if not current:
        return JSONResponse(status_code=401, content={"success": False, "error": "Not logged in."})

    data = await request.json()
    old_password = (data.get("old_password") or "").strip()
    new_password = (data.get("new_password") or "").strip()
    confirm = (data.get("confirm") or "").strip()

    user = session.get(User, current["id"])
    if not user or not _verify(old_password, user.password_hash):
        return JSONResponse(status_code=401, content={"success": False, "error": "Current password is incorrect."})
    if len(new_password) < 6:
        return JSONResponse(status_code=400, content={"success": False, "error": "New password must be at least 6 characters."})
    if new_password != confirm:
        return JSONResponse(status_code=400, content={"success": False, "error": "Passwords do not match."})
    
    user.password_hash = _hash(new_password)
    session.add(user)
    session.commit()
    return {"success": True}