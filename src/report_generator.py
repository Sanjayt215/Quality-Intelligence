"""Report Generation Utility Module.

Generates self-contained, clean HTML printable reports and structured data exports
for Single-Commit Inspections, Batch Triage Sessions, and Model Audit Overviews.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pandas as pd


def generate_single_commit_html_report(
    commit_id: str,
    project: str,
    risk_score: float,
    tier_info: Dict[str, Any],
    threshold: float,
    raw_inputs: Dict[str, Any],
    derived_features: Dict[str, Any],
    notes: Optional[str] = None,
) -> str:
    """Generate self-contained HTML executive report for a single analyzed commit."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    badge_color = tier_info.get("color", "#38bdf8")
    tier_name = tier_info.get("tier", "Unclassified")
    rec = tier_info.get("recommendation", "Standard review.")

    raw_rows = "\n".join([
        f"<tr><td><code>{k}</code></td><td>{raw_inputs.get(k, 'N/A')}</td></tr>"
        for k in ["la", "ld", "nf", "nd", "ns", "ent", "ndev", "age", "nuc", "aexp", "arexp", "asexp"]
    ])

    derived_rows = "\n".join([
        f"<tr><td><code>{k}</code></td><td>{round(float(v), 4) if isinstance(v, (int, float)) else v}</td></tr>"
        for k, v in list(derived_features.items())[:10]
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Quality Intelligence - Commit Risk Audit ({html.escape(commit_id)})</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0b0f19; color: #f1f5f9; padding: 30px; line-height: 1.5; }}
  .container {{ max-width: 900px; margin: 0 auto; background: #131b2e; border: 1px solid #1e293b; border-radius: 12px; padding: 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
  .header {{ border-bottom: 1px solid #1e293b; padding-bottom: 20px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; }}
  .logo {{ font-size: 22px; font-weight: 700; color: #38bdf8; }}
  .score-badge {{ background: {badge_color}; color: #000; padding: 8px 16px; border-radius: 8px; font-weight: 700; font-size: 18px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }}
  .card {{ background: #1e293b; border-radius: 8px; padding: 18px; border: 1px solid #334155; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }}
  th, td {{ padding: 8px 10px; border-bottom: 1px solid #334155; text-align: left; }}
  th {{ color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 11px; }}
  code {{ color: #38bdf8; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
  .callout {{ background: rgba(56, 189, 248, 0.1); border-left: 4px solid #38bdf8; padding: 12px 16px; border-radius: 0 6px 6px 0; margin-top: 20px; font-size: 13px; color: #cbd5e1; }}
  .footer {{ margin-top: 30px; border-top: 1px solid #1e293b; padding-top: 14px; font-size: 11px; color: #64748b; text-align: center; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <div class="logo">🛡️ Quality Intelligence</div>
      <div style="color: #94a3b8; font-size: 13px;">Code-Change Defect-Risk Predictor Audit</div>
    </div>
    <div class="score-badge">{risk_score:.1%} Risk ({tier_name})</div>
  </div>

  <div class="grid">
    <div class="card">
      <h3 style="margin-top:0; color:#f8fafc; font-size:15px;">Commit Overview</h3>
      <p style="margin:4px 0;"><strong>Commit ID:</strong> <code>{html.escape(commit_id)}</code></p>
      <p style="margin:4px 0;"><strong>Target Project:</strong> {html.escape(project)}</p>
      <p style="margin:4px 0;"><strong>Evaluated At:</strong> {now_str}</p>
      <p style="margin:4px 0;"><strong>Decision Threshold:</strong> {threshold:.2f} ({'FLAGGED FOR REVIEW' if risk_score >= threshold else 'Standard CI Gate'})</p>
      <p style="margin:8px 0 0 0; color:#cbd5e1;"><strong>Recommendation:</strong> {html.escape(rec)}</p>
    </div>
    <div class="card">
      <h3 style="margin-top:0; color:#f8fafc; font-size:15px;">Key Churn & Complexity Indicators</h3>
      <p style="margin:4px 0;"><strong>Total Lines Changed:</strong> {raw_inputs.get('la', 0) + raw_inputs.get('ld', 0):,} lines</p>
      <p style="margin:4px 0;"><strong>Files Touched:</strong> {raw_inputs.get('nf', 1)} files (Dispersion Entropy: {raw_inputs.get('ent', 0):.2f})</p>
      <p style="margin:4px 0;"><strong>Subsystem Experience:</strong> {raw_inputs.get('asexp', 0):.0f} prior commits</p>
      <p style="margin:4px 0;"><strong>File Age:</strong> {raw_inputs.get('age', 0):.1f} days/weeks mean</p>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <h3 style="margin-top:0; color:#f8fafc; font-size:15px;">Raw Input Metrics</h3>
      <table>
        <thead><tr><th>Metric</th><th>Entered Value</th></tr></thead>
        <tbody>{raw_rows}</tbody>
      </table>
    </div>
    <div class="card">
      <h3 style="margin-top:0; color:#f8fafc; font-size:15px;">Top Derived Features</h3>
      <table>
        <thead><tr><th>Engineered Feature</th><th>Derived Value</th></tr></thead>
        <tbody>{derived_rows}</tbody>
      </table>
    </div>
  </div>

  <div class="callout">
    <strong>Scientific Methodology Disclaimer:</strong> The predicted score is an empirical Defect-Risk Priority Score trained on SZZ-identified bug-inducing commits from the ApacheJIT corpus. High scores represent elevated retrospective defect correlation, not a definitive algorithmic defect certainty or proof of a test-evading silent regression.
  </div>

  <div class="footer">
    Generated by Quality Intelligence Platform • ApacheJIT Random Forest Model (200 Trees, 26 Features)
  </div>
</div>
</body>
</html>
"""


def generate_batch_html_report(
    summary: Dict[str, Any],
    top_records: List[Dict[str, Any]],
    threshold: float,
) -> str:
    """Generate self-contained HTML review queue report for a batch upload."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    table_rows = []
    for r in top_records[:25]:
        score = r.get("defect_risk_score", r.get("risk_score", 0.0))
        tier = r.get("risk_tier", "Low Risk")
        cid = r.get("commit_id", "N/A")
        proj = r.get("project", "N/A")
        flag = "FLAGGED" if score >= threshold else "STANDARD"
        flag_color = "#ef4444" if flag == "FLAGGED" else "#10b981"
        table_rows.append(
            f"<tr><td><code>{html.escape(str(cid))}</code></td><td>{html.escape(str(proj))}</td>"
            f"<td><strong>{score:.1%}</strong></td><td>{tier}</td>"
            f"<td style='color:{flag_color}; font-weight:600;'>{flag}</td></tr>"
        )
    rows_html = "\n".join(table_rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Quality Intelligence - Batch Review Queue Audit</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0b0f19; color: #f1f5f9; padding: 30px; line-height: 1.5; }}
  .container {{ max-width: 950px; margin: 0 auto; background: #131b2e; border: 1px solid #1e293b; border-radius: 12px; padding: 32px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
  .header {{ border-bottom: 1px solid #1e293b; padding-bottom: 20px; margin-bottom: 24px; }}
  .logo {{ font-size: 22px; font-weight: 700; color: #38bdf8; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
  .kpi-card {{ background: #1e293b; border-radius: 8px; padding: 16px; border: 1px solid #334155; text-align: center; }}
  .kpi-val {{ font-size: 24px; font-weight: 700; color: #38bdf8; }}
  .kpi-lbl {{ font-size: 11px; text-transform: uppercase; color: #94a3b8; font-weight: 600; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px; }}
  th, td {{ padding: 10px 12px; border-bottom: 1px solid #334155; text-align: left; }}
  th {{ color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 11px; }}
  code {{ color: #38bdf8; font-family: ui-monospace, monospace; }}
  .footer {{ margin-top: 30px; border-top: 1px solid #1e293b; padding-top: 14px; font-size: 11px; color: #64748b; text-align: center; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="logo">🛡️ Quality Intelligence</div>
    <div style="color: #94a3b8; font-size: 13px;">Batch Triage Audit & Prioritized Review Queue • {now_str}</div>
  </div>

  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-val">{summary.get('total_processed', 0):,}</div>
      <div class="kpi-lbl">Total Commits</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val" style="color:#ef4444;">{summary.get('flagged_count', 0):,}</div>
      <div class="kpi-lbl">Flagged for Review</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">{summary.get('flagged_percentage', 0.0):.1f}%</div>
      <div class="kpi-lbl">Flagged Rate</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-val">{summary.get('mean_risk_score', 0.0):.1%}</div>
      <div class="kpi-lbl">Mean Risk Score</div>
    </div>
  </div>

  <h3 style="color:#f8fafc; font-size:16px; margin-bottom:6px;">Top Priority Commits Requiring Review (Threshold = {threshold:.2f})</h3>
  <table>
    <thead>
      <tr>
        <th>Commit ID</th>
        <th>Project</th>
        <th>Defect-Risk Score</th>
        <th>Risk Tier</th>
        <th>Review Gate</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>

  <div class="footer">
    Generated by Quality Intelligence Platform • Batch Prioritization Queue
  </div>
</div>
</body>
</html>
"""
