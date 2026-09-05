import fs from 'node:fs';
import path from 'node:path';

const root = 'C:/odoo-dev';
const tableDir = path.join(root, 'PortailRH.SemanticModel/definition/tables');
const sourceMap = {
  ActivitesRH: 'fact_hr_activity',
  Deplacements: 'fact_travel_request',
  Fournitures: 'fact_supply_request',
  Attestations: 'fact_attestation_request',
  Presences: 'fact_attendance',
  LogsZKTeco: 'fact_zkteco_log',
  MessagesIA: 'fact_onboarding_message',
  DocumentsIA: 'fact_onboarding_document',
  Employes: 'dim_employee',
  Departements: 'dim_department',
  Societes: 'dim_company',
};

for (const [table, view] of Object.entries(sourceMap)) {
  const file = path.join(tableDir, `${table}.tmdl`);
  let text = fs.readFileSync(file, 'utf8').replace(/\r\n/g, '\n');
  const marker = `\n\tpartition ${table} = m`;
  const start = text.indexOf(marker);
  if (start < 0) throw new Error(`Partition not found in ${table}`);
  const annotation = text.indexOf('\n\tannotation PBI_ResultType = Table', start);
  if (annotation < 0) throw new Error(`Annotation not found in ${table}`);
  const partition = `
\tpartition ${table} = m
\t\tmode: import
\t\tsource =
\t\t\tlet
\t\t\t\tSource = PostgreSQL.Database("127.0.0.1:5432", "portail_rh_powerbi", [CreateNavigationProperties=false]),
\t\t\t\tView = Source{[Schema="bi", Item="${view}"]}[Data]
\t\t\tin
\t\t\t\tView
`;
  text = text.slice(0, start) + partition + text.slice(annotation);
  fs.writeFileSync(file, text.replace(/\n/g, '\r\n'), 'utf8');
  console.log(`PostgreSQL source set: ${table} -> bi.${view}`);
}

const relationships = [
  ['ActivitesRH', 'employee_id', 'Employes', 'employee_id'],
  ['ActivitesRH', 'department_id', 'Departements', 'department_id'],
  ['ActivitesRH', 'company_id', 'Societes', 'company_id'],
  ['Deplacements', 'employee_id', 'Employes', 'employee_id'],
  ['Deplacements', 'department_id', 'Departements', 'department_id'],
  ['Deplacements', 'company_id', 'Societes', 'company_id'],
  ['Fournitures', 'employee_id', 'Employes', 'employee_id'],
  ['Fournitures', 'department_id', 'Departements', 'department_id'],
  ['Fournitures', 'company_id', 'Societes', 'company_id'],
];
relationships.push(
  ['Attestations', 'employee_id', 'Employes', 'employee_id'],
  ['Attestations', 'department_id', 'Departements', 'department_id'],
  ['Attestations', 'company_id', 'Societes', 'company_id'],
  ['Presences', 'employee_id', 'Employes', 'employee_id'],
  ['Presences', 'department_id', 'Departements', 'department_id'],
  ['Presences', 'company_id', 'Societes', 'company_id'],
  ['LogsZKTeco', 'employee_id', 'Employes', 'employee_id'],
  ['LogsZKTeco', 'department_id', 'Departements', 'department_id'],
  ['LogsZKTeco', 'company_id', 'Societes', 'company_id'],
  ['MessagesIA', 'employee_id', 'Employes', 'employee_id'],
  ['MessagesIA', 'department_id', 'Departements', 'department_id'],
  ['MessagesIA', 'company_id', 'Societes', 'company_id'],
  ['DocumentsIA', 'department_id', 'Departements', 'department_id'],
  ['DocumentsIA', 'company_id', 'Societes', 'company_id'],
);

const relationText = relationships.map(([fact, fk, dim, pk], index) => {
  const name = `${String(index + 1).padStart(2, '0')} ${fact} ${dim}`;
  return `relationship '${name}'\n\tfromColumn: ${fact}.${fk}\n\ttoColumn: ${dim}.${pk}`;
}).join('\n\n') + '\n';
fs.writeFileSync(path.join(root, 'PortailRH.SemanticModel/definition/relationships.tmdl'), relationText, 'utf8');
console.log(`Created ${relationships.length} one-direction star-schema relationships.`);
