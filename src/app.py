from __future__ import annotations
import os
from flask import Flask, jsonify, render_template_string, redirect, url_for
from .db import init_db
from .models import Base, CashFlowExternal
from .services.ingest import ingest_all, detect_extractor
from .services.holdings import consolidated_nav, latest_valuations
from .services.kpis import xirr

def _safe_parse_summaries(data_dir: str = "data"):
    out = []
    for fn in sorted(os.listdir(data_dir)):
        if not fn.lower().endswith(".pdf"):
            continue
        path = os.path.join(data_dir, fn)
        ex = detect_extractor(path)
        if not ex:
            out.append({"file": fn, "status": "skipped", "reason": "no match"})
            continue
        try:
            sm = ex.summary(path)  # side-effect free
            out.append({"file": fn, "status": "ok", "broker": ex.name, "summary": sm})
        except Exception as e:
            out.append({"file": fn, "status": "error", "error": str(e)})
    return out

def create_app() -> Flask:
    app = Flask(__name__)
    os.makedirs("data", exist_ok=True)
    engine, Session = init_db("sqlite:///data/app.db")
    Base.metadata.create_all(bind=engine)

    # Ingest once, synchronously, so the page has data immediately
    with Session() as s:
        app.config["INGEST_REPORT"] = ingest_all(s, "data")

    @app.get("/")
    def index():
        summaries = _safe_parse_summaries("data")

        # KPIs from DB
        with Session() as s:
            lv = latest_valuations(s)
            accounts, all_flows, total_terminal, max_date = [], [], 0.0, None
            for account_id, d, v in lv:
                if max_date is None or d > max_date:
                    max_date = d
                flows = s.query(CashFlowExternal).filter(
                    CashFlowExternal.account_id == account_id
                ).all()
                cf = [(f.date, f.amount) for f in flows] + [(d, v)]
                accounts.append({"id": account_id, "date": str(d), "value": v, "xirr": xirr(cf)})
                all_flows.extend(cf[:-1])
                total_terminal += v
            consolidated_irr = None
            if max_date is not None:
                all_flows.append((max_date, total_terminal))
                consolidated_irr = xirr(all_flows)

        rep = app.config.get("INGEST_REPORT") or []
        ok = sum(1 for r in rep if r.get("status") == "ok")
        skip = sum(1 for r in rep if r.get("status") == "skipped")
        err = sum(1 for r in rep if r.get("status") == "error")
        ingest_label = f"ok={ok}, skipped={skip}, errors={err}" if rep else "no files found"

        html = """
        <html><head><meta charset="utf-8" />
        <title>Portfolio</title>
        <style>
          body{font-family:system-ui, -apple-system, Segoe UI, Roboto, Arial; margin:24px}
          table{border-collapse:collapse; width:100%} th,td{border:1px solid #ddd;padding:6px 8px;text-align:left; vertical-align: top}
          .err{color:#b00} .pill{padding:6px 10px;border:1px solid #eee;border-radius:999px;background:#fafafa;margin-bottom:12px;display:inline-block}
          button{padding:8px 12px;border:1px solid #ccc;border-radius:8px;background:#fff;cursor:pointer}
          h2{margin:12px 0}
        </style></head><body>
        <h2>Headlines parsed from data/</h2>
        <div class="pill">Last ingest: {{ ingest_label }}</div>

        <table>
          <tr><th>File</th><th>Status</th><th>Broker</th><th>As-of / Period</th><th>Total / NAV</th><th>Error</th></tr>
          {% for r in summaries %}
            <tr>
              <td>{{ r.file }}</td>
              <td>{{ r.status }}</td>
              <td>{{ r.get('broker','') }}</td>
              <td>
                {% if r.status == 'ok' %}
                  {% set sm = r.summary %}
                  {% if sm.get('asof') %}{{ sm.get('asof') }}
                  {% elif sm.get('period_start') %}{{ sm.get('period_start') }} → {{ sm.get('period_end') }}
                  {% else %}–{% endif %}
                {% endif %}
              </td>
              <td>
                {% if r.status == 'ok' %}
                  {% set sm = r.summary %}
                  {% set cv = sm.get('current_value') %}
                  {% set tp = sm.get('total_portfolio') %}
                  {% set en = sm.get('end_nav_usd') %}
                  {% if cv is not none %}{{ "%.2f"|format(cv) }}
                  {% elif tp is not none %}{{ "%.2f"|format(tp) }}
                  {% elif en is not none %}{{ "%.2f"|format(en) }}
                  {% else %}–{% endif %}
                {% endif %}
              </td>
              <td class="err">{{ r.get('error','') }}</td>
            </tr>
          {% endfor %}
        </table>

        <h2>Accounts (from DB)</h2>
        <table>
          <tr><th>Account ID</th><th>As of</th><th>Value</th><th>XIRR</th></tr>
          {% for a in accounts %}
            <tr>
              <td>{{ a.id }}</td>
              <td>{{ a.date }}</td>
              <td>{{ "%.2f"|format(a.value) }}</td>
              <td>{% if a.xirr is not none %}{{ (a.xirr*100)|round(2) }}%{% else %}–{% endif %}</td>
            </tr>
          {% endfor %}
        </table>

        <p style="margin-top:12px"><b>Consolidated NAV:</b> {{ "%.2f"|format(accounts|sum(attribute='value')) }}</p>
        <p><b>Consolidated IRR:</b> {% if consolidated_irr is not none %}{{ (consolidated_irr*100)|round(2) }}%{% else %}–{% endif %}</p>

        <form action="/reingest" method="post" style="margin-top:16px"><button>Re-scan data/</button></form>
        </body></html>
        """
        return render_template_string(html,
            summaries=summaries,
            accounts=accounts,
            consolidated_irr=consolidated_irr,
            ingest_label=ingest_label
        )

    @app.post("/reingest")
    def reingest():
        # Re-run parsing, refresh page
        with Session() as s:
            app.config["INGEST_REPORT"] = ingest_all(s, "data")
        return redirect(url_for("index"))

    # Dev JSON routes (optional)
    @app.get("/api/parsed_main")
    def api_parsed_main():
        return jsonify(_safe_parse_summaries("data"))

    @app.get("/api/ingest_report")
    def api_ingest_report():
        return jsonify(app.config.get("INGEST_REPORT"))

    return app

app = create_app()
if __name__ == "__main__":
    app.run(debug=True)
