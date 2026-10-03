PW = "SuperSecret123"


def register(client, org, email):
    r = client.post("/auth/register-organization", json={
        "organization_name": org, "owner_name": "Owner", "email": email, "password": PW})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_register_login_me(client):
    h = register(client, "Alpha Builders", "a@alpha.pk")
    assert client.get("/users/me", headers=h).json()["role_name"] == "OWNER"
    r = client.post("/auth/login", json={"email": "a@alpha.pk", "password": PW})
    assert r.status_code == 200
    assert client.post("/auth/login", json={"email": "a@alpha.pk", "password": "wrongpassword1"}).status_code == 401


def test_requires_auth(client):
    assert client.get("/users").status_code == 401


def test_tenant_isolation(client):
    ha = register(client, "Alpha", "a@alpha.pk")
    hb = register(client, "Beta", "b@beta.pk")
    client.post("/users", headers=ha, json={"email": "eng@alpha.pk", "full_name": "Eng A",
                                            "password": PW, "role_name": "SITE_ENGINEER"})
    a_emails = {u["email"] for u in client.get("/users", headers=ha).json()}
    b_emails = {u["email"] for u in client.get("/users", headers=hb).json()}
    assert a_emails == {"a@alpha.pk", "eng@alpha.pk"}
    assert b_emails == {"b@beta.pk"}
    # org A audit log never contains org B events
    assert all(e["action"] for e in client.get("/audit-logs", headers=ha).json())


def test_rbac_denies_site_engineer(client):
    ha = register(client, "Alpha", "a@alpha.pk")
    client.post("/users", headers=ha, json={"email": "eng@alpha.pk", "full_name": "Eng A",
                                            "password": PW, "role_name": "SITE_ENGINEER"})
    tok = client.post("/auth/login", json={"email": "eng@alpha.pk", "password": PW}).json()["access_token"]
    he = {"Authorization": f"Bearer {tok}"}
    assert client.get("/users", headers=he).status_code == 403
    assert client.get("/audit-logs", headers=he).status_code == 403
    assert client.post("/users", headers=he, json={"email": "x@alpha.pk", "full_name": "X Y",
                                                   "password": PW, "role_name": "WORKER"}).status_code == 403


def test_cannot_use_role_from_other_org_and_refresh_revocation(client):
    ha = register(client, "Alpha", "a@alpha.pk")
    tokens = client.post("/auth/login", json={"email": "a@alpha.pk", "password": PW}).json()
    assert client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": tokens["access_token"]}).status_code == 401
    client.post("/auth/logout-all", headers=ha)
    assert client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_audit_records_login_failure(client):
    h = register(client, "Alpha", "a@alpha.pk")
    client.post("/auth/login", json={"email": "a@alpha.pk", "password": "wrongpassword1"})
    actions = [(e["action"], e["result"]) for e in client.get("/audit-logs", headers=h).json()]
    assert ("auth.login", "failure") in actions
