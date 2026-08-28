import secrets

from fastapi import Header, HTTPException, Request, status


async def require_service_token(
    request: Request,
    x_service_token: str | None = Header(default=None),
) -> None:
    expected = request.app.state.settings.service_token.get_secret_value()
    if not x_service_token or not secrets.compare_digest(x_service_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service credentials",
        )
