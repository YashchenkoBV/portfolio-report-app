from __future__ import annotations
import os, json, threading
from flask import Flask, jsonify, render_template_string
from .db import init_db
from .models import Base, Valuation, CashFlowExternal
from .services.ingest import ingest_all, detect_extractor
from .services.holdings import consolidated_nav, latest_valuations
from .services.kpis import xirr

INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Portfolio App</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 24px; color:#222; }
    h1 { margin: 0 0 8px; }
    .sub { color:#666; margin-bottom:16px; }
    .row { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-bottom:10px; }
    button { padding:9px 12px; border:1px solid #d0d0d0; border-radius:10px; background:#fff; cursor:pointer; }
    button:hover { background:#f6f6f6; }
    .pill { padding:6px 10px; border:1px solid #eee; border-radius:999px; background:#fafafa; }
    .card { border:1px solid #eee; padding:12px; border-radius:12px; margin-top:12px; }
    pre { white-space: pre-wrap; word-break: break-word; background:#fcfcfc; border:1px solid #f0f0f0; padding:10px; border-radius:8px; }
    .ok{color:#2a7;}
    .warn{color:#c80;}
    .err{color:#c22;}
  </style>
</head>
<body>
  <h1>Portfolio App</h1>
  <div class="sub">Works only with PDFs in <b>data/</b>. Ingestion runs automatically on server start.</div>

  <div class="row">
    <span class="pill" id="ingest-pill">Ingestion: pending…</span>
    <button onclick="call('GET','/api/ingest_report')">Ingest Report</button>
    <button onclick="call('GET','/api/parsed_main')">Parsed Main</button>
    <button onclick="call('GET','/api/dashboard')">Dashboard</button>
    <button onclick="call('GET','/api/kpi')">KPI</button>
    <button onclick="call('POST','/api/reingest')">Re-scan data/</button>
  </div>

  <div class="card">
    <div id="status">Ready.</div>
    <pre id="out"></pre>
  </div>

<script>
async function call(method, url) {
  setStatus(method + " " + url + " …");
  try {
    const res = await fetch(url, { method });
    const txt = await res.text();
    let body = txt;
    try { body = JSON.parse(txt); } catch {}
    setStatus(method + " " + url + " → " + res.status);
    show(body);
  } catch (e) {
    setStatus("Error: " + e);
  }
}
function setStatus(s){ document.getElementById('status').textContent = s; }
function show(obj){ 
  const pre = document.getElementById('out'); 
  pre.textContent = (typeof obj === 'string') ? obj : JSON.stringify(obj, null, 2);
}
// initial poll of ingest status
async function pollIngest() {
  try{
    const res = await fetch('/api/ingest_report');
    const data = await res.json();
    const pill = document.getElementById('ingest-pill');
    if (Array.isArray(data)) {
      const ok = data.filter(x=>x.status==='ok').length;
      const skip = data.filter(x=>x.status==='skipped').length;
      const err = data.filter(x=>x.status==='error').length;
      pill.textContent = `Ingestion: ok=${ok}, skipped=${skip}, errors=${err}`;
      pill.className = 'pill ' + (err? 'err' : (ok? 'ok':'warn'));
    } else {
      pill.textContent = 'Ingestion: pending…';
      pill.className = 'pill';
    }
  }catch(e){}
}
pollIngest();
setInterval(pollIngest, 3000);
</script>
</body>
</html>
"""

def create_app():
    app = Flask(__name__)
    os.makedirs("data", exist_ok=True)
    engine, Session = init_db("sqlite:///data/app.db")
    Base.metadata.create_all(bind=engine)

    app.config["INGEST_REPORT"] = None  # last run report

    # --- kick off ingestion immediately (in a thread to avoid blocking boot) ---
    def _run_ingest():
        with Session() as s:
            app.config["INGEST_REPORT"] = ingest_all(s, "data")
    threading.Thread(target=_run_ingest, daemon=True).start()

    # --- UI home ---
    @app.get("/")
    def home():
        return render_template_string(INDEX_HTML)

    # --- APIs the UI calls ---
    @app.get("/api/ingest_report")
    def api_ingest_report():
        return jsonify(app.config.get("INGEST_REPORT"))

    @app.post("/api/reingest")
    def api_reingest():
        with Session() as s:
            app.config["INGEST_REPORT"] = ingest_all(s, "data")
            return jsonify(app.config["INGEST_REPORT"])

    @app.get("/api/parsed_main")
    def parsed_main():
        # parse headline numbers straight from PDFs, no DB
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
        return jsonify(out)

    @app.get("/api/dashboard")
    def api_dashboard():
        with Session() as s:
            nav = consolidated_nav(s)
            return {"consolidated_nav": nav}

    @app.get("/api/kpi")
    def api_kpi():
        with Session() as s:
            lv = latest_valuations(s)
            result, all_flows, total_terminal, max_date = {"accounts": {}, "consolidated": None}, [], 0.0, None
            for account_id, d, v in lv:
                if max_date is None or d > max_date: max_date = d
                flows = s.query(CashFlowExternal).filter(CashFlowExternal.account_id == account_id).all()
                cf = [(f.date, f.amount) for f in flows]
                cf.append((d, v))
                result["accounts"][account_id] = {"date": str(d), "value": v, "xirr": xirr(cf)}
                all_flows.extend(cf[:-1]); total_terminal += v
            if max_date is not None:
                all_flows.append((max_date, total_terminal))
                result["consolidated"] = xirr(all_flows)
            return jsonify(result)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
