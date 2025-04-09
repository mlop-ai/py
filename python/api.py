from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

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

    project = relationship("Project", backref="runs")

    def __repr__(self):
        return (
            f"<Run(id={self.id}, projectId={self.projectId}, "
            f"organizationId={self.organizationId}, status={self.status})>"
        )


def process_runs(session, ch_client):
    runs = session.query(Run).all()
    now_utc = datetime.now(timezone.utc)

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
        if time_diff > timedelta(minutes=10):
            print(
                f"Run {run.id} (Project: {project_name}) last metric at {last_metric_time} is older than 10 minutes."
            )
            run.status = "FAILED"
        else:
            print(
                f"Run {run.id} (Project: {project_name}) is active. Last metric at {last_metric_time}."
            )

    # Commit updates to PostgreSQL.
    session.commit()
    print("All updates committed to the database.")
