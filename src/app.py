from __future__ import annotations
import os
from flask import Flask, request, jsonify
from .db import init_db
from .models import Base
from .services.ingest import ingest_file, ingest_all, detect_extractor, EXTRACTORS
from .services.holdings import consolidated_nav, latest_valuations

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

    @app.post("/ingest_all")
    def ingestall():
        with Session() as s:
            res = ingest_all(s, "data")
            return jsonify(res)

    @app.get("/parsed_main")
    def parsed_main():
        # parse headline numbers straight from PDFs without writing to DB
        out = []
        for fn in os.listdir("data"):
            if not fn.lower().endswith(".pdf"):
                continue
            path = os.path.join("data", fn)
            ex = detect_extractor(path)
            if not ex:
                out.append({"file": fn, "status": "skipped", "reason": "no match"}); continue
            # use the extractor's side-effect-free summary
            sm = ex.summary(path)
            out.append({"file": fn, "broker": ex.name, "headline": sm})
        return jsonify(out)

    @app.get("/dashboard")
    def dashboard():
        with Session() as s:
            nav = consolidated_nav(s)
            return {"consolidated_nav": nav}

    @app.get("/kpi")
    def kpi():
        from .models import Valuation, CashFlowExternal
        from .services.kpis import xirr
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
