import fs from 'fs';
import path from 'path';

const reportRoot = 'C:/odoo-dev/PortailRH.Report/definition/pages';
const common = {
  reference: 'Référence', request_date: 'Date de demande', employee_name: 'Employé',
  department_name: 'Département', company_name: 'Société', manager_name: 'Responsable',
  state_label: 'Statut', month_label: 'Mois', month_start: 'Mois',
  create_date: 'Créé le', write_date: 'Mis à jour le', amount: 'Montant estimé',
  quantity: 'Quantité', active: 'Actif'
};
const labels = {
  'ActivitesRH.activity_type_label': 'Type de demande',
  'Deplacements.date_from': 'Date de début',
  'Deplacements.date_to': 'Date de fin',
  'Deplacements.duration_days': 'Durée (jours)',
  'Deplacements.estimated_cost': 'Coût estimé',
  'Fournitures.item_name_normalized': 'Article',
  'Fournitures.estimated_cost': 'Coût estimé',
  'Fournitures.estimated_unit_cost': 'Coût unitaire estimé',
  'Attestations.attestation_type_label': "Type d’attestation",
  'Presences.attendance_date': 'Date de présence',
  'Presences.check_in': 'Heure d’entrée',
  'Presences.check_out': 'Heure de sortie',
  'Presences.worked_hours': 'Heures travaillées',
  'Presences.overtime_hours': 'Heures supplémentaires',
  'Presences.late_minutes': 'Retard (min)',
  'Presences.early_departure_minutes': 'Départ anticipé (min)',
  'Presences.status_label': 'Statut de présence',
  'Presences.quality_label': 'Qualité des données',
  'LogsZKTeco.device_user_id': 'Identifiant badge',
  'LogsZKTeco.punch_datetime': 'Date et heure du pointage',
  'LogsZKTeco.punch_date': 'Date du pointage',
  'LogsZKTeco.punch_type_label': 'Type de pointage',
  'LogsZKTeco.device_name': 'Appareil',
  'LogsZKTeco.device_serial': 'N° de série',
  'LogsZKTeco.has_error': 'Erreur détectée',
  'LogsZKTeco.is_processed': 'Traité',
  'MessagesIA.role_label': 'Rôle',
  'MessagesIA.confidence_score': 'Score de confiance',
  'MessagesIA.latency_ms': 'Latence (ms)',
  'MessagesIA.cache_hit': 'Réponse en cache',
  'MessagesIA.feedback_label': 'Avis utilisateur',
  'MessagesIA.needs_escalation': 'Escalade RH',
  'MessagesIA.message_date': 'Date du message',
  'DocumentsIA.category_label': 'Catégorie',
  'DocumentsIA.language_label': 'Langue',
  'DocumentsIA.visibility_label': 'Visibilité',
  'DocumentsIA.indexing_state_label': 'État d’indexation',
  'DocumentsIA.indexed_at': 'Indexé le'
};
const labelFor = (table, property) => labels[`${table}.${property}`] || common[property] || property;
let changed = 0;
function walk(node) {
  if (!node || typeof node !== 'object') return;
  const column = node.field?.Column;
  const table = column?.Expression?.SourceRef?.Entity;
  const property = column?.Property;
  if (table && property && Object.hasOwn(node, 'nativeQueryRef')) {
    const label = labelFor(table, property);
    if (node.nativeQueryRef !== label) { node.nativeQueryRef = label; changed++; }
  }
  for (const value of Object.values(node)) walk(value);
}
const files = [];
function collect(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) collect(full);
    else if (entry.name === 'visual.json') files.push(full);
  }
}
collect(reportRoot);
let touchedFiles = 0;
for (const file of files) {
  const visual = JSON.parse(fs.readFileSync(file, 'utf8'));
  const before = changed;
  walk(visual);
  if (changed > before) {
    fs.writeFileSync(file, JSON.stringify(visual, null, 2), 'utf8');
    touchedFiles++;
  }
}
console.log(`Friendly labels applied: ${changed} projections in ${touchedFiles} visuals.`);
