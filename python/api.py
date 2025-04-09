from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    name = Column(String)

    def __repr__(self):
        return f"<Project(id={self.id}, name={self.name})>"


class Run(Base):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True)
    projectId = Column(Integer, ForeignKey("projects.id"))
    organizationId = Column(Integer)
    status = Column(String)
    updatedAt = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", backref="runs")

    def __repr__(self):
        return (
            f"<Run(id={self.id}, projectId={self.projectId}, "
            f"organizationId={self.organizationId}, status={self.status}, "
            f"updatedAt={self.updatedAt})>"
        )


def process_runs(session, ch_client, grace=16):
    now_utc = datetime.now(timezone.utc)
    runs = session.query(Run).all()

    runs = [r for r in runs if r.status == "RUNNING"]
    for run in runs:
        if not run.project:
            print(f"Run {run.id} has no associated project.")
            continue

        project_name = run.project.name
        ch_query = """
            SELECT MAX(time) AS last_metric_time
            FROM mlop_metrics
            WHERE projectName = %(projectName)s
              AND runId = %(runId)s
              AND tenantId = %(tenantId)s
        """
        ch_params = {
            "projectName": project_name,
            "runId": run.id,
            "tenantId": run.organizationId,
        }
        try:
            result = ch_client.query(ch_query, parameters=ch_params)
        except Exception as e:
            print(f"Error querying ClickHouse for run {run.id}: {e}")
            continue

        if not result.result_rows or result.result_rows[0][0] is None:
            print(f"No metric data for run {run.id}.")
            continue

        last_metric_time = result.result_rows[0][0]
        if isinstance(last_metric_time, str):
            try:
                last_metric_time = datetime.fromisoformat(last_metric_time)
            except ValueError as e:
                print(f"Error parsing metric time for run {run.id}: {e}")
                continue
        if last_metric_time.tzinfo is None:
            last_metric_time = last_metric_time.replace(tzinfo=timezone.utc)

        time_diff = now_utc - last_metric_time
        if timedelta(seconds=grace) < time_diff < timedelta(days=16384) or (
            # for runs with no metrics, use updatedAt time
            last_metric_time == datetime.fromtimestamp(0, timezone.utc) and timedelta(seconds=grace) < now_utc - run.updatedAt.replace(tzinfo=timezone.utc)
        ):
            print(
                f"Run {run.id} (Project: {project_name}) last metric at {last_metric_time} is older than 10 minutes."
            )
            run.status = "FAILED"
        else:
            print(
                f"Run {run.id} (Project: {project_name}) is active. Last metric at {last_metric_time}."
            )
    session.commit()
    print("All updates saved to the database.")
