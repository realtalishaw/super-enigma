from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from typing import Optional
import httpx

from .services.ui_client import UIClient

router = APIRouter()
ui_client = UIClient()

# Main page routes
@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page - collect prompt + integrations"""
    return request.app.state.templates.TemplateResponse(
        "pages/home.html",
        {"request": request}
    )

@router.get("/suggestions", response_class=HTMLResponse)
async def suggestions(
    request: Request,
    prompt: Optional[str] = None,
    integrations: Optional[str] = None
):
    """Workflow suggestions page"""
    context = {
        "request": request,
        "prompt": prompt,
        "integrations": integrations.split(",") if integrations else []
    }
    return request.app.state.templates.TemplateResponse(
        "pages/suggestions.html",
        context
    )

@router.get("/builder/{workflow_id}", response_class=HTMLResponse)
async def builder(request: Request, workflow_id: str):
    """Workflow builder page"""
    # Fetch workflow data from backend
    workflow = await ui_client.get_workflow(workflow_id)
    context = {
        "request": request,
        "workflow": workflow,
        "workflow_id": workflow_id
    }
    return request.app.state.templates.TemplateResponse(
        "pages/builder.html",
        context
    )

@router.get("/preferences", response_class=HTMLResponse)
async def preferences(request: Request):
    """User preferences page"""
    # Fetch user preferences from backend
    prefs = await ui_client.get_preferences()
    context = {
        "request": request,
        "preferences": prefs
    }
    return request.app.state.templates.TemplateResponse(
        "pages/preferences.html",
        context
    )

@router.get("/integrations", response_class=HTMLResponse)
async def integrations_page(request: Request):
    """Integrations page - browse and search integrations"""
    return request.app.state.templates.TemplateResponse(
        "pages/integrations.html",
        {"request": request}
    )

# HTMX partials
@router.get("/partials/auth/modal", response_class=HTMLResponse)
async def auth_modal(request: Request):
    """Email sign-in modal"""
    return request.app.state.templates.TemplateResponse(
        "partials/auth_modal.html",
        {"request": request}
    )

@router.get("/partials/integrations", response_class=HTMLResponse)
async def integrations_list(request: Request, search: Optional[str] = None):
    """Integration list - now handled client-side"""
    return request.app.state.templates.TemplateResponse(
        "partials/integrations_list.html",
        {
            "request": request,
            "integrations": [],
            "search": search,
            "selected_integrations": []
        }
    )

@router.post("/partials/suggestions", response_class=HTMLResponse)
async def suggestions_grid(
    request: Request,
    prompt: str = Form(...),
    integrations: str = Form(...)
):
    """Suggestion cards grid from prompt/integrations"""
    # Parse integrations string and generate suggestions
    integration_list = integrations.split(",") if integrations else []
    
    # For testing, provide mock suggestions if the backend isn't available
    try:
        suggestions = await ui_client.generate_suggestions(prompt, integration_list)
    except Exception:
        # Fallback to mock data for testing
        suggestions = [
            {
                "id": "s1",
                "title": f"Auto-{prompt.split()[0].lower()} workflow",
                "description": f"Automatically handle {prompt.lower()} using {', '.join(integration_list) if integration_list else 'available integrations'}",
                "requiredIntegrationIds": integration_list,
                "stepsPreview": [
                    {"label": f"Trigger: {prompt.split()[0]}"},
                    {"label": "Process data"},
                    {"label": "Take action"}
                ]
            }
        ]
    
    context = {
        "request": request,
        "suggestions": suggestions,
        "prompt": prompt,
        "integrations": integration_list
    }
    return request.app.state.templates.TemplateResponse(
        "partials/suggestions_grid.html",
        context
    )

@router.get("/partials/builder/inputs/{workflow_id}", response_class=HTMLResponse)
async def builder_inputs(request: Request, workflow_id: str):
    """Inputs form for workflow builder"""
    schema = await ui_client.get_workflow_schema(workflow_id)
    context = {
        "request": request,
        "schema": schema,
        "workflow_id": workflow_id
    }
    return request.app.state.templates.TemplateResponse(
        "partials/builder_inputs.html",
        context
    )

@router.get("/partials/builder/graph/{workflow_id}", response_class=HTMLResponse)
async def builder_graph(request: Request, workflow_id: str):
    """SVG/HTML canvas of workflow nodes"""
    workflow = await ui_client.get_workflow(workflow_id)
    context = {
        "request": request,
        "workflow": workflow,
        "workflow_id": workflow_id
    }
    return request.app.state.templates.TemplateResponse(
        "partials/builder_graph.html",
        context
    )

@router.get("/partials/builder/logs/{workflow_id}", response_class=HTMLResponse)
async def builder_logs(request: Request, workflow_id: str):
    """Outputs/logs panel for workflow"""
    runs = await ui_client.get_workflow_runs(workflow_id, limit=1)
    context = {
        "request": request,
        "runs": runs,
        "workflow_id": workflow_id
    }
    return request.app.state.templates.TemplateResponse(
        "partials/builder_logs.html",
        context
    )

@router.get("/partials/header", response_class=HTMLResponse)
async def header_partial(request: Request):
    """Header fragment (switch sign-in ↔ profile)"""
    session = await ui_client.get_auth_session()
    context = {
        "request": request,
        "session": session
    }
    return request.app.state.templates.TemplateResponse(
        "components/header.html",
        context
    )
