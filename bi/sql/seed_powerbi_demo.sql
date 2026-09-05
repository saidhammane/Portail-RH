-- Jeu de donnees analytique dedie a Power BI.
-- Base cible recommandee: portail_rh_powerbi.
-- Script idempotent: les lignes BI sont supprimees puis recreees.
BEGIN;

CREATE TEMP TABLE bi_demo_employees ON COMMIT DROP AS
SELECT
    e.id AS employee_id,
    e.user_id,
    e.department_id,
    COALESCE(e.company_id, 1) AS company_id,
    d.manager_id,
    ROW_NUMBER() OVER (ORDER BY e.id) AS rn
FROM hr_employee e
JOIN hr_department d ON d.id = e.department_id
WHERE COALESCE(d.name->>'fr_FR', d.name->>'en_US') IN (
    'Ressources Humaines',
    'Informatique',
    'Finance et Comptabilite'
)
AND e.user_id IS NOT NULL
AND e.active IS TRUE;

DELETE FROM hr_attendance_device_log
WHERE device_serial = 'BI-DEMO-01';

DELETE FROM hr_attendance
WHERE zkteco_managed IS TRUE
  AND create_uid = 2
  AND check_in >= TIMESTAMP '2025-09-01 00:00:00';

DELETE FROM hr_attestation_request WHERE name LIKE 'BI-ATT-%';
DELETE FROM hr_supply_request WHERE name LIKE 'BI-SRQ-%';
DELETE FROM hr_travel_request WHERE name LIKE 'BI-TR-%';
DELETE FROM hr_onboarding_message
WHERE content LIKE '[BI DEMO]%';

DELETE FROM hr_onboarding_conversation c
WHERE c.user_id IN (SELECT user_id FROM bi_demo_employees)
  AND c.started_at >= TIMESTAMP '2025-09-01 00:00:00'
  AND NOT EXISTS (
      SELECT 1 FROM hr_onboarding_message m
      WHERE m.conversation_id = c.id
  );

DELETE FROM hr_onboarding_document WHERE name LIKE 'BI-%';
DELETE FROM ir_attachment WHERE name LIKE 'BI-%';

WITH months AS (
    SELECT
        month_start::date,
        ROW_NUMBER() OVER (ORDER BY month_start) - 1 AS month_index
    FROM generate_series(
        DATE '2025-09-01',
        DATE '2026-08-01',
        INTERVAL '1 month'
    ) month_start
), travel_rows AS (
    SELECT
        m.month_start,
        m.month_index,
        e.*,
        ((m.month_index + e.rn)::integer % 6) + 1 AS destination_index,
        ((m.month_index * 3 + e.rn)::integer % 4) + 1 AS duration_value,
        ((m.month_index * 7 + e.rn)::integer % 20) + 2 AS day_offset,
        (m.month_index * 11 + e.rn)::integer AS state_seed
    FROM months m
    CROSS JOIN bi_demo_employees e
    WHERE MOD(m.month_index + e.rn, 2) = 0
)
INSERT INTO hr_travel_request (
    name, employee_id, department_id, manager_id,
    destination, date_from, date_to, duration_days,
    purpose, estimated_cost, state,
    create_uid, write_uid, create_date, write_date
)
SELECT
    'BI-TR-' || TO_CHAR(month_start, 'YYYYMM') || '-' || LPAD(rn::text, 2, '0'),
    employee_id,
    department_id,
    manager_id,
    (ARRAY['Casablanca','Rabat','Marrakech','Tanger','Agadir','Fes'])[destination_index],
    month_start + day_offset,
    month_start + day_offset + duration_value - 1,
    duration_value,
    'Mission client et coordination operationnelle',
    ROUND((650 + MOD(month_index * 317 + rn * 233, 4300))::numeric, 2),
    CASE
        WHEN MOD(state_seed, 12) IN (0, 1) THEN 'draft'
        WHEN MOD(state_seed, 12) IN (2, 3) THEN 'submitted'
        WHEN MOD(state_seed, 12) = 4 THEN 'rejected'
        WHEN MOD(state_seed, 12) IN (5, 6) THEN 'approved'
        ELSE 'done'
    END,
    user_id, user_id,
    month_start + GREATEST(day_offset - 8, 1),
    month_start + day_offset
FROM travel_rows;
WITH months AS (
    SELECT
        month_start::date,
        ROW_NUMBER() OVER (ORDER BY month_start) - 1 AS month_index
    FROM generate_series(
        DATE '2025-09-01',
        DATE '2026-08-01',
        INTERVAL '1 month'
    ) month_start
), supply_rows AS (
    SELECT
        m.month_start,
        m.month_index,
        e.*,
        ((m.month_index * 2 + e.rn)::integer % 8) + 1 AS item_index,
        ((m.month_index + e.rn * 3)::integer % 8) + 1 AS quantity_value,
        ((m.month_index * 5 + e.rn)::integer % 19) + 2 AS day_offset,
        (m.month_index * 13 + e.rn)::integer AS state_seed
    FROM months m
    CROSS JOIN bi_demo_employees e
)
INSERT INTO hr_supply_request (
    name, employee_id, department_id, manager_id, company_id,
    item_name, description, quantity, estimated_cost, reason, state,
    create_uid, write_uid, create_date, write_date
)
SELECT
    'BI-SRQ-' || TO_CHAR(month_start, 'YYYYMM') || '-' || LPAD(rn::text, 2, '0'),
    employee_id,
    department_id,
    manager_id,
    company_id,
    (ARRAY[
        'Ordinateur portable','Ecran 24 pouces','Clavier','Souris USB',
        'Casque audio','Ramette papier','Cartouche imprimante','Chaise ergonomique'
    ])[item_index],
    'Besoin operationnel du departement',
    quantity_value,
    ROUND((quantity_value * (ARRAY[7200,1900,320,180,650,55,480,2400])[item_index])::numeric, 2),
    'Renouvellement ou equipement collaborateur',
    CASE
        WHEN MOD(state_seed, 15) = 0 THEN 'draft'
        WHEN MOD(state_seed, 15) IN (1, 2) THEN 'submitted'
        WHEN MOD(state_seed, 15) = 3 THEN 'rejected'
        WHEN MOD(state_seed, 15) IN (4, 5, 6) THEN 'approved'
        ELSE 'done'
    END,
    user_id, user_id,
    month_start + GREATEST(day_offset - 5, 1),
    month_start + day_offset
FROM supply_rows;
WITH months AS (
    SELECT
        month_start::date,
        ROW_NUMBER() OVER (ORDER BY month_start) - 1 AS month_index
    FROM generate_series(
        DATE '2025-09-01',
        DATE '2026-08-01',
        INTERVAL '1 month'
    ) month_start
), attestation_rows AS (
    SELECT
        m.month_start,
        m.month_index,
        e.*,
        ((m.month_index + e.rn)::integer % 4) + 1 AS type_index,
        ((m.month_index * 3 + e.rn)::integer % 18) + 2 AS day_offset,
        (m.month_index * 17 + e.rn)::integer AS state_seed
    FROM months m
    CROSS JOIN bi_demo_employees e
    WHERE MOD(m.month_index + e.rn, 3) = 0
)
INSERT INTO hr_attestation_request (
    name, employee_id, department_id, attestation_type,
    request_date, reason, state,
    create_uid, write_uid, create_date, write_date
)
SELECT
    'BI-ATT-' || TO_CHAR(month_start, 'YYYYMM') || '-' || LPAD(rn::text, 2, '0'),
    employee_id,
    department_id,
    (ARRAY['work','salary','internship','other'])[type_index],
    month_start + day_offset,
    CASE type_index
        WHEN 1 THEN 'Justificatif administratif'
        WHEN 2 THEN 'Dossier bancaire ou logement'
        WHEN 3 THEN 'Dossier de formation'
        ELSE 'Besoin administratif specifique'
    END,
    CASE
        WHEN MOD(state_seed, 10) = 0 THEN 'draft'
        WHEN MOD(state_seed, 10) IN (1, 2) THEN 'submitted'
        WHEN MOD(state_seed, 10) = 3 THEN 'rejected'
        WHEN MOD(state_seed, 10) IN (4, 5) THEN 'approved'
        ELSE 'done'
    END,
    user_id,
    user_id,
    month_start + GREATEST(day_offset - 2, 1),
    month_start + day_offset
FROM attestation_rows;

-- Presences synthetiques sur six mois ouvrables.
WITH workdays AS (
    SELECT day_value::date AS workday
    FROM generate_series(
        DATE '2026-03-01',
        DATE '2026-08-31',
        INTERVAL '1 day'
    ) day_value
    WHERE EXTRACT(ISODOW FROM day_value) BETWEEN 1 AND 5
), attendance_base AS (
    SELECT
        e.employee_id,
        e.company_id,
        w.workday,
        (MOD(e.employee_id * 7 + EXTRACT(DOY FROM w.workday)::integer * 11, 70) - 15)::integer AS arrival_offset,
        (MOD(e.employee_id * 5 + EXTRACT(DOY FROM w.workday)::integer * 3, 55) - 12)::integer AS departure_offset,
        MOD(e.employee_id + EXTRACT(DOY FROM w.workday)::integer, 37) = 0 AS missing_checkout,
        MOD(e.employee_id * 3 + EXTRACT(DOY FROM w.workday)::integer, 43) = 0 AS short_day
    FROM workdays w
    CROSS JOIN bi_demo_employees e
), attendance_values AS (
    SELECT
        employee_id,
        company_id,
        workday,
        arrival_offset,
        GREATEST(arrival_offset, 0) AS late_minutes,
        CASE WHEN short_day THEN 270 ELSE GREATEST(departure_offset, 0) END AS early_minutes,
        missing_checkout,
        short_day,
        workday::timestamp + INTERVAL '8 hours 30 minutes' + arrival_offset * INTERVAL '1 minute' AS check_in_value,
        CASE
            WHEN short_day THEN workday::timestamp + INTERVAL '13 hours'
            ELSE workday::timestamp + INTERVAL '17 hours 30 minutes'
                 - GREATEST(departure_offset, 0) * INTERVAL '1 minute'
                 + GREATEST(-departure_offset, 0) * INTERVAL '1 minute'
        END AS check_out_value
    FROM attendance_base
)
INSERT INTO hr_attendance (
    employee_id, check_in, check_out, worked_hours, overtime_hours,
    in_mode, out_mode, zkteco_managed,
    zkteco_late_minutes, zkteco_early_departure_minutes, zkteco_status,
    create_uid, write_uid, create_date, write_date
)SELECT
    employee_id,
    check_in_value,
    check_out_value,
    ROUND((EXTRACT(EPOCH FROM (check_out_value - check_in_value)) / 3600.0)::numeric, 4),
    ROUND(GREATEST(
        EXTRACT(EPOCH FROM (check_out_value - check_in_value)) / 3600.0 - 8.0,
        0
    )::numeric, 4),
    'kiosk',
    'kiosk',
    TRUE,
    late_minutes,
    early_minutes,
    CASE
        WHEN late_minutes > 0 AND early_minutes > 0 THEN 'late_early'
        WHEN late_minutes > 0 THEN 'late'
        WHEN early_minutes > 0 THEN 'early'
        ELSE 'on_time'
    END,
    2,
    2,
    check_in_value,
    COALESCE(check_out_value, check_in_value)
FROM attendance_values
WHERE NOT missing_checkout;
-- Logs bruts associes aux presences creees.
INSERT INTO hr_attendance_device_log (
    employee_id, company_id, device_user_id,
    punch_datetime, punch_type, device_name, device_serial,
    external_uid, state, attendance_id,
    create_uid, write_uid, create_date, write_date
)
SELECT
    attendance.employee_id,
    COALESCE(employee.company_id, 1),
    COALESCE(employee.zkteco_user_id, attendance.employee_id::text),
    punch.punch_datetime,
    punch.punch_type,
    'ZKTeco Siege Bravico',
    'BI-DEMO-01',
    'BI-' || attendance.id || '-' || punch.suffix,
    'processed',
    attendance.id,
    2,
    2,
    punch.punch_datetime,
    punch.punch_datetime
FROM hr_attendance attendance
JOIN hr_employee employee ON employee.id = attendance.employee_id
CROSS JOIN LATERAL (
    VALUES
        (attendance.check_in, 'check_in', 'IN'),
        (attendance.check_out, 'check_out', 'OUT')
) AS punch(punch_datetime, punch_type, suffix)
WHERE attendance.zkteco_managed IS TRUE
  AND attendance.create_uid = 2
  AND attendance.check_in >= TIMESTAMP '2026-03-01 00:00:00'
  AND punch.punch_datetime IS NOT NULL;
-- Quelques logs en erreur sans presence generee.
WITH error_days AS (
    SELECT day_value::date AS workday
    FROM generate_series(
        DATE '2026-03-15',
        DATE '2026-08-15',
        INTERVAL '15 day'
    ) day_value
), error_rows AS (
    SELECT
        e.employee_id,
        e.company_id,
        e.rn,
        d.workday,
        ROW_NUMBER() OVER (ORDER BY d.workday, e.employee_id) AS seq
    FROM error_days d
    CROSS JOIN bi_demo_employees e
    WHERE MOD(e.rn + EXTRACT(DOY FROM d.workday)::integer, 4) = 0
)
INSERT INTO hr_attendance_device_log (
    employee_id, company_id, device_user_id,
    punch_datetime, punch_type, device_name, device_serial,
    external_uid, state, error_message,
    create_uid, write_uid, create_date, write_date
)
SELECT
    employee_id,
    company_id,
    employee_id::text,
    workday::timestamp + INTERVAL '8 hours 30 minutes',
    CASE WHEN MOD(seq, 2) = 0 THEN 'check_in' ELSE 'check_out' END,
    'ZKTeco Siege Bravico',
    'BI-DEMO-01',
    'BI-ERROR-' || seq,
    'error',
    CASE WHEN MOD(seq, 2) = 0
         THEN 'Sortie correspondante introuvable.'
         ELSE 'Entree correspondante introuvable.' END,
    2, 2,
    workday::timestamp + INTERVAL '8 hours 30 minutes',
    workday::timestamp + INTERVAL '8 hours 30 minutes'
FROM error_rows;
-- Documents d'integration et metriques RAG.
INSERT INTO ir_attachment (
    name, type, url, mimetype, public,
    create_uid, write_uid, create_date, write_date
)
SELECT
    'BI-' || document_name || '.txt',
    'url',
    'https://demo.bravico.local/' || LOWER(REPLACE(document_name, ' ', '-')),
    'text/plain',
    FALSE,
    2, 2,
    TIMESTAMP '2026-01-10 09:00:00' + seq * INTERVAL '10 day',
    TIMESTAMP '2026-01-10 09:00:00' + seq * INTERVAL '10 day'
FROM (
    VALUES
        (1, 'Guide accueil collaborateur'),
        (2, 'Politique teletravail'),
        (3, 'Procedure demandes RH'),
        (4, 'Securite informatique'),
        (5, 'Avantages et couverture'),
        (6, 'Reglement interieur'),
        (7, 'Guide manager'),
        (8, 'Procedure confidentielle RH')
) AS documents(seq, document_name);
WITH document_specs AS (
    SELECT * FROM (VALUES
        ('Guide accueil collaborateur','welcome','fr','employee',NULL::text,1,'indexed'),
        ('Politique teletravail','policy','fr','employee',NULL::text,2,'indexed'),
        ('Procedure demandes RH','policy','fr','employee',NULL::text,3,'indexed'),
        ('Securite informatique','it','fr','department','Informatique',4,'indexed'),
        ('Avantages et couverture','benefits','fr','employee',NULL::text,5,'indexed'),
        ('Reglement interieur','policy','ar','employee',NULL::text,6,'indexed'),
        ('Guide manager','welcome','fr','manager',NULL::text,7,'indexed'),
        ('Procedure confidentielle RH','other','fr','hr',NULL::text,8,'indexed')
    ) AS value(name, category, language, visibility, department_name, seq, indexing_state)
)
INSERT INTO hr_onboarding_document (
    attachment_id, company_id, department_id, version,
    name, file_name, category, language, visibility,
    checksum, indexing_state, indexed_at, active,
    create_uid, write_uid, create_date, write_date
)
SELECT
    attachment.id,
    1,
    department.id,
    1,
    'BI-' || spec.name,
    'BI-' || spec.name || '.txt',
    spec.category,
    spec.language,
    spec.visibility,
    MD5(spec.name || '-bi-demo'),
    spec.indexing_state,
    TIMESTAMP '2026-01-10 10:00:00' + spec.seq * INTERVAL '10 day',
    TRUE,
    2, 2,
    TIMESTAMP '2026-01-10 09:00:00' + spec.seq * INTERVAL '10 day',
    TIMESTAMP '2026-01-10 10:00:00' + spec.seq * INTERVAL '10 day'
FROM document_specs spec
JOIN ir_attachment attachment
  ON attachment.name = 'BI-' || spec.name || '.txt'
LEFT JOIN hr_department department
  ON COALESCE(department.name->>'fr_FR', department.name->>'en_US') = spec.department_name;
WITH months AS (
    SELECT
        month_start::date,
        ROW_NUMBER() OVER (ORDER BY month_start) - 1 AS month_index
    FROM generate_series(
        DATE '2025-09-01',
        DATE '2026-08-01',
        INTERVAL '1 month'
    ) month_start
), conversations AS (
    SELECT
        m.month_start,
        m.month_index,
        e.employee_id,
        e.user_id,
        e.rn,
        ((m.month_index * 3 + e.rn)::integer % 20) + 2 AS day_offset
    FROM months m
    CROSS JOIN bi_demo_employees e
)
INSERT INTO hr_onboarding_conversation (
    user_id, employee_id, started_at, last_message_at, active,
    create_uid, write_uid, create_date, write_date
)
SELECT
    user_id,
    employee_id,
    month_start + day_offset + TIME '09:00:00',
    month_start + day_offset + TIME '09:03:00',
    TRUE,
    user_id,
    user_id,
    month_start + day_offset + TIME '09:00:00',
    month_start + day_offset + TIME '09:03:00'
FROM conversations;
WITH demo_conversations AS (
    SELECT
        conversation.id AS conversation_id,
        conversation.user_id,
        conversation.started_at,
        ROW_NUMBER() OVER (ORDER BY conversation.started_at, conversation.id) AS seq
    FROM hr_onboarding_conversation conversation
    WHERE conversation.user_id IN (SELECT user_id FROM bi_demo_employees)
      AND conversation.started_at >= TIMESTAMP '2025-09-01 00:00:00'
)
INSERT INTO hr_onboarding_message (
    conversation_id, role, content,
    confidence_score, latency_ms, cache_hit,
    feedback, needs_escalation, escalated_at,
    create_uid, write_uid, create_date, write_date
)
SELECT
    conversation_id,
    'user',
    '[BI DEMO] Question d onboarding numero ' || seq,
    NULL,
    NULL,
    FALSE,
    NULL,
    FALSE,
    NULL,
    user_id,
    user_id,
    started_at,
    started_at
FROM demo_conversations;
WITH demo_conversations AS (
    SELECT
        conversation.id AS conversation_id,
        conversation.user_id,
        conversation.started_at,
        ROW_NUMBER() OVER (ORDER BY conversation.started_at, conversation.id) AS seq
    FROM hr_onboarding_conversation conversation
    WHERE conversation.user_id IN (SELECT user_id FROM bi_demo_employees)
      AND conversation.started_at >= TIMESTAMP '2025-09-01 00:00:00'
)
INSERT INTO hr_onboarding_message (
    conversation_id, role, content,
    confidence_score, latency_ms, cache_hit,
    feedback, needs_escalation, escalated_at,
    create_uid, write_uid, create_date, write_date
)
SELECT
    conversation_id,
    'assistant',
    '[BI DEMO] Reponse sourcee numero ' || seq,
    ROUND((0.62 + MOD(seq, 35) / 100.0)::numeric, 2),
    320 + MOD(seq * 137, 1680),
    MOD(seq, 2) = 0,
    CASE
        WHEN MOD(seq, 10) IN (0, 1) THEN 'not_helpful'
        ELSE 'helpful'
    END,
    MOD(seq, 11) = 0,
    CASE WHEN MOD(seq, 11) = 0 THEN started_at + INTERVAL '5 minutes' ELSE NULL END,
    user_id,
    user_id,
    started_at + INTERVAL '2 minutes',
    started_at + INTERVAL '2 minutes'
FROM demo_conversations;

COMMIT;