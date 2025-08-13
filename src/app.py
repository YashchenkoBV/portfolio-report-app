from __future__ import annotations
import os, json
from flask import Flask, jsonify, render_template_string, redirect, url_for
from .db import init_db
from .models import Base, CashFlowExternal, Valuation
from .services.ingest import ingest_all
from .services.holdings import consolidated_nav, latest_valuations, all_valuations, account_names
from .services.kpis import xirr

def create_app() -> Flask:
    app = Flask(__name__)
    os.makedirs("data", exist_ok=True)
    engine, Session = init_db("sqlite:///data/app.db")
    Base.metadata.create_all(bind=engine)

    # ingest once, sync
    with Session() as s:
        app.config["INGEST_REPORT"] = ingest_all(s, "data")

    @app.get("/")
    def index():
        # Fast paint; data loaded via JS
        rep = app.config.get("INGEST_REPORT") or []
        ok = sum(1 for r in rep if r.get("status") == "ok")
        skip = sum(1 for r in rep if r.get("status") == "skipped")
        err = sum(1 for r in rep if r.get("status") == "error")
        ingest_label = f"ok={ok}, skipped={skip}, errors={err}" if rep else "no files found"

        html = """
        <html><head><meta charset="utf-8" />
        <title>Portfolio</title>
        <script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>
        <style>
          body{font-family:system-ui, -apple-system, Segoe UI, Roboto, Arial; margin:24px}
          table{border-collapse:collapse; width:100%} th,td{border:1px solid #ddd;padding:6px 8px;text-align:left; vertical-align: top}
          .err{color:#b00} .pill{padding:6px 10px;border:1px solid #eee;border-radius:999px;background:#fafafa;margin-bottom:12px;display:inline-block}
          button{padding:8px 12px;border:1px solid #ccc;border-radius:8px;background:#fff;cursor:pointer}
          h2{margin:12px 0}
          /* simple "wait" overlay */
          #wait{position:fixed;inset:0;background:rgba(255,255,255,.9);display:flex;align-items:center;justify-content:center;font-size:18px;z-index:9999}
          .spinner{width:26px;height:26px;border:3px solid #ccc;border-top-color:#555;border-radius:50%;margin-right:10px;animation:spin 1s linear infinite}
          @keyframes spin{to{transform:rotate(360deg)}}
        </style></head><body>
        <div id="wait"><div class="spinner"></div><div>Please wait… parsing PDFs and computing metrics</div></div>

        <h2>Headlines parsed from data/</h2>
        <div class="pill">Last ingest: {{ ingest_label }}</div>
        <table id="tbl-summ"><tr><th>File</th><th>Status</th><th>Broker</th><th>As-of / Period</th><th>Total / NAV</th><th>Error</th></tr></table>

        <h2>Accounts (from DB)</h2>
        <table id="tbl-accts"><tr><th>Account</th><th>As of</th><th>Value</th><th>XIRR</th></tr></table>

        <p style="margin-top:12px"><b>Consolidated NAV:</b> <span id="con-nav">–</span></p>
        <p><b>Consolidated IRR:</b> <span id="con-irr">–</span></p>

        <div id="charts" style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px">
          <div><div id="chart-waterfall" style="height:340px"></div></div>
          <div><div id="chart-allocation" style="height:340px"></div></div>
        </div>
        <div style="margin-top:16px"><div id="chart-line" style="height:340px"></div></div>

        <form action="/reingest" method="post" style="margin-top:16px"><button>Re-scan data/</button></form>

        <script>
        function td(txt){const d=document.createElement('td'); d.textContent=txt; return d;}
        function row(cells){const tr=document.createElement('tr'); cells.forEach(c=>tr.appendChild(c)); return tr;}

        async function loadAll(){
          const [summR, kpiR] = await Promise.all([fetch('/api/parsed_main'), fetch('/api/kpi')]);
          const summaries = await summR.json();
          const kpi = await kpiR.json();

          // fill summaries
          const sTbl = document.getElementById('tbl-summ');
          summaries.forEach(r=>{
            const asof = r.status==='ok' ? (r.summary.asof || (r.summary.period_start? (r.summary.period_start+' → '+r.summary.period_end) : '–')) : '';
            const total = r.status==='ok'
              ? (r.summary.current_value ?? r.summary.total_portfolio ?? r.summary.end_nav_usd ?? null)
              : null;
            sTbl.appendChild(row([
              td(r.file), td(r.status), td(r.broker||''), td(asof),
              td(total!=null ? (Number(total).toFixed(2)) : '–'),
              td(r.error||'')
            ]));
          });

          // fill accounts
          const aTbl = document.getElementById('tbl-accts');
          (kpi.accounts||[]).forEach(a=>{
            const irr = (a.xirr!=null) ? (a.xirr*100).toFixed(2)+'%' : '–';
            aTbl.appendChild(row([td(a.name||a.id), td(a.date), td((a.value||0).toFixed(2)), td(irr)]));
          });

          document.getElementById('con-nav').textContent = (kpi.consolidated_nav||0).toFixed(2);
          document.getElementById('con-irr').textContent = (kpi.consolidated_irr!=null) ? (kpi.consolidated_irr*100).toFixed(2)+'%' : '–';

          // charts
          drawWaterfall(kpi.bridge||{});
          drawAllocation(kpi.accounts||[]);
          drawLine(kpi.timeseries||[]);

          document.getElementById('wait').style.display = 'none';
        }

        function drawWaterfall(bridge){
          const s = bridge.start_nav, f = bridge.end_nav, nf = bridge.net_flows, pnl = bridge.pnl;
          if (s==null || f==null){ Plotly.purge('chart-waterfall'); return; }
          const x = ['Start NAV','Net Flows','P&L','End NAV'];
          const measure = ['absolute','relative','relative','total'];
          const y = [s, nf||0, pnl|| (f - s - (nf||0)), f];
          Plotly.newPlot('chart-waterfall', [{type:'waterfall', x, y, measure}], {title:'NAV Bridge', margin:{t:40}});
        }

        function drawAllocation(accounts){
          if (!accounts.length){ Plotly.purge('chart-allocation'); return; }
          const labels = accounts.map(a=>a.name||('Acc '+a.id));
          const values = accounts.map(a=>a.value||0);
          Plotly.newPlot('chart-allocation', [{type:'pie', labels, values, hole:.5}], {title:'Allocation (by account)', margin:{t:40}});
        }

        function drawLine(ts){
          if (!ts.length){ Plotly.purge('chart-line'); return; }
          const dates = ts.map(p=>p.date);
          const navs = ts.map(p=>p.nav_total);
          const flows = ts.map(p=>p.net_flow||0);
          Plotly.newPlot('chart-line', [
            {x:dates, y:navs, mode:'lines', name:'Total NAV'},
            {x:dates, y:flows, mode:'lines', name:'Net Flow'}
          ], {title:'NAV & Flows over Time', margin:{t:40}});
        }

        loadAll();
        </script>
        </body></html>
        """
        return render_template_string(html, ingest_label=ingest_label)

    @app.post("/reingest")
    def reingest():
        with Session() as s:
            app.config["INGEST_REPORT"] = ingest_all(s, "data")
        return redirect(url_for("index"))

    # ---------- APIs used by the page (fast) ----------
    @app.get("/api/parsed_main")
    def api_parsed_main():
        # light, file-by-file raw headlines, never crash
        out = []
        from .services.ingest import detect_extractor
        for fn in sorted(os.listdir("data")):
            if not fn.lower().endswith(".pdf"):
                continue
            path = os.path.join("data", fn)
            ex = detect_extractor(path)
            if not ex:
                out.append({"file": fn, "status": "skipped", "reason": "no match"}); continue
            try:
                sm = ex.summary(path)
                out.append({"file": fn, "status": "ok", "broker": ex.name, "summary": sm})
            except Exception as e:
                out.append({"file": fn, "status": "error", "error": str(e)})
        return jsonify(out)

    @app.get("/api/kpi")
    def api_kpi():
        with Session() as s:
            # per-account XIRR using flows + terminal value
            name_map = account_names(s)
            lv = latest_valuations(s)
            accounts = []
            all_flows, total_terminal, max_date = [], 0.0, None
            for account_id, d, v in lv:
                if (max_date is None) or (d > max_date): max_date = d
                flows = s.query(CashFlowExternal).filter(CashFlowExternal.account_id == account_id).all()
                cf = [(f.date, f.amount) for f in flows] + [(d, v)]
                accounts.append({"id": account_id, "name": name_map.get(account_id, str(account_id)),
                                 "date": str(d), "value": float(v), "xirr": xirr(cf)})
                all_flows.extend(cf[:-1]); total_terminal += float(v)

            consolidated_irr = None
            if max_date is not None:
                all_flows.append((max_date, total_terminal))
                consolidated_irr = xirr(all_flows)

            # consolidated NAV series and daily flows
            nav_series = [{"date": str(d), "nav_total": float(v)} for d, v in all_valuations(s)]
            # simple bridge: earliest & latest valuation dates
            start_nav = nav_series[0]["nav_total"] if nav_series else None
            end_nav   = nav_series[-1]["nav_total"] if nav_series else None
            # net external flows between first and last date
            from datetime import date as _date
            if nav_series:
                d0 = _date.fromisoformat(nav_series[0]["date"])
                d1 = _date.fromisoformat(nav_series[-1]["date"])
                q = s.query(CashFlowExternal).filter(CashFlowExternal.date >= d0, CashFlowExternal.date <= d1).all()
                net_flows = float(sum(f.amount for f in q))
            else:
                net_flows = 0.0
            pnl = None
            if (start_nav is not None) and (end_nav is not None):
                pnl = end_nav - start_nav - net_flows

            # daily net flows for the line chart (optional, sparse if few PDFs)
            from collections import defaultdict
            flows_by_day = defaultdict(float)
            for f in s.query(CashFlowExternal).all():
                flows_by_day[str(f.date)] += float(f.amount)
            # merge into ts as a parallel series (missing dates → 0)
            ts_dates = [p["date"] for p in nav_series]
            timeseries = [{"date": d, "nav_total": next(p["nav_total"] for p in nav_series if p["date"]==d),
                           "net_flow": flows_by_day.get(d, 0.0)} for d in ts_dates]

            return jsonify({
                "consolidated_nav": float(sum(a["value"] for a in accounts)),
                "consolidated_irr": consolidated_irr,
                "accounts": accounts,
                "bridge": {"start_nav": start_nav, "net_flows": net_flows, "pnl": pnl, "end_nav": end_nav},
                "timeseries": timeseries
            })

    return app

app = create_app()
if __name__ == "__main__":
    app.run(debug=True)
