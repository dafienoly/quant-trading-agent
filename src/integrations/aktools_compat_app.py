from __future__ import annotations

from fastapi import Request

from aktools.main import app, get_latest_version, templates
import akshare
import aktools


def _remove_homepage_route() -> None:
    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            getattr(route, "path", None) == "/"
            and "GET" in getattr(route, "methods", set())
        )
    ]


_remove_homepage_route()


@app.get("/", tags=["主页"], description="AKTools homepage", summary="AKTools homepage")
async def compatible_homepage(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="homepage.html",
        context={
            "ip_address": request.headers.get("host", ""),
            "ak_current_version": akshare.__version__,
            "at_current_version": aktools.__version__,
            "ak_latest_version": get_latest_version("akshare"),
            "at_latest_version": get_latest_version("aktools"),
        },
    )
