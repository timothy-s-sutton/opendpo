-- 001_core: tenancy, memberships and the tamper-evident audit log.
-- Runs as opendpo_owner. The API connects as opendpo_app, which has no
-- BYPASSRLS, so row-level security applies to every query it makes.

CREATE TABLE workspace (
    id          uuid PRIMARY KEY,
    name        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tenant (
    id              uuid PRIMARY KEY,
    workspace_id    uuid NOT NULL REFERENCES workspace(id),
    name            text NOT NULL,
    -- PLT-09: standard, lean or single-person office
    approval_preset text NOT NULL DEFAULT 'standard'
        CHECK (approval_preset IN ('standard', 'lean', 'single_person')),
    intended_use_ack_at  timestamptz,
    intended_use_ack_by  uuid,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Users are identities from Keycloak; id is the token's "sub" claim.
CREATE TABLE app_user (
    id            uuid PRIMARY KEY,
    username      text NOT NULL UNIQUE,
    display_name  text NOT NULL,
    email         text NOT NULL
);

-- PLT-04: roles live on memberships, not on users.
CREATE TABLE membership (
    tenant_id  uuid NOT NULL REFERENCES tenant(id),
    user_id    uuid NOT NULL REFERENCES app_user(id),
    role       text NOT NULL CHECK (role IN (
                   'submitter', 'system_owner', 'privacy_analyst', 'privacy_counsel',
                   'dpo', 'tenant_admin', 'auditor')),
    granted_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, user_id, role)
);

CREATE TABLE workspace_membership (
    workspace_id  uuid NOT NULL REFERENCES workspace(id),
    user_id       uuid NOT NULL REFERENCES app_user(id),
    role          text NOT NULL CHECK (role IN ('workspace_admin')),
    PRIMARY KEY (workspace_id, user_id, role)
);

-- PLT-40, PLT-41: append-only, hash-chained per tenant.
CREATE TABLE audit_event (
    id               bigserial PRIMARY KEY,
    tenant_id        uuid NOT NULL REFERENCES tenant(id),
    seq              bigint NOT NULL,
    occurred_at      timestamptz NOT NULL,
    actor_type       text NOT NULL CHECK (actor_type IN ('user', 'agent', 'system')),
    actor_id         text NOT NULL,
    actor_roles      text[] NOT NULL DEFAULT '{}',
    on_behalf_of     text,          -- SOD-6: the user who triggered an agent action
    action           text NOT NULL,
    object_type      text,
    object_id        text,
    payload          jsonb NOT NULL DEFAULT '{}',
    content_versions jsonb NOT NULL DEFAULT '{}',
    prev_hash        char(64) NOT NULL,
    hash             char(64) NOT NULL,
    UNIQUE (tenant_id, seq)
);

-- SOD-5: no one edits or deletes audit events, the owner included.
CREATE FUNCTION audit_event_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_event is append-only (SOD-5)';
END $$;

CREATE TRIGGER audit_event_no_update BEFORE UPDATE OR DELETE ON audit_event
    FOR EACH ROW EXECUTE FUNCTION audit_event_immutable();
CREATE TRIGGER audit_event_no_truncate BEFORE TRUNCATE ON audit_event
    FOR EACH STATEMENT EXECUTE FUNCTION audit_event_immutable();

-- PLT-01: tenant isolation in the database engine.
ALTER TABLE tenant      ENABLE ROW LEVEL SECURITY;
ALTER TABLE membership  ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_event ENABLE ROW LEVEL SECURITY;

CREATE FUNCTION current_tenant() RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT nullif(current_setting('app.tenant_id', true), '')::uuid
$$;

CREATE POLICY tenant_isolation ON tenant      USING (id = current_tenant());
CREATE POLICY tenant_isolation ON membership  USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());
CREATE POLICY tenant_isolation ON audit_event USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

-- A user's own memberships across tenants, needed before a tenant is chosen.
CREATE FUNCTION my_memberships(p_user uuid)
RETURNS TABLE (tenant_id uuid, tenant_name text, workspace_id uuid, role text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT m.tenant_id, t.name, t.workspace_id, m.role
    FROM membership m JOIN tenant t ON t.id = m.tenant_id
    WHERE m.user_id = p_user
    ORDER BY t.name, m.role
$$;

GRANT SELECT ON workspace, app_user, workspace_membership TO opendpo_app;
GRANT SELECT, UPDATE ON tenant TO opendpo_app;
GRANT SELECT, INSERT, DELETE ON membership TO opendpo_app;
GRANT SELECT, INSERT ON audit_event TO opendpo_app;
GRANT USAGE ON SEQUENCE audit_event_id_seq TO opendpo_app;
GRANT EXECUTE ON FUNCTION my_memberships(uuid), current_tenant() TO opendpo_app;
