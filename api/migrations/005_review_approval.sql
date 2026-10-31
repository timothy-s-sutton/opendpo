-- 005_review_approval: review and approval of assessments (PLT-30 to PLT-35, SOD-1, SOD-2,
-- WF-16, WF-20, WF-22). An assessment is submitted for review as a fixed snapshot; each
-- review round's decisions are kept; approval names the people, their positions and the date.

ALTER TABLE assessment DROP CONSTRAINT assessment_status_check;
ALTER TABLE assessment ADD CONSTRAINT assessment_status_check
    CHECK (status IN ('draft', 'in_review', 'returned', 'approved', 'rejected', 'superseded'));

ALTER TABLE assessment
    ADD COLUMN review_round     integer NOT NULL DEFAULT 0,
    ADD COLUMN routing_level    text CHECK (routing_level IN ('low', 'medium', 'high')),
    ADD COLUMN submitted_by     uuid REFERENCES app_user(id),
    ADD COLUMN submitted_at     timestamptz,
    ADD COLUMN submitted_digest text,             -- sha256 of every section as submitted
    ADD COLUMN approved_at      timestamptz,
    ADD COLUMN next_review_due  date;             -- WF-22

CREATE TABLE assessment_approval (
    id                        bigserial PRIMARY KEY,
    tenant_id                 uuid NOT NULL REFERENCES tenant(id),
    assessment_id             uuid NOT NULL REFERENCES assessment(id),
    review_round              integer NOT NULL,
    step                      text NOT NULL CHECK (step IN ('provisional', 'final')),
    role                      text NOT NULL,      -- the role the person acted in
    user_id                   uuid NOT NULL REFERENCES app_user(id),
    decision                  text NOT NULL CHECK (decision IN ('approve', 'return', 'reject')),
    note                      text,
    has_initiation_authority  boolean NOT NULL DEFAULT false,   -- § 7152(a)(9)
    self_approval_reason      text,               -- PLT-34, single-person office only
    submitted_digest          text NOT NULL,      -- what exactly was approved
    decided_at                timestamptz NOT NULL DEFAULT now(),
    CHECK (decision = 'approve' OR note IS NOT NULL)
);

CREATE FUNCTION assessment_approval_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'approval decisions are a record (PLT-32)';
END $$;
CREATE TRIGGER assessment_approval_no_change BEFORE UPDATE OR DELETE ON assessment_approval
    FOR EACH ROW EXECUTE FUNCTION assessment_approval_immutable();

ALTER TABLE assessment_approval ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON assessment_approval USING (tenant_id = current_tenant())
    WITH CHECK (tenant_id = current_tenant());
GRANT SELECT, INSERT ON assessment_approval TO opendpo_app;
GRANT USAGE ON SEQUENCE assessment_approval_id_seq TO opendpo_app;
