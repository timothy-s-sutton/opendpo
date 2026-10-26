-- 002_intake_triage: projects, structured intake answers, triage runs and the
-- analyst's confirmation (WF-01 to WF-08). Every table is tenant-scoped with RLS.

-- Scoping answers are given once per tenant (the full scoping questionnaire
-- comes in v1; the demo tenant's answers are seeded).
CREATE TABLE tenant_scoping (
    tenant_id   uuid PRIMARY KEY REFERENCES tenant(id),
    answers     jsonb NOT NULL DEFAULT '{}',
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  uuid REFERENCES app_user(id)
);

CREATE TABLE project (
    id             uuid PRIMARY KEY,
    tenant_id      uuid NOT NULL REFERENCES tenant(id),
    name           text NOT NULL,
    -- draft: being filled in; awaiting_clarification: an analyst must settle the
    -- AI question first (WF-08); triaged: rules have run, waiting for an analyst
    -- (WF-06); confirmed: an analyst confirmed or changed the result.
    status         text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'awaiting_clarification', 'triaged', 'confirmed')),
    answers        jsonb NOT NULL DEFAULT '{}',      -- the working copy (WF-04)
    clarification  text,                              -- the analyst's open question, if any
    created_by     uuid NOT NULL REFERENCES app_user(id),
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

-- Each submission is kept as it was sent; later edits make a new version.
CREATE TABLE intake_submission (
    id                bigserial PRIMARY KEY,
    tenant_id         uuid NOT NULL REFERENCES tenant(id),
    project_id        uuid NOT NULL REFERENCES project(id),
    version           integer NOT NULL,
    answers           jsonb NOT NULL,
    scoping           jsonb NOT NULL,
    form_version      integer NOT NULL,
    submitted_by      uuid NOT NULL REFERENCES app_user(id),
    submitted_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, version)
);

CREATE TABLE triage_run (
    id                uuid PRIMARY KEY,
    tenant_id         uuid NOT NULL REFERENCES tenant(id),
    project_id        uuid NOT NULL REFERENCES project(id),
    submission_id     bigint NOT NULL REFERENCES intake_submission(id),
    facts             jsonb NOT NULL,                 -- answers plus scoping, as evaluated
    result            jsonb NOT NULL,                 -- what the rules decided, with citations
    content_versions  jsonb NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    status            text NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'confirmed', 'superseded')),
    -- WF-06: the analyst's decision. Changes are kept beside the rules' result,
    -- never written over it.
    decision          jsonb,
    decided_by        uuid REFERENCES app_user(id),
    decided_at        timestamptz
);

-- Submissions are a record: no edits, no deletes.
CREATE FUNCTION intake_submission_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'intake_submission is append-only (WF-04)';
END $$;
CREATE TRIGGER intake_submission_no_change BEFORE UPDATE OR DELETE ON intake_submission
    FOR EACH ROW EXECUTE FUNCTION intake_submission_immutable();

-- A triage run's rules result never changes; only its status and the analyst's decision do.
CREATE FUNCTION triage_run_result_fixed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'triage runs are kept (WF-06)';
    END IF;
    IF NEW.facts IS DISTINCT FROM OLD.facts OR NEW.result IS DISTINCT FROM OLD.result
       OR NEW.content_versions IS DISTINCT FROM OLD.content_versions
       OR NEW.submission_id IS DISTINCT FROM OLD.submission_id THEN
        RAISE EXCEPTION 'a triage result cannot be edited; record a decision instead (WF-06)';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER triage_run_fixed BEFORE UPDATE OR DELETE ON triage_run
    FOR EACH ROW EXECUTE FUNCTION triage_run_result_fixed();

ALTER TABLE tenant_scoping    ENABLE ROW LEVEL SECURITY;
ALTER TABLE project           ENABLE ROW LEVEL SECURITY;
ALTER TABLE intake_submission ENABLE ROW LEVEL SECURITY;
ALTER TABLE triage_run        ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON tenant_scoping    USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());
CREATE POLICY tenant_isolation ON project           USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());
CREATE POLICY tenant_isolation ON intake_submission USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());
CREATE POLICY tenant_isolation ON triage_run        USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());

GRANT SELECT, INSERT, UPDATE ON tenant_scoping TO opendpo_app;
GRANT SELECT, INSERT, UPDATE ON project TO opendpo_app;
GRANT SELECT, INSERT ON intake_submission TO opendpo_app;
GRANT USAGE ON SEQUENCE intake_submission_id_seq TO opendpo_app;
GRANT SELECT, INSERT, UPDATE ON triage_run TO opendpo_app;
