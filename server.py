import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from compat.migrate import get_client, list_runs, migrate_all, migrate_run_v1
from python.models import Run, RunStatus, RunTriggers, RunTriggerType

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_DIRECT_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# TODO: add auth


@app.post("/api/runs/triggers")
async def get_run_triggers(
    runId: int = Body(..., embed=True), db: Session = Depends(get_db)
):
    run = db.query(Run).filter(Run.id == runId).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if not run.status == RunStatus.CANCELLED:
        triggers = db.query(RunTriggers).filter(RunTriggers.runId == runId).all()
        for trigger in triggers:
            if trigger.triggerType == RunTriggerType.CANCEL:
                run.status = RunStatus.CANCELLED
                run.statusUpdated = datetime.now(timezone.utc)
                db.commit()
                db.refresh(run)

    return {
        "status": run.status,
        "triggers": [
            {
                "trigger": trigger.trigger,
            }
            for trigger in triggers
        ]
        if (False and triggers is not None)
        else None,
    }


@app.post("/api/compat/w/viewer")  # TODO: protect
async def _viewer(key: str = Body(..., embed=True)):
    c = get_client(key)
    return c.viewer()


@app.post("/api/compat/w/list-runs")
async def _list_runs(
    auth: str = Body(..., embed=True),
    key: str = Body(..., embed=True),
    entity: str = Body(..., embed=True),
):
    c = get_client(key)
    return list_runs(c, entity)


@app.post("/api/compat/w/migrate-all")
async def _migrate_all(
    auth: str = Body(..., embed=True),
    key: str = Body(..., embed=True),
    entity: str = Body(..., embed=True),
):
    if migrate_all(auth, key, entity):
        return {"status": "success"}
    else:
        raise HTTPException(status_code=500, detail="Failed to migrate runs")


@app.post("/api/compat/w/migrate-run")
async def _migrate_run(
    auth: str = Body(..., embed=True),
    key: str = Body(..., embed=True),
    entity: str = Body(..., embed=True),
    project: str = Body(..., embed=True),
    run: str = Body(..., embed=True),
):
    c = get_client(key)
    if migrate_run_v1(auth, c, entity, project, run):
        return {"status": "success"}
    else:
        raise HTTPException(status_code=500, detail="Failed to migrate run")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3004)
