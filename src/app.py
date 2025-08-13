from __future__ import annotations
import os
from flask import Flask, request, jsonify
from sqlalchemy import text
from .db import init_db, SessionLocal
from .models import Base
from .services.ingest import ingest_file
from .services.holdings import consolidated_nav
from .services.kpis import xirr, nav_bridge
from datetime import date

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

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
