from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.router import api_router

app = FastAPI(title="TRACE API", version="0.1.0", docs_url="/docs")
app.include_router(api_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc),
            }
        },
    )
