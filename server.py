import os
from datetime import datetime, timezone
from typing import Union

import docker
from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, Header, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from compat.migrate import get_client, list_runs, migrate_all, migrate_run_v1
from python.env import get_database_url, get_smtp_config
from python.docker import start_server, stop_server, stop_all
from python.models import Run, RunStatus, RunTriggers, RunTriggerType
from python.server import check_run, send_alert, check_api_key

load_dotenv()

SMTP_CONFIG = get_smtp_config()
DATABASE_URL = get_database_url()
DOMAIN = os.getenv("W_DOMAIN", "localhost")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

client = docker.from_env()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/api/docker/start")
async def start_docker(
    authorization: str = Header(None),
    session: Session = Depends(get_db),
):
    api_key = check_api_key(session, authorization.replace("Bearer ", ""))
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    port, password, url, private_key, ssh_port = start_server(client)
    cmd = f"echo -e '{private_key}' > id_ed25519; chmod 600 id_ed25519; ssh -i id_ed25519 -p {ssh_port} mlop@{os.getenv('D_DOMAIN', 'localhost')}"
    return {"port": port, "password": password, "url": url, "cmd": cmd}  # "key": private_key


@app.post("/api/docker/stop")
async def stop_docker(
    port: int = Body(..., embed=True),
    authorization: str = Header(None),
    session: Session = Depends(get_db),
):
    api_key = check_api_key(session, authorization.replace("Bearer ", ""))
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    try:
        stop_server(client, int(port))
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to stop server: {e}")


@app.post("/api/docker/stop-all")
async def stop_all_docker(
    authorization: str = Header(None),
    session: Session = Depends(get_db),
):
    api_key = check_api_key(session, authorization.replace("Bearer ", ""))
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    try:
        stop_all(client)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to stop all servers: {e}")


@app.post("/api/runs/trigger")
async def get_run_triggers(
    runId: int = Body(..., embed=True),
    session: Session = Depends(get_db),
    authorization: str = Header(None),
):
    run = check_api_key(authorization)

    if not run.status == RunStatus.CANCELLED:
        triggers = session.query(RunTriggers).filter(
            RunTriggers.runId == runId).all()
        for trigger in triggers:
            if trigger.triggerType == RunTriggerType.CANCEL:
                run.status = RunStatus.CANCELLED
                run.statusUpdated = datetime.now(timezone.utc)
                session.commit()
                session.refresh(run)

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


@app.post("/api/runs/alert")
async def set_run_alerts(
    runId: int = Body(..., embed=True),
    alert: dict[str, Union[str, int, bool, None]] = Body(..., embed=True),
    session: Session = Depends(get_db),
    authorization: str = Header(None),
):
    run = check_run(session, runId, authorization)

    if not isinstance(alert, dict):  # TODO: add more checks
        raise HTTPException(status_code=400, detail="Invalid alert")

    try:
        send_alert(
            session,
            run,
            SMTP_CONFIG,
            last_update_time=datetime.fromtimestamp(
                alert.get("timestamp") / 1000, tz=timezone.utc
            )
            if alert.get("timestamp")
            else datetime.now(timezone.utc),
            title=alert.get("title", "Status Update"),
            body=alert.get("body", "alert"),
            level=alert.get("level", "INFO"),
            email=alert.get("email", True),
        )

        if alert.get("url"):
            # TODO: add webhook support
            raise HTTPException(status_code=302, detail=alert.get("url"))
        else:
            return {"status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to send alert: {e}")


@app.post("/api/compat/w/viewer")  # TODO: protect
async def _viewer(key: str = Body(..., embed=True)):
    c = get_client(key, DOMAIN)
    return c.viewer()


@app.post("/api/compat/w/list-runs")
async def _list_runs(
    auth: str = Body(..., embed=True),
    key: str = Body(..., embed=True),
    entity: str = Body(..., embed=True),
):
    c = get_client(key, DOMAIN)
    return list_runs(c, entity)


@app.post("/api/compat/w/migrate-all")
async def _migrate_all(
    auth: str = Body(..., embed=True),
    key: str = Body(..., embed=True),
    entity: str = Body(..., embed=True),
):
    if migrate_all(auth, key, entity, DOMAIN):
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
    c = get_client(key, DOMAIN)
    if migrate_run_v1(auth, c, entity, project, run):
        return {"status": "success"}
    else:
        raise HTTPException(status_code=500, detail="Failed to migrate run")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3004)
