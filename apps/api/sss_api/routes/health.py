"""Process-level health route."""

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live(request: Request) -> dict[str, str]:
    return {
        "status": "ok",
        "service": "sss-api",
        "environment": request.app.state.settings.environment,
    }
