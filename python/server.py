from datetime import datetime, timedelta, timezone

from python.models import Member, Notification, Organization, Run, RunStatus, User
from python.send import send_email
from python.sqid import sqid_encode
from python.temp import process_run_email
from python.utils import get_run_url


def process_runs(session, ch_client, smtp_config, grace=60):
    runs = session.query(Run).filter(Run.status == "RUNNING").all()
    print(f"Processing {len(runs)} runs")
    for run in runs:
        if not run.project:
            print(f"Run {run.id} has no associated project.")
            continue
        check_run_time(session, ch_client, smtp_config, run, grace)
        if run.loggerSettings.get("trigger"):  # TODO: clean before parsing
            for k, v in run.loggerSettings["trigger"].items():
                if v.get("operator") and isinstance(k, str):
                    check_threshold(
                        session,
                        ch_client,
                        smtp_config,
                        run,
                        log_name=k,
                        threshold=v.get("threshold"),
                        operator=v.get("operator"),
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


def check_threshold(
    session, ch_client, smtp_config, run, log_name, threshold, operator=">="
):
    if not (operator in ["<", "<=", ">", ">="] and isinstance(threshold, (int, float))):
        print(f"Invalid operator: {operator}")
        return False
    project_name = run.project.name

    ch_query = f"""
        SELECT time AS last_metric_time, value
        FROM mlop_metrics
        WHERE projectName = %(projectName)s
            AND runId = %(runId)s
            AND tenantId = %(tenantId)s
            AND logName = %(logName)s
            AND value {operator} %(threshold)s
        ORDER BY time DESC
        LIMIT 1
    """

    ch_params = {
        "projectName": project_name,
        "runId": run.id,
        "tenantId": run.organizationId,
        "logName": log_name,
        "threshold": threshold,
    }

    try:
        result = ch_client.query(ch_query, parameters=ch_params)
    except Exception as e:
        print(f"Error querying ClickHouse for run {run.id} threshold check: {e}")
        return None

    if not result.result_rows or result.result_rows[0][0] is None:
        print(f"No threshold violation found for run {run.id} on {log_name}.")
        return None

    last_metric_time = result.result_rows[0][0]
    violation_value = result.result_rows[0][1]

    if isinstance(last_metric_time, str):
        try:
            last_metric_time = datetime.fromisoformat(last_metric_time)
        except ValueError as e:
            print(f"Error parsing metric time for run {run.id}: {e}")
            return None

    if last_metric_time.tzinfo is None:
        last_metric_time = last_metric_time.replace(tzinfo=timezone.utc)

    print(
        f"Run {run.id} (Project: {project_name}) {log_name} value {violation_value} {operator} {threshold} at {last_metric_time}."
    )

    run.status = RunStatus.CANCELLED  # run.status = "FAILED"
    session.add(
        Notification(
            runId=run.id,
            organizationId=run.organizationId,
            type="RUN_FAILED",
            content=f"Reason: {log_name} value {violation_value} {operator} {threshold}",
        )
    )

    for e in get_emails(session, run.organizationId):
        send_email(
            smtp_config,
            from_address=smtp_config["from_address"],
            to_address=e,
            subject=f"mlop: threshold on {log_name} exceeded for run {run.name} in {project_name}",
            body=process_run_email(
                run_name=run.name,
                project_name=project_name,
                last_metric_time=last_metric_time.strftime("%Y-%m-%d %H:%M:%S"),
                time_diff_seconds=int(
                    (datetime.now(timezone.utc) - last_metric_time).total_seconds()
                ),
                run_url=get_run_url(
                    host=smtp_config["app_host"],
                    organization=run.organization.slug,
                    project=project_name,
                    run_id=run.id,
                ),
                reason=f"Threshold exceeded for {log_name}: {violation_value} {operator} {threshold}.",
            ),
            html=True,
        )

    return True


def check_run_time(session, ch_client, smtp_config, run, grace=60):
    now_utc = datetime.now(timezone.utc)
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
        return None

    if not result.result_rows or result.result_rows[0][0] is None:
        print(f"No metric data for run {run.id}.")
        return None

    last_metric_time = result.result_rows[0][0]
    if isinstance(last_metric_time, str):
        try:
            last_metric_time = datetime.fromisoformat(last_metric_time)
        except ValueError as e:
            print(f"Error parsing metric time for run {run.id}: {e}")
            return None
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
                    run_name=run.name,
                    project_name=project_name,
                    last_metric_time=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    time_diff_seconds=int(
                        timedelta(
                            datetime.now(timezone.utc) - last_metric_time
                        ).total_seconds()
                    ),
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
    return True
