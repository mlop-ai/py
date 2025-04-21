from datetime import datetime, timedelta, timezone

from python.models import Member, Notification, Organization, Run, User
from python.send import send_email
from python.sqid import sqid_encode
from python.temp import process_run_email
from python.utils import get_run_url


def process_runs(session, ch_client, smtp_config, grace=60):
    now_utc = datetime.now(timezone.utc)
    runs = session.query(Run).filter(Run.status == "RUNNING").all()
    print(f"Processing {len(runs)} runs")
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
        if last_metric_time == datetime.fromtimestamp(0, timezone.utc) and timedelta(
            seconds=grace
        ) < now_utc - run.updatedAt.replace(tzinfo=timezone.utc):
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
                    body=process_run_email(
                        run_name="test-run",
                        project_name="examples",
                        last_metric_time=datetime.utcnow().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        time_diff_seconds=int(timedelta(datetime.now(timezone.utc) - last_metric_time).total_seconds()),
                        run_url=get_run_url(
                            host=smtp_config["app_host"],
                            organization=run.organization.slug,
                            project=project_name,
                            run_id=run.id,
                        ),
                        reason="The run may have stalled and requires attention.",
                    ),
                    html=True,
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
