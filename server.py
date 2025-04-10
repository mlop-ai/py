import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

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

@app.post("/api/runs/triggers/{run_id}")
async def get_run_triggers(run_id: int, db: Session = Depends(get_db)):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if not run.status == RunStatus.CANCELLED:
        triggers = db.query(RunTriggers).filter(RunTriggers.runId == run_id).all()
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
        ] if (False and triggers is not None) else None,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
