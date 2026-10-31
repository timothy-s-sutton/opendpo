-- 004_inventory_policies: the data inventory (INV-01 to INV-06, INV-09), tenant copies of
-- policies with structured, versioned positions (PLT-12, PLT-13, PLT-19), job titles for the
-- report's named contributors and approvers (§ 7152(a)(8)-(9)), and the links an assessment
-- needs to them. Transfers are optional in v1 and not built for the preview.

-- § 7152(a)(8)-(9): reports name people with their positions.
ALTER TABLE app_user ADD COLUMN job_title text;

-- ---------------------------------------------------------------------------
-- Inventory
-- ---------------------------------------------------------------------------

CREATE TABLE vendor (
    id            uuid PRIMARY KEY,
    tenant_id     uuid NOT NULL REFERENCES tenant(id),
    name          text NOT NULL,
    role          text NOT NULL CHECK (role IN ('service_provider', 'contractor', 'third_party', 'processor')),
    dpa_status    text NOT NULL CHECK (dpa_status IN ('signed', 'in_negotiation', 'none')),
    locations     jsonb NOT NULL DEFAULT '[]',
    notes         text
);

CREATE TABLE system (
    id               uuid PRIMARY KEY,
    tenant_id        uuid NOT NULL REFERENCES tenant(id),
    name             text NOT NULL,
    business_owner   text NOT NULL,
    technical_owner  text,
    origin           text NOT NULL CHECK (origin IN ('vendor', 'in_house')),
    vendor_id        uuid REFERENCES vendor(id),
    hosting          text,
    locations        jsonb NOT NULL DEFAULT '[]',
    sensitivity      text NOT NULL CHECK (sensitivity IN ('low', 'moderate', 'high')),
    status           text NOT NULL CHECK (status IN ('planned', 'testing', 'live', 'retired')),
    CHECK (origin = 'in_house' OR vendor_id IS NOT NULL)
);

-- INV-05: separate from systems, since one model can sit behind several systems.
CREATE TABLE ai_component (
    id                        uuid PRIMARY KEY,
    tenant_id                 uuid NOT NULL REFERENCES tenant(id),
    name                      text NOT NULL,
    origin                    text NOT NULL CHECK (origin IN ('vendor', 'in_house')),
    kind                      text NOT NULL CHECK (kind IN ('traditional_model', 'llm')),
    vendor_id                 uuid REFERENCES vendor(id),
    version                   text,
    intended_use              text NOT NULL,
    inputs                    text NOT NULL,
    output                    text NOT NULL,
    trained_on_personal_data  boolean NOT NULL,
    known_limitations         text,
    CHECK (origin = 'in_house' OR vendor_id IS NOT NULL)
);

CREATE TABLE system_ai_component (
    tenant_id        uuid NOT NULL REFERENCES tenant(id),
    system_id        uuid NOT NULL REFERENCES system(id),
    ai_component_id  uuid NOT NULL REFERENCES ai_component(id),
    PRIMARY KEY (system_id, ai_component_id)
);

CREATE TABLE data_category (
    id               uuid PRIMARY KEY,
    tenant_id        uuid NOT NULL REFERENCES tenant(id),
    name             text NOT NULL,
    examples         text,
    sensitive        boolean NOT NULL,          -- sensitive personal information
    ccpa_category    text,
    gdpr_special     boolean NOT NULL DEFAULT false,
    retention        text NOT NULL              -- a period, or how it is decided
);

CREATE TABLE data_subject_group (
    id                 uuid PRIMARY KEY,
    tenant_id          uuid NOT NULL REFERENCES tenant(id),
    name               text NOT NULL,
    approximate_count  integer,
    jurisdictions      jsonb NOT NULL DEFAULT '[]'
);

-- INV-01: the processing activity is the centre of the inventory. How AI takes part in
-- the decision is recorded here, on the use, not on the system.
CREATE TABLE processing_activity (
    id                uuid PRIMARY KEY,
    tenant_id         uuid NOT NULL REFERENCES tenant(id),
    name              text NOT NULL,
    purpose           text NOT NULL,           -- specific, not generic (§ 7152(a)(1))
    legal_basis       text,                    -- GDPR only; empty for US-only processing
    decision_domain   text,
    ai_role           text CHECK (ai_role IN ('none', 'assists', 'materially_influences', 'decides')),
    -- INV-06: none; limited (a person looks, but not every part of meaningful review is met);
    -- meaningful (understands the output, weighs other information, can change the outcome).
    human_review      text CHECK (human_review IN ('none', 'limited', 'meaningful')),
    human_review_note text,
    people_affected   jsonb NOT NULL DEFAULT '{}',  -- INV-09: by jurisdiction and population
    collection        text,                         -- how information is collected, and from where
    consumer_interaction text,                      -- how people interact with the business, and why
    disclosures       text,                         -- what people are told, and how
    go_live           date,
    stage             text CHECK (stage IN ('idea', 'design', 'testing', 'live', 'live_with_change', 'retired'))
);

CREATE TABLE activity_system (
    tenant_id    uuid NOT NULL REFERENCES tenant(id),
    activity_id  uuid NOT NULL REFERENCES processing_activity(id),
    system_id    uuid NOT NULL REFERENCES system(id),
    PRIMARY KEY (activity_id, system_id)
);

CREATE TABLE activity_ai_component (
    tenant_id        uuid NOT NULL REFERENCES tenant(id),
    activity_id      uuid NOT NULL REFERENCES processing_activity(id),
    ai_component_id  uuid NOT NULL REFERENCES ai_component(id),
    PRIMARY KEY (activity_id, ai_component_id)
);

CREATE TABLE activity_data_category (
    tenant_id         uuid NOT NULL REFERENCES tenant(id),
    activity_id       uuid NOT NULL REFERENCES processing_activity(id),
    data_category_id  uuid NOT NULL REFERENCES data_category(id),
    why_needed        text,                    -- § 7152(a)(2): the minimum necessary
    PRIMARY KEY (activity_id, data_category_id)
);

CREATE TABLE activity_subject_group (
    tenant_id     uuid NOT NULL REFERENCES tenant(id),
    activity_id   uuid NOT NULL REFERENCES processing_activity(id),
    group_id      uuid NOT NULL REFERENCES data_subject_group(id),
    PRIMARY KEY (activity_id, group_id)
);

CREATE TABLE activity_recipient (
    tenant_id     uuid NOT NULL REFERENCES tenant(id),
    activity_id   uuid NOT NULL REFERENCES processing_activity(id),
    vendor_id     uuid NOT NULL REFERENCES vendor(id),
    purpose       text NOT NULL,               -- § 7152(a)(3)(F): why they receive it
    PRIMARY KEY (activity_id, vendor_id)
);

-- ---------------------------------------------------------------------------
-- Policies: each tenant's own copy of a template, versioned (PLT-13, PLT-19)
-- ---------------------------------------------------------------------------

CREATE TABLE policy (
    id           uuid PRIMARY KEY,
    tenant_id    uuid NOT NULL REFERENCES tenant(id),
    template_id  text,                         -- the OpenDPO template it came from, if any
    title        text NOT NULL,
    UNIQUE (tenant_id, template_id)
);

CREATE TABLE policy_version (
    id                 uuid PRIMARY KEY,
    tenant_id          uuid NOT NULL REFERENCES tenant(id),
    policy_id          uuid NOT NULL REFERENCES policy(id),
    version            integer NOT NULL CHECK (version >= 1),
    template_version   text,
    sections           jsonb NOT NULL,
    status             text NOT NULL CHECK (status IN ('proposed', 'confirmed', 'retired')),
    proposed_by        uuid REFERENCES app_user(id),
    confirmed_by       uuid REFERENCES app_user(id),
    confirmed_at       timestamptz,
    effective_from     date,
    UNIQUE (policy_id, version),
    -- SOD-3: whoever proposed a policy change cannot confirm it.
    CHECK (confirmed_by IS NULL OR proposed_by IS NULL OR confirmed_by <> proposed_by),
    CHECK (status <> 'confirmed' OR (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL))
);

CREATE TABLE policy_position (
    id                 uuid PRIMARY KEY,
    tenant_id          uuid NOT NULL REFERENCES tenant(id),
    policy_version_id  uuid NOT NULL REFERENCES policy_version(id),
    position_key       text NOT NULL,          -- e.g. POS-AI-002, stable across versions
    section            text,
    type               text NOT NULL CHECK (type IN ('requirement', 'prohibition', 'threshold',
                           'approval_rule', 'default', 'conditional_permission')),
    statement          text NOT NULL,
    applies_to         jsonb NOT NULL DEFAULT '{}',
    parameters         jsonb NOT NULL DEFAULT '{}',
    framework_refs     jsonb NOT NULL DEFAULT '[]',
    UNIQUE (policy_version_id, position_key)
);

-- A policy version's content and positions never change once written; a change is a new version.
CREATE FUNCTION policy_version_content_fixed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'policy versions are kept (PLT-13)';
    END IF;
    IF NEW.sections IS DISTINCT FROM OLD.sections OR NEW.version IS DISTINCT FROM OLD.version
       OR NEW.policy_id IS DISTINCT FROM OLD.policy_id OR NEW.proposed_by IS DISTINCT FROM OLD.proposed_by
       OR NEW.template_version IS DISTINCT FROM OLD.template_version THEN
        RAISE EXCEPTION 'a policy version cannot be edited; propose a new version instead (PLT-13)';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER policy_version_content_fixed BEFORE UPDATE OR DELETE ON policy_version
    FOR EACH ROW EXECUTE FUNCTION policy_version_content_fixed();

CREATE FUNCTION policy_position_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'policy positions belong to a fixed policy version (PLT-13)';
END $$;
CREATE TRIGGER policy_position_no_change BEFORE UPDATE OR DELETE ON policy_position
    FOR EACH ROW EXECUTE FUNCTION policy_position_immutable();

-- ---------------------------------------------------------------------------
-- What an assessment covers and was made with
-- ---------------------------------------------------------------------------

ALTER TABLE assessment ADD COLUMN processing_activity_id uuid REFERENCES processing_activity(id);
ALTER TABLE assessment ADD COLUMN policy_versions jsonb NOT NULL DEFAULT '[]';

CREATE OR REPLACE FUNCTION assessment_basis_fixed() RETURNS trigger LANGUAGE plpgsql AS $$
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
       OR NEW.processing_activity_id IS DISTINCT FROM OLD.processing_activity_id
       OR NEW.policy_versions IS DISTINCT FROM OLD.policy_versions
       OR NEW.created_by IS DISTINCT FROM OLD.created_by THEN
        RAISE EXCEPTION 'what an assessment was made with cannot change; start a new assessment instead';
    END IF;
    RETURN NEW;
END $$;

-- ---------------------------------------------------------------------------
-- Row-level security and grants
-- ---------------------------------------------------------------------------

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['vendor', 'system', 'ai_component', 'system_ai_component', 'data_category',
                             'data_subject_group', 'processing_activity', 'activity_system',
                             'activity_ai_component', 'activity_data_category', 'activity_subject_group',
                             'activity_recipient', 'policy', 'policy_version', 'policy_position'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY tenant_isolation ON %I USING (tenant_id = current_tenant()) '
                       'WITH CHECK (tenant_id = current_tenant())', t);
        EXECUTE format('GRANT SELECT, INSERT ON %I TO opendpo_app', t);
    END LOOP;
END $$;

-- Inventory records are kept current, so the app may update them; policy versions only
-- change status (the trigger above keeps their content fixed).
GRANT UPDATE ON vendor, system, ai_component, data_category, data_subject_group, processing_activity,
    activity_data_category, activity_recipient, policy_version TO opendpo_app;
