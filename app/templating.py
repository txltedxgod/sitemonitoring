"""Single shared Jinja2 templates instance + helpers.

NOTE: variable delimiters are customized to [[ ... ]] (instead of the default
double-brace syntax) to avoid conflicts with the build tooling.
"""
from __future__ import annotations

from fastapi.templating import Jinja2Templates

from app import __version__

templates = Jinja2Templates(
    directory="app/templates",
    variable_start_string="[[",
    variable_end_string="]]",
)
templates.env.globals["app_name"] = "Site Monitor"
templates.env.globals["app_version"] = __version__


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "\u2014"
    return f"{value:.1f}%"


def _fmt_ms(value: float | None) -> str:
    if value is None:
        return "\u2014"
    return f"{value:.0f} ms"


def _fmt_dt(value) -> str:
    if not value:
        return "never"
    return value.strftime("%Y-%m-%d %H:%M:%S UTC")


templates.env.filters["pct"] = _fmt_pct
templates.env.filters["ms"] = _fmt_ms
templates.env.filters["dt"] = _fmt_dt
