"""The Overview page's task list: each person sees the work waiting on them, and only work they
are allowed to do."""
from .conftest import HARBOR, as_user
from .test_agent import fixture_provider, harms_signed, opened  # noqa: F401  (fixtures)
from .test_assessment import FIXTURE, rules_loaded  # noqa: F401
from .test_review import act, decide_to_go_ahead, drafted  # noqa: F401

BASE = f"/api/tenants/{HARBOR}"


def tasks(client, who):
    r = client.get(f"{BASE}/tasks", headers=as_user(who))
    assert r.status_code == 200, r.text
    return r.json()


def has(t, group, key, value):
    return any(i[key] == value for g in t["groups"] if g["id"] == group for i in g["items"])


def test_tasks_follow_the_walkthrough(client, drafted):  # noqa: F811
    aid = drafted
    assert has(tasks(client, "ana.patel"), "in_progress", "assessment_id", aid)
    assert not has(tasks(client, "sam.rivera"), "in_progress", "assessment_id", aid)   # cannot edit it

    decide_to_go_ahead(client, aid)
    client.post(f"{BASE}/assessments/{aid}/submit", json={}, headers=as_user("ana.patel"))
    # Devon and Carla each see it; Ana, who prepared it, and Ben, not on the final step, do not.
    for who in ("devon.hart", "carla.mendes"):
        t = tasks(client, who)
        assert has(t, "approve", "assessment_id", aid)
        assert t["groups"][0]["title"] == "Risk assessments awaiting your approval"
    for who in ("ana.patel", "ben.okafor"):
        assert not has(tasks(client, who), "approve", "assessment_id", aid)

    # Once Devon approves, it leaves his list and stays on Carla's.
    act(client, aid, "devon.hart", has_initiation_authority=True)
    assert not has(tasks(client, "devon.hart"), "approve", "assessment_id", aid)
    assert has(tasks(client, "carla.mendes"), "approve", "assessment_id", aid)

    # Returned: back on Ana's list, with Carla's note.
    act(client, aid, "carla.mendes", "return", note="Name the bias auditor.")
    t = tasks(client, "ana.patel")
    item = next(i for g in t["groups"] if g["id"] == "returned" for i in g["items"] if i["assessment_id"] == aid)
    assert item["detail"] == "Carla Mendes: Name the bias auditor."
    assert not has(tasks(client, "carla.mendes"), "approve", "assessment_id", aid)


def test_intake_and_triage_tasks(client, rules_loaded):  # noqa: F811
    pid = client.post(f"{BASE}/projects", json={"answers": FIXTURE["answers"]},
                      headers=as_user("sam.rivera")).json()["id"]
    assert has(tasks(client, "sam.rivera"), "intake", "project_id", pid)
    assert not has(tasks(client, "ana.patel"), "intake", "project_id", pid)        # not hers
    run = client.post(f"{BASE}/projects/{pid}/submit", headers=as_user("sam.rivera")).json()["triage_run"]
    assert has(tasks(client, "ana.patel"), "triage", "project_id", pid)
    assert not has(tasks(client, "sam.rivera"), "triage", "project_id", pid)
    client.post(f"{BASE}/projects/{pid}/triage/{run}/decision", json={"decision": "confirm"},
                headers=as_user("ana.patel"))
    t = tasks(client, "ana.patel")
    assert has(t, "start", "project_id", pid) and not has(t, "triage", "project_id", pid)
