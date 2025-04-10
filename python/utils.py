from python.sqid import sqid_encode


def get_run_url(host, organization, project, run_id):
    return f"{host}/o/{organization}/projects/{project}/{sqid_encode(run_id)}"
