SELECT e.id, encode(convert_to(e.name,'UTF8'),'hex') AS name_hex
FROM hr_employee e
WHERE e.user_id IS NOT NULL
ORDER BY e.id
LIMIT 15;
SELECT state, encode(convert_to(state_label,'UTF8'),'hex') AS label_hex
FROM bi.fact_hr_activity
GROUP BY state,state_label
ORDER BY state;