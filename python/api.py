from datetime import datetime, timedelta, timezone

from models import Member, Organization, User
from send import send_email
from sqid import sqid_encode
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
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
    name = Column(String)
    projectId = Column(Integer, ForeignKey("projects.id"))
    organizationId = Column(Integer)
    status = Column(String)
    updatedAt = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project = relationship("Project", backref="runs")

    def __repr__(self):
        return (
            f"<Run(id={self.id}, name={self.name}, projectId={self.projectId}, "
            f"organizationId={self.organizationId}, status={self.status}, "
            f"updatedAt={self.updatedAt})>"
        )


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    runId = Column(Integer, ForeignKey("runs.id"))
    organizationId = Column(String)
    createdAt = Column(DateTime(timezone=True), server_default=func.now())
    type = Column(String)
    content = Column(String)

    run = relationship("Run", backref="notifications")

    def __repr__(self):
        return (
            f"<Notification(id={self.id}, runId={self.runId}, "
            f"organizationId={self.organizationId}, type={self.type}, "
            f"content={self.content})>"
        )


def process_runs(session, ch_client, smtp_config, grace=16):
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

        # for runs with no metrics, use updatedAt time
        if last_metric_time == datetime.fromtimestamp(0, timezone.utc) and timedelta(seconds=grace) < now_utc - run.updatedAt.replace(tzinfo=timezone.utc):
            last_metric_time = run.updatedAt.replace(tzinfo=timezone.utc)
        
        time_diff = now_utc - last_metric_time
        if timedelta(seconds=grace) < time_diff < timedelta(days=16384):
            print(
                f"Run {run.id} (Project: {project_name}) last metric at {last_metric_time} is older than {grace} seconds."
            )
            run.status = "FAILED"
            session.add(
                Notification(
                    runId=run.id,
                    organizationId=run.organizationId,
                    type="RUN_FAILED",
                    content=f"Reason: last update exceeded {grace} seconds",
                )
            )
            for e in get_emails(session, run.organizationId):
                send_email(
                    smtp_config,
                    from_address=smtp_config["from_address"],
                    to_address=e,
                    subject="mlop: status update",
                    body=f"Run {run.name} (Project: {project_name}) may have stalled. The last metric was received at (UTC) {last_metric_time.strftime('%Y-%m-%d %H:%M:%S')} and has not been updated for more than {int(time_diff.total_seconds())} seconds. View the run at https://localhost/o/mlop/projects/{project_name}/{sqid_encode(run.id)}."
                )
        else:
            print(
                f"Run {run.id} (Project: {project_name}) is active. Last metric at {last_metric_time}."
            )
    session.commit()
    print("All updates saved to the database.")


def get_emails(session, organization_id):
    try:
        members = (
            session.query(User.email)
            .join(Member, Member.userId == User.id)
            .filter(Member.organizationId == organization_id)
            .all()
        )
        emails = [member[0] for member in members]
        return emails
    except Exception as e:
        print(f"Error retrieving organization emails: {e}")
        return []
