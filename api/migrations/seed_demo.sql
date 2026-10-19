-- Demo seed: fictional consultant workspace with one client tenant (USE-06).
-- Every person and organization here is fictional.
INSERT INTO workspace (id, name) VALUES ('b7f0cdea-983b-5c77-b9cd-9ebb25f6e874', 'Northbridge Privacy Advisors');
INSERT INTO tenant (id, workspace_id, name, approval_preset) VALUES ('ff3e39f3-ea89-5b8d-9af6-2638c94349e3', 'b7f0cdea-983b-5c77-b9cd-9ebb25f6e874', 'Harbor Staffing', 'standard');
INSERT INTO app_user (id, username, display_name, email) VALUES ('3f5423c7-2feb-5dba-a1ee-d4e2a1367f54', 'sam.rivera', 'Sam Rivera', 'sam.rivera@harbor.example');
INSERT INTO membership (tenant_id, user_id, role) VALUES ('ff3e39f3-ea89-5b8d-9af6-2638c94349e3', '3f5423c7-2feb-5dba-a1ee-d4e2a1367f54', 'submitter');
INSERT INTO app_user (id, username, display_name, email) VALUES ('63ff48e9-49dc-5f0e-baa8-dc6f9c275b07', 'olivia.grant', 'Olivia Grant', 'olivia.grant@harbor.example');
INSERT INTO membership (tenant_id, user_id, role) VALUES ('ff3e39f3-ea89-5b8d-9af6-2638c94349e3', '63ff48e9-49dc-5f0e-baa8-dc6f9c275b07', 'system_owner');
INSERT INTO app_user (id, username, display_name, email) VALUES ('261563d0-1835-5491-ba2d-147a373b9759', 'ana.patel', 'Ana Patel', 'ana.patel@northbridge.example');
INSERT INTO membership (tenant_id, user_id, role) VALUES ('ff3e39f3-ea89-5b8d-9af6-2638c94349e3', '261563d0-1835-5491-ba2d-147a373b9759', 'privacy_analyst');
INSERT INTO app_user (id, username, display_name, email) VALUES ('a8d77717-7ebf-5685-bd32-115c93ab01e3', 'ben.okafor', 'Ben Okafor', 'ben.okafor@northbridge.example');
INSERT INTO membership (tenant_id, user_id, role) VALUES ('ff3e39f3-ea89-5b8d-9af6-2638c94349e3', 'a8d77717-7ebf-5685-bd32-115c93ab01e3', 'privacy_analyst');
INSERT INTO app_user (id, username, display_name, email) VALUES ('03ab32ab-8a26-502f-8442-0e312d8a4810', 'carla.mendes', 'Carla Mendes', 'carla.mendes@harbor.example');
INSERT INTO membership (tenant_id, user_id, role) VALUES ('ff3e39f3-ea89-5b8d-9af6-2638c94349e3', '03ab32ab-8a26-502f-8442-0e312d8a4810', 'privacy_counsel');
INSERT INTO app_user (id, username, display_name, email) VALUES ('c1dcb056-f864-5447-8963-5225af8c4aff', 'devon.hart', 'Devon Hart', 'devon.hart@northbridge.example');
INSERT INTO membership (tenant_id, user_id, role) VALUES ('ff3e39f3-ea89-5b8d-9af6-2638c94349e3', 'c1dcb056-f864-5447-8963-5225af8c4aff', 'dpo');
INSERT INTO app_user (id, username, display_name, email) VALUES ('d3a42163-472b-5f19-a030-51503c00465d', 'terry.lin', 'Terry Lin', 'terry.lin@harbor.example');
INSERT INTO membership (tenant_id, user_id, role) VALUES ('ff3e39f3-ea89-5b8d-9af6-2638c94349e3', 'd3a42163-472b-5f19-a030-51503c00465d', 'tenant_admin');
INSERT INTO app_user (id, username, display_name, email) VALUES ('9a3d6f91-ca46-56b3-9cf7-3e059cc8a72c', 'wren.ellis', 'Wren Ellis', 'wren.ellis@northbridge.example');
INSERT INTO workspace_membership (workspace_id, user_id, role) VALUES ('b7f0cdea-983b-5c77-b9cd-9ebb25f6e874', '9a3d6f91-ca46-56b3-9cf7-3e059cc8a72c', 'workspace_admin');
INSERT INTO app_user (id, username, display_name, email) VALUES ('6e6ce584-dc2d-5ed7-a7bf-805ee2ec89a5', 'avery.shaw', 'Avery Shaw', 'avery.shaw@harbor.example');
INSERT INTO membership (tenant_id, user_id, role) VALUES ('ff3e39f3-ea89-5b8d-9af6-2638c94349e3', '6e6ce584-dc2d-5ed7-a7bf-805ee2ec89a5', 'auditor');
