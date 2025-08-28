from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os

from .ui_routes import router as ui_router

app = FastAPI(
    title="Weave - Workflow Automation Engine",
    description="UI for building and managing automated workflows",
    version="1.0.0"
)

# Mount static files if directory exists
static_dir = Path("app/static")
if static_dir.exists() and static_dir.is_dir():
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
else:
    print(f"Warning: Static directory {static_dir} does not exist. Static files will not be served.")

# Setup Jinja2 templates
templates_dir = Path("app/templates")
if templates_dir.exists() and templates_dir.is_dir():
    templates = Jinja2Templates(directory="app/templates")
else:
    raise RuntimeError(f"Templates directory {templates_dir} does not exist. Cannot start application.")

# Make templates available to all requests
@app.middleware("http")
async def add_templates_to_request(request: Request, call_next):
    request.app.state.templates = templates
    response = await call_next(request)
    return response

# Include UI routes
app.include_router(ui_router)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "weave-ui"}

@app.get("/test")
async def test_page(request: Request):
    """Test page to verify HTMX and interactions"""
    return request.app.state.templates.TemplateResponse(
        "test.html",
        {"request": request}
    )
