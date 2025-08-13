from __future__ import annotations
import os
from flask import Flask, request, jsonify
from .db import init_db
from .models import Base, Valuation, CashFlowExternal
from .services.ingest import ingest_file
from .services.holdings import consolidated_nav, latest_valuations
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
        with Session() as s:
            lv = latest_valuations(s)
            result = {"accounts": {}, "consolidated": None}
            all_flows = []
            total_terminal = 0.0
            max_date = None

            for account_id, d, v in lv:
                max_date = d if (max_date is None or d > max_date) else max_date
                flows = s.query(CashFlowExternal).filter(CashFlowExternal.account_id == account_id).all()
                cf = [(f.date, f.amount) for f in flows]
                cf.append((d, v))
                result["accounts"][account_id] = {"date": str(d), "value": v, "xirr": xirr(cf)}
                all_flows.extend(cf[:-1])
                total_terminal += v

            if max_date is not None:
                all_flows.append((max_date, total_terminal))
                result["consolidated"] = xirr(all_flows)

            return jsonify(result)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
