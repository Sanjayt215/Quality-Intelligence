"""UI Theme, Custom Styling, and Enterprise Design System Tokens.

Provides cohesive dark-mode SaaS developer aesthetic:
- Charcoal & Dark Navy palette (#0b0f19, #1e293b, #334155)
- Accessible risk tier color tokens (Red, Orange, Yellow, Emerald)
- Streamlit custom CSS injection
- Plotly chart dark theme templates
"""

from __future__ import annotations

from typing import Any, Dict

import plotly.graph_objects as go
import streamlit as st


# Color Palette Tokens
THEME_COLORS = {
    "bg_main": "#0b0f19",
    "bg_panel": "#131b2e",
    "bg_card": "#1e293b",
    "border": "#334155",
    "text_primary": "#f8fafc",
    "text_secondary": "#94a3b8",
    "text_muted": "#64748b",
    "accent_blue": "#38bdf8",
    "accent_indigo": "#6366f1",
    "accent_purple": "#818cf8",
    # Risk Tiers
    "risk_critical": "#ef4444",
    "risk_elevated": "#f97316",
    "risk_moderate": "#eab308",
    "risk_low": "#10b981",
}


CUSTOM_CSS = """
<style>
/* Global App Background & Typography */
.stApp {
    background-color: #0b0f19;
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* Sidebar Customization */
section[data-testid="stSidebar"] {
    background-color: #0f172a;
    border-right: 1px solid #1e293b;
}

section[data-testid="stSidebar"] .stRadio label {
    font-size: 0.95rem;
    font-weight: 500;
    color: #cbd5e1;
    padding: 4px 8px;
    border-radius: 6px;
    transition: background-color 0.15s ease;
}

section[data-testid="stSidebar"] .stRadio label:hover {
    background-color: #1e293b;
    color: #38bdf8;
}

/* Top App Header / Breadcrumb */
.top-header-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 18px;
    background-color: #131b2e;
    border: 1px solid #1e293b;
    border-radius: 10px;
    margin-bottom: 24px;
}

/* Card Containers */
.qi-card {
    background-color: #131b2e;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 18px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
}

.qi-card-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #f1f5f9;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* Hero Header */
.qi-hero {
    background: linear-gradient(135deg, #131b2e 0%, #1a243d 100%);
    border: 1px solid #2a3754;
    border-radius: 12px;
    padding: 26px 28px;
    margin-bottom: 24px;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
}

.qi-hero-title {
    font-size: 1.85rem;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: -0.02em;
    margin-bottom: 6px;
}

.qi-hero-subtitle {
    font-size: 1.05rem;
    color: #94a3b8;
    line-height: 1.5;
    margin-bottom: 0px;
}

/* Metric Display Widget */
.qi-metric-box {
    background-color: #131b2e;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 16px;
    text-align: left;
}

.qi-metric-label {
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #94a3b8;
    margin-bottom: 4px;
    font-weight: 600;
}

.qi-metric-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: #f8fafc;
    margin-bottom: 2px;
}

.qi-metric-delta {
    font-size: 0.85rem;
    color: #38bdf8;
}

/* Risk Badges */
.badge-critical {
    background-color: rgba(239, 68, 68, 0.15);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.35);
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.85rem;
    display: inline-block;
}

.badge-elevated {
    background-color: rgba(249, 115, 22, 0.15);
    color: #fb923c;
    border: 1px solid rgba(249, 115, 22, 0.35);
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.85rem;
    display: inline-block;
}

.badge-moderate {
    background-color: rgba(234, 179, 8, 0.15);
    color: #facc15;
    border: 1px solid rgba(234, 179, 8, 0.35);
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.85rem;
    display: inline-block;
}

.badge-low {
    background-color: rgba(16, 185, 129, 0.15);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.35);
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.85rem;
    display: inline-block;
}

/* Scientific Disclaimer Box */
.qi-disclaimer {
    background-color: rgba(56, 189, 248, 0.08);
    border-left: 4px solid #38bdf8;
    padding: 12px 16px;
    border-radius: 0 8px 8px 0;
    font-size: 0.9rem;
    color: #cbd5e1;
    margin: 16px 0;
    line-height: 1.5;
}

/* Buttons */
.stButton>button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s ease;
}

/* Tables */
div[data-testid="stDataFrame"] {
    border: 1px solid #1e293b;
    border-radius: 8px;
    overflow: hidden;
}
</style>
"""


def apply_ui_theme() -> None:
    """Inject custom enterprise CSS into the Streamlit application."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def get_plotly_layout(
    title: str = "",
    height: int = 380,
    show_legend: bool = True,
) -> Dict[str, Any]:
    """Generate dark-mode layout specification for Plotly charts."""
    return {
        "title": {
            "text": title,
            "font": {"color": "#f8fafc", "size": 15, "family": "Inter, system-ui, sans-serif"},
            "x": 0.02,
        },
        "height": height,
        "paper_bgcolor": "rgba(19, 27, 46, 0.0)",
        "plot_bgcolor": "rgba(19, 27, 46, 0.4)",
        "font": {"color": "#94a3b8", "size": 12},
        "margin": {"l": 40, "r": 30, "t": 50, "b": 40},
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "font": {"color": "#cbd5e1"},
        } if show_legend else {},
        "xaxis": {
            "gridcolor": "#1e293b",
            "zerolinecolor": "#334155",
            "tickfont": {"color": "#94a3b8"},
        },
        "yaxis": {
            "gridcolor": "#1e293b",
            "zerolinecolor": "#334155",
            "tickfont": {"color": "#94a3b8"},
        },
    }
