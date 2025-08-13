"""Flask application entry point for the portfolio report app.

This application automatically scans the ``data`` directory for PDF files
on startup, parses them using the available extractors, stores the
results in a SQLite database and computes simple portfolio metrics. The
home page displays a summary of the ingestion status and the computed
metrics. A ``/reingest`` route is available to re‑scan the data folder
manually.

The UI is deliberately minimal: no file upload, only the data in the
``data`` directory is considered. If no PDFs are present or parsing
fails, the metrics tables will be empty.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime
from flask import Flask, jsonify, render_template_string, redirect, url_for
from .db import init_db
from .models import Base, CashFlowExternal
from .services.ingest import ingest_all, detect_extractor
from .services.holdings import consolidated_nav, latest_valuations
from .services.kpis import xirr


def create_app() -> Flask:
    app = Flask(__name__)
    # ensure data directory exists
    os.makedirs("data", exist_ok=True)
    engine, Session = init_db("sqlite:///data/app.db")
    Base.metadata.create_all(bind=engine)

    # store last ingest report in app config
    app.config["INGEST_REPORT"] = None

    def run_ingest():
        # run ingestion in background
        with Session() as s:
            app.config["INGEST_REPORT"] = ingest_all(s, "data")

    # start ingest thread on startup
    threading.Thread(target=run_ingest, daemon=True).start()

    def compute_kpis() -> dict:
        """Compute per‑account and consolidated KPIs from the database."""
        with Session() as s:
            # compute latest valuations per account
            rows = latest_valuations(s)
            accounts = {}
            all_flows = []
            total_terminal = 0.0
            max_date = None
            for acc_id, d, v in rows:
                # compute per account XIRR
                flows = (
                    s.query(CashFlowExternal)
                    .filter(CashFlowExternal.account_id == acc_id)
                    .all()
                )
                cf_list = [(f.date, f.amount) for f in flows]
                cf_list.append((d, v))
                irr = xirr(cf_list)
                accounts[acc_id] = {
                    "date": d,
                    "value": v,
                    "xirr": irr,
                }
                # accumulate for consolidated XIRR
                all_flows.extend(cf_list[:-1])
                total_terminal += v
                if max_date is None or d > max_date:
                    max_date = d
            cons_irr = None
            if max_date is not None:
                all_flows.append((max_date, total_terminal))
                cons_irr = xirr(all_flows)
            return {
                "accounts": accounts,
                "consolidated_nav": float(sum(a["value"] for a in accounts.values())),
                "consolidated_irr": cons_irr,
            }

    def parse_summaries() -> list[dict]:
        """Return a list of headline numbers for each PDF in data/.

        Uses the extractors' summary method. Does not interact with the
        database, so it reflects the raw contents of the PDFs.
        """
        out = []
        for fn in sorted(os.listdir("data")):
            if not fn.lower().endswith(".pdf"):
                continue
            path = os.path.join("data", fn)
            ex = detect_extractor(path)
            if not ex:
                out.append({"file": fn, "status": "skipped", "reason": "no match"})
                continue
            sm = ex.summary(path)
            out.append({"file": fn, "broker": ex.name, "headline": sm})
        return out

    @app.route("/")
    def index():
        # compute metrics for display
        status = app.config.get("INGEST_REPORT")
        kpis = compute_kpis()
        summaries = parse_summaries()
        # format HTML tables
        def fmt_irr(x):
            return f"{x*100:.2f}%" if x is not None else "-"

        account_rows = "".join(
            f"<tr><td>{acc_id}</td><td>{v['date']}</td><td>{v['value']:.2f}</td><td>{fmt_irr(v['xirr'])}</td></tr>"
            for acc_id, v in kpis["accounts"].items()
        )
        summary_rows = "".join(
            f"<tr><td>{item.get('file')}</td><td>{item.get('broker','-')}</td><td>{item.get('headline')}</td><td>{item.get('status','ok')}</td></tr>"
            for item in summaries
        )
        ingest_msg = "Ingestion running…" if status is None else "Ingestion complete."
        html = f"""
        <html>
        <head>
          <meta charset='utf-8'>
          <title>Portfolio Report</title>
          <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1, h2 {{ margin-bottom: 10px; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ccc; padding: 6px 8px; }}
            th {{ background: #f0f0f0; text-align: left; }}
            .small {{ color: #666; font-size: 0.9em; }}
          </style>
        </head>
        <body>
          <h1>Portfolio Report</h1>
          <p class='small'>{ingest_msg}</p>

          <h2>Headline Numbers (raw PDF parsing)</h2>
          <table>
            <tr><th>File</th><th>Broker</th><th>Headline</th><th>Status</th></tr>
            {summary_rows}
          </table>

          <h2>Account Metrics</h2>
          <table>
            <tr><th>Account ID</th><th>Date</th><th>Total Value (USD)</th><th>IRR</th></tr>
            {account_rows if account_rows else '<tr><td colspan="4">No accounts yet.</td></tr>'}
          </table>

          <h2>Consolidated</h2>
          <p>Total NAV: {kpis['consolidated_nav']:.2f}</p>
          <p>Consolidated IRR: {fmt_irr(kpis['consolidated_irr'])}</p>

          <form action='{url_for('reingest')}' method='post'>
            <button type='submit'>Re-scan data folder</button>
          </form>
        </body>
        </html>
        """
        return html

    @app.route("/reingest", methods=["POST"])
    def reingest():
        # start ingestion again in background
        def run():
            with Session() as s:
                app.config["INGEST_REPORT"] = ingest_all(s, "data")
        threading.Thread(target=run, daemon=True).start()
        return redirect(url_for("index"))

    @app.route("/api/kpi")
    def api_kpi():
        return jsonify(compute_kpis())

    @app.route("/api/ingest_report")
    def api_ingest_report():
        return jsonify(app.config.get("INGEST_REPORT"))

    @app.route("/api/parsed_main")
    def api_parsed_main():
        return jsonify(parse_summaries())

    return app


app = create_app()

if __name__ == "__main__":
    # run the development server
    app.run(debug=True)