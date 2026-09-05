BEGIN;
CREATE SCHEMA IF NOT EXISTS bi;

CREATE OR REPLACE VIEW bi.dim_company AS
SELECT id AS company_id, name AS company_name
FROM res_company;

CREATE OR REPLACE VIEW bi.dim_department AS
SELECT
 d.id AS department_id,
 COALESCE(d.name->>'fr_FR',d.name->>'en_US',d.name->>'en_GB',TRIM(BOTH '"' FROM d.name::text)) AS department_name,
 d.manager_id,
 m.name AS manager_name,
 d.company_id,
 c.name AS company_name,
 CASE WHEN COALESCE(d.active,TRUE) THEN 1 ELSE 0 END AS active
FROM hr_department d
LEFT JOIN hr_employee m ON m.id=d.manager_id
LEFT JOIN res_company c ON c.id=d.company_id;

CREATE OR REPLACE VIEW bi.dim_employee AS
SELECT
 e.id AS employee_id,
 e.name AS employee_name,
 e.department_id,
 COALESCE(d.name->>'fr_FR',d.name->>'en_US',d.name->>'en_GB',TRIM(BOTH '"' FROM d.name::text)) AS department_name,
 COALESCE(e.parent_id,d.manager_id) AS manager_id,
 COALESCE(pm.name,dm.name) AS manager_name,
 e.company_id,
 c.name AS company_name,
 e.user_id,
 e.zkteco_user_id,
 e.active
FROM hr_employee e
LEFT JOIN hr_department d ON d.id=e.department_id
LEFT JOIN hr_employee pm ON pm.id=e.parent_id
LEFT JOIN hr_employee dm ON dm.id=d.manager_id
LEFT JOIN res_company c ON c.id=e.company_id;

CREATE OR REPLACE VIEW bi.fact_travel_request AS
SELECT
 r.id AS request_id,
 r.name AS reference,
 r.date_from AS request_date,
 DATE_TRUNC('month',r.date_from)::date AS month_start,
 EXTRACT(YEAR FROM r.date_from)::int AS year,
 EXTRACT(MONTH FROM r.date_from)::int AS month_number,
 TO_CHAR(r.date_from,'YYYY-MM') AS month_label,
 r.employee_id,
 e.name AS employee_name,
 r.department_id,
 COALESCE(d.name->>'fr_FR',d.name->>'en_US',TRIM(BOTH '"' FROM d.name::text)) AS department_name,
 r.manager_id,
 m.name AS manager_name,
 COALESCE(e.company_id,d.company_id) AS company_id,
 c.name AS company_name,
 r.destination,
 r.date_from,
 r.date_to,
 r.duration_days,
 r.estimated_cost,
 r.state,
 CASE r.state WHEN 'draft' THEN 'Brouillon' WHEN 'submitted' THEN 'Soumis' WHEN 'approved' THEN 'ApprouvÃ©' WHEN 'rejected' THEN 'RefusÃ©' WHEN 'done' THEN 'TerminÃ©' ELSE r.state END AS state_label,
 CASE WHEN r.state IN ('approved','done') THEN 1 ELSE 0 END AS is_approved,
 CASE WHEN r.state='submitted' THEN 1 ELSE 0 END AS is_pending,
 r.create_date,
 r.write_date
FROM hr_travel_request r
LEFT JOIN hr_employee e ON e.id=r.employee_id
LEFT JOIN hr_department d ON d.id=r.department_id
LEFT JOIN hr_employee m ON m.id=r.manager_id
LEFT JOIN res_company c ON c.id=COALESCE(e.company_id,d.company_id);

CREATE OR REPLACE VIEW bi.fact_supply_request AS
SELECT
 r.id AS request_id,
 r.name AS reference,
 r.create_date::date AS request_date,
 DATE_TRUNC('month',r.create_date)::date AS month_start,
 EXTRACT(YEAR FROM r.create_date)::int AS year,
 EXTRACT(MONTH FROM r.create_date)::int AS month_number,
 TO_CHAR(r.create_date,'YYYY-MM') AS month_label,
 r.employee_id,
 e.name AS employee_name,
 r.department_id,
 COALESCE(d.name->>'fr_FR',d.name->>'en_US',TRIM(BOTH '"' FROM d.name::text)) AS department_name,
 r.manager_id,
 m.name AS manager_name,
 r.company_id,
 c.name AS company_name,
 r.item_name,
 INITCAP(TRIM(r.item_name)) AS item_name_normalized,
 r.quantity,
 r.estimated_cost,
 CASE WHEN r.quantity<>0 THEN r.estimated_cost/r.quantity ELSE 0 END AS estimated_unit_cost,
 r.state,
 CASE r.state WHEN 'draft' THEN 'Brouillon' WHEN 'submitted' THEN 'Soumis' WHEN 'approved' THEN 'ApprouvÃ©' WHEN 'rejected' THEN 'RefusÃ©' WHEN 'done' THEN 'TerminÃ©' ELSE r.state END AS state_label,
 CASE WHEN r.state IN ('approved','done') THEN 1 ELSE 0 END AS is_approved,
 CASE WHEN r.state='submitted' THEN 1 ELSE 0 END AS is_pending,
 r.create_date,
 r.write_date
FROM hr_supply_request r
LEFT JOIN hr_employee e ON e.id=r.employee_id
LEFT JOIN hr_department d ON d.id=r.department_id
LEFT JOIN hr_employee m ON m.id=r.manager_id
LEFT JOIN res_company c ON c.id=r.company_id;

CREATE OR REPLACE VIEW bi.fact_attestation_request AS
SELECT
 r.id AS request_id,
 r.name AS reference,
 r.request_date,
 DATE_TRUNC('month',r.request_date)::date AS month_start,
 EXTRACT(YEAR FROM r.request_date)::int AS year,
 EXTRACT(MONTH FROM r.request_date)::int AS month_number,
 TO_CHAR(r.request_date,'YYYY-MM') AS month_label,
 r.employee_id,
 e.name AS employee_name,
 r.department_id,
 COALESCE(d.name->>'fr_FR',d.name->>'en_US',TRIM(BOTH '"' FROM d.name::text)) AS department_name,
 COALESCE(e.company_id,d.company_id) AS company_id,
 c.name AS company_name,
 r.attestation_type,
 CASE r.attestation_type WHEN 'work' THEN 'Travail' WHEN 'salary' THEN 'Salaire' WHEN 'internship' THEN 'Stage' WHEN 'other' THEN 'Autre' ELSE r.attestation_type END AS attestation_type_label,
 r.state,
 CASE r.state WHEN 'draft' THEN 'Brouillon' WHEN 'submitted' THEN 'Soumis' WHEN 'approved' THEN 'ApprouvÃ©' WHEN 'rejected' THEN 'RefusÃ©' WHEN 'done' THEN 'TerminÃ©' ELSE r.state END AS state_label,
 CASE WHEN r.state IN ('approved','done') THEN 1 ELSE 0 END AS is_approved,
 r.create_date,
 r.write_date
FROM hr_attestation_request r
LEFT JOIN hr_employee e ON e.id=r.employee_id
LEFT JOIN hr_department d ON d.id=r.department_id
LEFT JOIN res_company c ON c.id=COALESCE(e.company_id,d.company_id);

CREATE OR REPLACE VIEW bi.fact_hr_activity AS
SELECT 'TR-'||request_id AS activity_key, request_id, 'travel' AS activity_type, 'DÃ©placement' AS activity_type_label, reference, request_date, month_start, employee_id, employee_name, department_id, department_name, company_id, company_name, state, state_label, estimated_cost AS amount, 1::double precision AS quantity
FROM bi.fact_travel_request
UNION ALL
SELECT 'SR-'||request_id, request_id, 'supply', 'Fourniture', reference, request_date, month_start, employee_id, employee_name, department_id, department_name, company_id, company_name, state, state_label, estimated_cost, quantity
FROM bi.fact_supply_request
UNION ALL
SELECT 'AT-'||request_id, request_id, 'attestation', 'Attestation', reference, request_date, month_start, employee_id, employee_name, department_id, department_name, company_id, company_name, state, state_label, 0::double precision, 1::double precision
FROM bi.fact_attestation_request;

CREATE OR REPLACE VIEW bi.fact_attendance AS
SELECT
 a.id AS attendance_id,
 a.employee_id,
 e.name AS employee_name,
 e.department_id,
 COALESCE(d.name->>'fr_FR',d.name->>'en_US',TRIM(BOTH '"' FROM d.name::text)) AS department_name,
 e.company_id,
 c.name AS company_name,
 a.check_in::date AS attendance_date,
 DATE_TRUNC('month',a.check_in)::date AS month_start,
 TO_CHAR(a.check_in,'YYYY-MM') AS month_label,
 a.check_in,
 a.check_out,
 a.worked_hours,
 a.overtime_hours,
 CASE WHEN a.zkteco_managed THEN 1 ELSE 0 END AS zkteco_managed,
 COALESCE(a.zkteco_late_minutes,0) AS late_minutes,
 COALESCE(a.zkteco_early_departure_minutes,0) AS early_departure_minutes,
 a.zkteco_status,
 CASE a.zkteco_status WHEN 'on_time' THEN 'Ã€ l''heure' WHEN 'late' THEN 'En retard' WHEN 'early' THEN 'DÃ©part anticipÃ©' WHEN 'late_early' THEN 'Retard et dÃ©part anticipÃ©' ELSE 'Non classÃ©' END AS status_label,
 CASE WHEN COALESCE(a.zkteco_late_minutes,0)>0 THEN 1 ELSE 0 END AS is_late,
 CASE WHEN COALESCE(a.zkteco_early_departure_minutes,0)>0 THEN 1 ELSE 0 END AS is_early,
 CASE WHEN a.worked_hours<6 THEN 1 ELSE 0 END AS is_short_day,
 CASE WHEN a.overtime_hours>0 THEN 1 ELSE 0 END AS is_overtime,
 CASE WHEN a.check_out IS NULL THEN 'Sortie manquante' WHEN a.worked_hours<6 THEN 'JournÃ©e courte' WHEN COALESCE(a.zkteco_late_minutes,0)>0 OR COALESCE(a.zkteco_early_departure_minutes,0)>0 THEN 'Anomalie horaire' ELSE 'Conforme' END AS quality_label,
 a.create_date,
 a.write_date
FROM hr_attendance a
LEFT JOIN hr_employee e ON e.id=a.employee_id
LEFT JOIN hr_department d ON d.id=e.department_id
LEFT JOIN res_company c ON c.id=e.company_id;

CREATE OR REPLACE VIEW bi.fact_zkteco_log AS
SELECT
 l.id AS log_id,
 l.employee_id,
 e.name AS employee_name,
 e.department_id,
 COALESCE(d.name->>'fr_FR',d.name->>'en_US',TRIM(BOTH '"' FROM d.name::text)) AS department_name,
 l.company_id,
 c.name AS company_name,
 l.device_user_id,
 l.punch_datetime,
 l.punch_datetime::date AS punch_date,
 DATE_TRUNC('month',l.punch_datetime)::date AS month_start,
 l.punch_type,
 CASE l.punch_type WHEN 'check_in' THEN 'EntrÃ©e' WHEN 'check_out' THEN 'Sortie' ELSE 'Inconnu' END AS punch_type_label,
 l.device_name,
 l.device_serial,
 l.state,
 CASE l.state WHEN 'raw' THEN 'Brut' WHEN 'mapped' THEN 'EmployÃ© identifiÃ©' WHEN 'processed' THEN 'TraitÃ©' WHEN 'error' THEN 'Erreur' ELSE l.state END AS state_label,
 CASE WHEN l.state='error' OR l.error_message IS NOT NULL THEN 1 ELSE 0 END AS has_error,
 CASE WHEN l.state='processed' THEN 1 ELSE 0 END AS is_processed,
 l.attendance_id,
 l.create_date
FROM hr_attendance_device_log l
LEFT JOIN hr_employee e ON e.id=l.employee_id
LEFT JOIN hr_department d ON d.id=e.department_id
LEFT JOIN res_company c ON c.id=l.company_id;

CREATE OR REPLACE VIEW bi.fact_onboarding_message AS
SELECT
 m.id AS message_id,
 m.conversation_id,
 conv.user_id,
 conv.employee_id,
 e.name AS employee_name,
 e.department_id,
 COALESCE(d.name->>'fr_FR',d.name->>'en_US',TRIM(BOTH '"' FROM d.name::text)) AS department_name,
 e.company_id,
 c.name AS company_name,
 m.role,
 CASE m.role WHEN 'user' THEN 'Utilisateur' WHEN 'assistant' THEN 'Assistant' ELSE m.role END AS role_label,
 m.confidence_score,
 m.latency_ms,
 CASE WHEN m.cache_hit THEN 1 ELSE 0 END AS cache_hit,
 m.feedback,
 CASE m.feedback WHEN 'helpful' THEN 'Utile' WHEN 'not_helpful' THEN 'Pas utile' ELSE 'Sans avis' END AS feedback_label,
 CASE WHEN m.needs_escalation THEN 1 ELSE 0 END AS needs_escalation,
 m.escalated_at,
 m.create_date::date AS message_date,
 DATE_TRUNC('month',m.create_date)::date AS month_start,
 m.create_date
FROM hr_onboarding_message m
JOIN hr_onboarding_conversation conv ON conv.id=m.conversation_id
LEFT JOIN hr_employee e ON e.id=conv.employee_id
LEFT JOIN hr_department d ON d.id=e.department_id
LEFT JOIN res_company c ON c.id=e.company_id;

CREATE OR REPLACE VIEW bi.fact_onboarding_document AS
SELECT
 doc.id AS document_id,
 doc.name AS document_name,
 doc.category,
 CASE doc.category WHEN 'welcome' THEN 'Accueil' WHEN 'policy' THEN 'Politique interne' WHEN 'benefits' THEN 'Avantages' WHEN 'safety' THEN 'SantÃ© et sÃ©curitÃ©' WHEN 'it' THEN 'Informatique' ELSE 'Autre' END AS category_label,
 doc.language,
 UPPER(doc.language) AS language_label,
 doc.company_id,
 c.name AS company_name,
 doc.department_id,
 COALESCE(d.name->>'fr_FR',d.name->>'en_US',TRIM(BOTH '"' FROM d.name::text)) AS department_name,
 doc.visibility,
 CASE doc.visibility WHEN 'employee' THEN 'Tous les employÃ©s' WHEN 'department' THEN 'DÃ©partement' WHEN 'manager' THEN 'Managers' WHEN 'hr' THEN 'RH uniquement' ELSE doc.visibility END AS visibility_label,
 doc.version,
 doc.indexing_state,
 CASE doc.indexing_state WHEN 'pending' THEN 'En attente' WHEN 'processing' THEN 'En cours' WHEN 'indexed' THEN 'IndexÃ©' WHEN 'error' THEN 'Erreur' ELSE doc.indexing_state END AS indexing_state_label,
 doc.indexed_at,
 CASE WHEN doc.active THEN 1 ELSE 0 END AS active,
 doc.create_date
FROM hr_onboarding_document doc
LEFT JOIN res_company c ON c.id=doc.company_id
LEFT JOIN hr_department d ON d.id=doc.department_id;

COMMIT;
