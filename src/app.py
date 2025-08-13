from __future__ import annotations
import os
from datetime import date
from flask import Flask, request, jsonify
from .db import init_db
from .models import Base, Valuation, CashFlowExternal
from .services.ingest import ingest_file
from .services.holdings import consolidated_nav
from .services.kpis import xirr

def create_app():
    app = Flask(__name__)
    os.makedirs("data", exist_ok=True)
    engine, Session = init_db("sqlite:///data/app.db")
    Base.metadata.create_all(bind=engine)

    @app.get("/")
    def health():
        return {"ok": True}

    @app.post("/ingest")
    def ingest():
        if "file" not in request.files:
            return {"error": "no file"}, 400
        f = request.files["file"]
        path = os.path.join("data", f.filename)
        f.save(path)
        with Session() as s:
            try:
                res = ingest_file(s, path)
                return jsonify(res)
            except Exception as e:
                s.rollback()
                return {"error": str(e)}, 400

    @app.get("/dashboard")
    def dashboard():
        with Session() as s:
            nav = consolidated_nav(s)
            return {"consolidated_nav": nav}

    @app.get("/kpi")
    def kpi():
        # Per-account IRR and consolidated IRR (based on latest valuations + external flows).
        with Session() as s:
            # Latest valuations per account
            latest = (
                s.query(Valuation.account_id, Valuation.date, Valuation.total_value)
                .from_statement(
                    # Use a window function to pick latest per account
                    # (SQLite 3.25+ supports window functions)
                    # fallback approach would be a subquery group-by
                    # Here we just do the subquery approach for simplicity:
                    # SELECT account_id, MAX(date) ... then join back.
                    # Implemented in services.holdings.latest_valuations already, but we inline to return dates too.
                    # For simplicity, reuse that later; keeping it explicit here.
                    # NOTE: For SQLite compatibility, we keep it simple in code below.
                    # We'll use a python-side reduce.
                    text("")
                )
            )
            # Fallback simple approach:
            vals = s.query(Valuation).all()
            by_acct = {}
            for v in vals:
                if (v.account_id not in by_acct) or (v.date > by_acct[v.account_id].date):
                    by_acct[v.account_id] = v

            # Build cashflows and compute per-account XIRR
            result = {"accounts": {}, "consolidated": None}
            all_flows = []
            total_terminal = 0.0
            max_date = None

            for acc_id, v in by_acct.items():
                max_date = v.date if (max_date is None or v.date > max_date) else max_date
                # Gather external flows for this account
                flows = s.query(CashFlowExternal).filter(CashFlowExternal.account_id == acc_id).all()
                cf = [(f.date, f.amount) for f in flows]
                # Add terminal value cash flow (positive)
                cf.append((v.date, v.total_value))
                irr = xirr(cf)
                result["accounts"][acc_id] = {"date": str(v.date), "value": v.total_value, "xirr": irr}
                # For consolidated IRR, aggregate flows and terminal value
                all_flows.extend(cf[:-1])  # exclude per-account terminal now; add a single consolidated terminal later
                total_terminal += v.total_value

            if max_date is not None:
                all_flows.append((max_date, total_terminal))
                result["consolidated"] = xirr(all_flows)

            return jsonify(result)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
