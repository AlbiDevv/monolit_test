import csv
import io
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .db import ROOT, connect, database_path, initialize
from .metrics import SelectionError, dashboard, document_detail

Mode = Literal["actual", "demo"]
DepartmentFilter = Annotated[list[str] | None, Query()]


def create_app(db_path: Path | None = None) -> FastAPI:
    path = db_path or database_path()

    @asynccontextmanager
    async def lifespan(_app):
        initialize(path)
        yield

    api = FastAPI(title="Дебиторская задолженность", version="1.0.0", lifespan=lifespan)

    @api.get("/api/health")
    def health():
        with connect(path) as conn:
            snapshots = conn.execute("SELECT COUNT(*) FROM snapshots WHERE mode='actual'").fetchone()[0]
        return {"status": "ok", "application": "monolit-receivables", "actual_snapshots": snapshots}

    @api.get("/api/meta")
    def metadata():
        with connect(path) as conn:
            conn.execute("BEGIN")
            departments = [dict(row) for row in conn.execute("SELECT id,name FROM departments ORDER BY id")]
            snapshots = []
            for row in conn.execute(
                "SELECT s.snapshot_date AS date,s.mode,COUNT(i.id) AS sources,"
                "GROUP_CONCAT(i.department_id) AS department_ids "
                "FROM snapshots s JOIN imports i ON i.snapshot_id=s.id "
                "GROUP BY s.id ORDER BY s.snapshot_date DESC"
            ):
                item = dict(row)
                item["departments"] = sorted(item.pop("department_ids").split(","))
                snapshots.append(item)
            organization = conn.execute("SELECT name FROM organizations ORDER BY id LIMIT 1").fetchone()
        return {"departments": departments, "snapshots": snapshots,
                "organization": organization[0] if organization else None,
                "currency_label": "Валюта управленческого учёта"}

    def load(mode, snapshot_date, department, start):
        try:
            with connect(path) as conn:
                return dashboard(conn, mode, snapshot_date, department or [], start)
        except SelectionError as exc:
            raise HTTPException(422, str(exc)) from exc

    @api.get("/api/dashboard")
    def summary(mode: Mode = "actual", snapshot_date: date | None = None,
                department: DepartmentFilter = None, start: date | None = None):
        return load(mode, snapshot_date, department, start)

    @api.get("/api/documents")
    def documents(snapshot_date: date, counterparty_id: Annotated[int, Query(gt=0, le=9223372036854775807)], mode: Mode = "actual"):
        with connect(path) as conn:
            result = document_detail(conn, mode, snapshot_date, counterparty_id)
        if not result:
            raise HTTPException(404, "Документы контрагента в выбранном срезе не найдены")
        return {"mode": mode, "snapshot_date": snapshot_date.isoformat(), "documents": result}

    @api.get("/api/export")
    def export(mode: Mode = "actual", snapshot_date: date | None = None,
               department: DepartmentFilter = None):
        result = load(mode, snapshot_date, department, None)
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(["Режим", "Срез", "Отдел", "Общая ДЗ", "Просроченная", "% просрочки",
                         "В подходе 1–5 дней", "Прогноз +1…+7 дней"])
        for row in [*result["departments"], {"name": "ИТОГО", **result["totals"]}]:
            money = [f"{row[key] // 100},{row[key] % 100:02d}" for key in ["total", "overdue"]]
            upcoming = [f"{row[key] // 100},{row[key] % 100:02d}" for key in ["expected", "forecast"]]
            writer.writerow(["Факт" if mode == "actual" else "Демонстрация", result["snapshot_date"],
                             row["name"], *money, f"{row['overdue_pct']:.2f}".replace(".", ","), *upcoming])
        filename = f"receivables-{mode}-{result['snapshot_date']}.csv"
        return Response(content="\ufeff" + buffer.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    dist = ROOT / "frontend" / "dist"
    if (dist / "assets").exists():
        api.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @api.get("/brand-logo.svg", include_in_schema=False)
    def brand_logo():
        if not (dist / "brand-logo.svg").exists():
            raise HTTPException(404, "Логотип не найден")
        return FileResponse(dist / "brand-logo.svg", media_type="image/svg+xml")

    @api.get("/")
    def frontend():
        if not (dist / "index.html").exists():
            raise HTTPException(503, "Соберите frontend командой npm run build или запустите Vite")
        return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

    return api


app = create_app()
