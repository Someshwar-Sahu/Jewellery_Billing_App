from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from app.database import get_session
from app.models.shop import User

def get_current_user(request: Request) -> dict | None:
    """
    Read the logged-in user from the signed session cookie.
    Returns a dict with id, username, role — or None if not logged in.
    """
    username = request.session.get("username")
    if not username:
        return None
    return{
        "id": request.session.get("user_id"),
        "username": username,
        "role": request.session.get("role", "owner"),
    }

def require_login(request: Request):
    """
    Dependency used on every protected router.
    If no valid session → redirect to /auth/login.
    FastAPI dependency injection handles this before the route function runs.
    """
    user = get_current_user(request)
    if user is None:
        request.session["next"] = str(request.url)
        from fastapi.responses import RedirectResponse
        raise _LoginRedirect()
    
class _LoginRedirect(Exception):
    """Internal sentinel raised by require_login."""
    pass

def add_login_redirect_handler(app):
    from fastapi import Request as _Request
    from fastapi.responses import RedirectResponse as _RR

    @app.exception_handler(_LoginRedirect)
    async def login_redirect_handler(_request: _Request, _exc: _LoginRedirect):
        next_url = _request.session.get("next","/invoices")
        return _RR(url=f"/auth/login?next={next_url}", status_code=302)