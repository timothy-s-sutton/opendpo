-- 003_assessment: the AI and ADMT risk assessment (WF-11, WF-15, WF-19, WF-20).
-- An assessment is opened from a confirmed triage run. Its content is kept as section
-- revisions that are never edited: the agent's draft is revision 1 and each reviewer
-- change adds one, so every edit stays visible against the original (WF-15).

CREATE TABLE assessment (
    id                   uuid PRIMARY KEY,
    tenant_id            uuid NOT NULL REFERENCES tenant(id),
    project_id           uuid NOT NULL REFERENCES project(id),
    triage_run_id        uuid NOT NULL REFERENCES triage_run(id),
    assessment_type      text NOT NULL,                  -- e.g. ccpa_risk_assessment, from triage
    -- What the assessment was made with (CNT-02, PLT-13). Fixed once created.
    template_id          text NOT NULL,
    template_version     integer NOT NULL,
    methodology          jsonb NOT NULL,                 -- a copy of the method as used
    content_versions     jsonb NOT NULL,
    -- C5: the triage category sets a floor for approval routing.
    routing_floor        text NOT NULL CHECK (routing_floor IN ('low', 'medium', 'high')),
    floor_rules          jsonb NOT NULL DEFAULT '[]',
    status               text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'in_review', 'returned', 'approved', 'superseded')),
    -- WF-20: the DPO's formal risk acceptances, recorded by the approval steps.
    risk_acceptances     jsonb NOT NULL DEFAULT '[]',
    created_by           uuid NOT NULL REFERENCES app_user(id),
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (triage_run_id, assessment_type)
);

CREATE TABLE assessment_revision (
    id              bigserial PRIMARY KEY,
    tenant_id       uuid NOT NULL REFERENCES tenant(id),
    assessment_id   uuid NOT NULL REFERENCES assessment(id),
    section         text NOT NULL,
    revision        integer NOT NULL CHECK (revision >= 1),
    body            jsonb NOT NULL,
    author_type     text NOT NULL CHECK (author_type IN ('user', 'agent')),
    author_id       text NOT NULL,                      -- a user id, or the agent's system identity
    on_behalf_of    uuid REFERENCES app_user(id),       -- SOD-6: who asked the agent
    note            text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (assessment_id, section, revision),
    CHECK (author_type = 'user' OR on_behalf_of IS NOT NULL)
);

-- Revisions are a record: no edits, no deletes.
CREATE FUNCTION assessment_revision_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'assessment_revision is append-only (WF-15)';
END $$;
CREATE TRIGGER assessment_revision_no_change BEFORE UPDATE OR DELETE ON assessment_revision
    FOR EACH ROW EXECUTE FUNCTION assessment_revision_immutable();

-- What an assessment was made with never changes, and assessments are kept (WF-24).
CREATE FUNCTION assessment_basis_fixed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'assessments are kept (WF-24)';
    END IF;
    IF NEW.project_id IS DISTINCT FROM OLD.project_id OR NEW.triage_run_id IS DISTINCT FROM OLD.triage_run_id
       OR NEW.assessment_type IS DISTINCT FROM OLD.assessment_type
       OR NEW.template_id IS DISTINCT FROM OLD.template_id
       OR NEW.template_version IS DISTINCT FROM OLD.template_version
       OR NEW.methodology IS DISTINCT FROM OLD.methodology
       OR NEW.content_versions IS DISTINCT FROM OLD.content_versions
       OR NEW.routing_floor IS DISTINCT FROM OLD.routing_floor
       OR NEW.floor_rules IS DISTINCT FROM OLD.floor_rules
       OR NEW.created_by IS DISTINCT FROM OLD.created_by THEN
        RAISE EXCEPTION 'what an assessment was made with cannot change; start a new assessment instead';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER assessment_basis_fixed BEFORE UPDATE OR DELETE ON assessment
    FOR EACH ROW EXECUTE FUNCTION assessment_basis_fixed();

ALTER TABLE assessment          ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_revision ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON assessment          USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());
CREATE POLICY tenant_isolation ON assessment_revision USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

GRANT SELECT, INSERT, UPDATE ON assessment TO opendpo_app;
GRANT SELECT, INSERT ON assessment_revision TO opendpo_app;
GRANT USAGE ON SEQUENCE assessment_revision_id_seq TO opendpo_app;
