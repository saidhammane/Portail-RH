import fs from 'fs';
import path from 'path';
import crypto from 'crypto';

const root = 'C:/odoo-dev';
const pagesRoot = path.join(root, 'PortailRH.Report', 'definition', 'pages');
const refRoot = 'C:/PowerBI/JobSearch/Job_Search_Dashboard.Report/definition/pages/7a9c4e2b1d6f8035a4c2/visuals';
const templateIds = {
  title: '0f1e2d3c4b5a69788766',
  cards: '112233445566778899aa',
  chart1: '2233445566778899aabb',
  chart2: '33445566778899aabbcc',
  table: '445566778899aabbccdd',
  slicer: '5566778899aabbccddee',
};
const templates = Object.fromEntries(Object.entries(templateIds).map(([key, id]) => [key, JSON.parse(fs.readFileSync(path.join(refRoot, id, 'visual.json'), 'utf8'))]));

const pages = [
  {
    key: 'overview', name: 'Vue globale RH', subtitle: 'Pilotage consolidé des demandes, effectifs et coûts estimés', accent: '#0F766E',
    cards: ['Total demandes','Demandes approuvees','Taux approbation','Cout total demandes','Employes actifs','Departements actifs'],
    charts: [
      { table:'ActivitesRH', category:'activity_type_label', measure:'Total demandes', title:'Demandes par processus', color:'#0F766E' },
      { table:'ActivitesRH', category:'state_label', measure:'Total demandes', title:'Demandes par état', color:'#2563EB' },
    ],
    table: { table:'ActivitesRH', columns:['activity_type_label','reference','employee_name','department_name','state_label','amount','request_date'], sort:'request_date', direction:'Descending', title:'Dernières demandes RH' },
    slicers: [ ['ActivitesRH','department_name','Département'], ['ActivitesRH','state_label','État'], ['ActivitesRH','activity_type_label','Processus'] ],
  },
  {
    key: 'attendance', name: 'Présence & ZKTeco', subtitle: 'Suivi des présences, retards, anomalies et qualité des pointages', accent: '#0369A1',
    cards: ['Total presences','Heures travaillees','Retards','Taux retard','Departs anticipes','Journees courtes'],
    charts: [
      { table:'Presences', category:'month_label', measure:'Retards', title:'Retards par mois', color:'#0369A1', chronological:true },
      { table:'Presences', category:'department_name', measure:'Retards', title:'Retards par département', color:'#F59E0B' },
    ],
    table: { table:'Presences', columns:['employee_name','attendance_date','worked_hours','late_minutes','early_departure_minutes','quality_label'], sort:'attendance_date', direction:'Descending', title:'Détail des anomalies de présence' },
    slicers: [ ['Presences','department_name','Département'], ['Presences','status_label','Statut'], ['Presences','quality_label','Qualité'] ],
  },
  {
    key: 'travel', name: 'Déplacements', subtitle: 'Analyse des volumes, coûts estimés, durées et destinations', accent: '#1D4ED8',
    cards: ['Total deplacements','Cout deplacements','Cout moyen deplacement','Taux approbation deplacements','Duree moyenne','Deplacements en attente'],
    charts: [
      { table:'Deplacements', category:'month_label', measure:'Cout deplacements', title:'Coût estimé par mois', color:'#1D4ED8', chronological:true },
      { table:'Deplacements', category:'department_name', measure:'Cout deplacements', title:'Coût estimé par département', color:'#0EA5E9' },
    ],
    table: { table:'Deplacements', columns:['reference','employee_name','destination','date_from','date_to','duration_days','estimated_cost','state_label'], sort:'estimated_cost', direction:'Descending', title:'Déplacements les plus coûteux' },
    slicers: [ ['Deplacements','department_name','Département'], ['Deplacements','state_label','État'], ['Deplacements','destination','Destination'] ],
  },
  {
    key: 'supply', name: 'Fournitures', subtitle: 'Consommation, coûts estimés et tendance des besoins par article', accent: '#7C3AED',
    cards: ['Total fournitures','Quantite fournitures','Cout fournitures','Cout moyen fourniture','Taux approbation fournitures','Prevision mensuelle quantite'],
    charts: [
      { table:'Fournitures', category:'month_label', measure:'Quantite fournitures', title:'Quantité demandée par mois', color:'#7C3AED', chronological:true },
      { table:'Fournitures', category:'item_name_normalized', measure:'Quantite fournitures', title:'Articles les plus demandés', color:'#A855F7' },
    ],
    table: { table:'Fournitures', columns:['reference','employee_name','department_name','item_name_normalized','quantity','estimated_cost','state_label'], sort:'estimated_cost', direction:'Descending', title:'Détail des demandes de fournitures' },
    slicers: [ ['Fournitures','department_name','Département'], ['Fournitures','state_label','État'], ['Fournitures','item_name_normalized','Article'] ],
  },
  {
    key: 'attestations', name: 'Attestations', subtitle: 'Pilotage des demandes administratives et de leur traitement', accent: '#BE123C',
    cards: ['Total attestations','Attestations approuvees','Attestations soumises','Attestations refusees','Taux attestations approuvees'],
    charts: [
      { table:'Attestations', category:'month_label', measure:'Total attestations', title:'Demandes par mois', color:'#BE123C', chronological:true },
      { table:'Attestations', category:'attestation_type_label', measure:'Total attestations', title:'Demandes par type', color:'#E11D48' },
    ],
    table: { table:'Attestations', columns:['reference','employee_name','department_name','request_date','attestation_type_label','state_label'], sort:'request_date', direction:'Descending', title:'Détail des attestations' },
    slicers: [ ['Attestations','department_name','Département'], ['Attestations','state_label','État'], ['Attestations','attestation_type_label','Type'] ],
  },
  {
    key: 'ai', name: 'Assistant IA d’onboarding', subtitle: 'Performance du RAG sécurisé, expérience utilisateur et escalades RH', accent: '#C2410C',
    cards: ['Questions IA','Reponses IA','Confiance moyenne IA','Latence moyenne IA','Taux cache IA','Escalades RH'],
    charts: [
      { table:'MessagesIA', category:'month_start', measure:'Reponses IA', title:'Réponses IA par mois', color:'#C2410C', chronological:true },
      { table:'MessagesIA', category:'department_name', measure:'Reponses IA', title:'Usage par département', color:'#F97316' },
    ],
    table: { table:'MessagesIA', columns:['employee_name','department_name','create_date','confidence_score','latency_ms','cache_hit','feedback_label','needs_escalation'], sort:'create_date', direction:'Descending', title:'Qualité des réponses de l’assistant' },
    slicers: [ ['MessagesIA','department_name','Département'], ['MessagesIA','role_label','Rôle'], ['MessagesIA','feedback_label','Feedback'] ],
  },
  {
    key: 'quality', name: 'Qualité & opérations', subtitle: 'Supervision des logs ZKTeco, indexation IA et qualité des données', accent: '#374151',
    cards: ['Logs ZKTeco','Logs en erreur','Taux traitement logs','Documents IA','Documents en erreur','Taux indexation'],
    charts: [
      { table:'LogsZKTeco', category:'state_label', measure:'Logs ZKTeco', title:'État des logs ZKTeco', color:'#374151' },
      { table:'Presences', category:'quality_label', measure:'Total presences', title:'Qualité des présences générées', color:'#64748B' },
    ],
    table: { table:'LogsZKTeco', columns:['employee_name','punch_datetime','device_name','punch_type_label','state_label','has_error'], sort:'punch_datetime', direction:'Descending', title:'Derniers logs de pointage' },
    slicers: [ ['LogsZKTeco','department_name','Département'], ['LogsZKTeco','state_label','État'], ['LogsZKTeco','device_name','Appareil'] ],
  },
];

const deepClone = obj => JSON.parse(JSON.stringify(obj));
const stableId = seed => crypto.createHash('sha1').update(seed).digest('hex').slice(0, 20);
const literal = value => `'${String(value).replaceAll("'", "''")}'`;
const columnField = (table, property) => ({ Column:{ Expression:{ SourceRef:{ Entity:table } }, Property:property } });
const measureField = property => ({ Measure:{ Expression:{ SourceRef:{ Entity:'ActivitesRH' } }, Property:property } });
const columnProjection = (table, property, active=false) => ({ field:columnField(table,property), queryRef:`${table}.${property}`, nativeQueryRef:property, ...(active ? {active:true} : {}) });
const measureProjection = property => ({ field:measureField(property), queryRef:`ActivitesRH.${property}`, nativeQueryRef:property });

function setPosition(visual, x, y, width, height, z, tabOrder) {
  visual.position = { x, y, z, height, width, tabOrder };
}
function setContainerTitle(visual, text) {
  const title = visual.visual?.visualContainerObjects?.title?.[0]?.properties;
  if (title?.text?.expr?.Literal) title.text.expr.Literal.Value = literal(text);
}
function makeTitle(page, pageId) {
  const visual = deepClone(templates.title);
  visual.name = stableId(`${pageId}-title`);
  setPosition(visual, 40, 24, 860, 96, 1000, 0);
  const paragraphs = visual.visual.objects.general[0].properties.paragraphs;
  paragraphs[0].textRuns[0].value = `PORTAIL RH — ${page.name.toUpperCase()}`;
  paragraphs[0].textRuns[0].textStyle.color = page.accent;
  paragraphs[1].textRuns[0].value = page.subtitle;
  return visual;
}
function makeCards(page, pageId) {
  const visual = deepClone(templates.cards);
  visual.name = stableId(`${pageId}-cards`);
  setPosition(visual, 40, 140, 1800, 176, 2000, 1);
  visual.visual.query.queryState.Data.projections = page.cards.map(measureProjection);
  return visual;
}
function makeChart(spec, pageId, index) {
  const visual = deepClone(index === 0 ? templates.chart1 : templates.chart2);
  visual.name = stableId(`${pageId}-chart-${index}`);
  setPosition(visual, index === 0 ? 40 : 960, 350, 880, 310, 3000 + index * 1000, 2 + index);
  visual.visual.query.queryState.Category.projections = [columnProjection(spec.table, spec.category, true)];
  visual.visual.query.queryState.Y.projections = [measureProjection(spec.measure)];
  visual.visual.query.sortDefinition = {
    sort:[spec.chronological ? { field:columnField(spec.table,spec.category), direction:'Ascending' } : { field:measureField(spec.measure), direction:'Descending' }],
    isDefaultSort:true,
  };
  visual.visual.objects.dataPoint[0].properties.fill.solid.color.expr.Literal.Value = literal(spec.color);
  setContainerTitle(visual, spec.title);
  return visual;
}
function makeTable(spec, pageId) {
  const visual = deepClone(templates.table);
  visual.name = stableId(`${pageId}-table`);
  setPosition(visual, 40, 700, 1800, 340, 5000, 4);
  visual.visual.query.queryState.Values.projections = spec.columns.map(c => columnProjection(spec.table,c));
  visual.visual.query.sortDefinition = { sort:[{ field:columnField(spec.table,spec.sort), direction:spec.direction }], isDefaultSort:true };
  setContainerTitle(visual, spec.title);
  return visual;
}
function makeSlicer(spec, pageId, index) {
  const [table, property, label] = spec;
  const visual = deepClone(templates.slicer);
  visual.name = stableId(`${pageId}-slicer-${index}`);
  setPosition(visual, 960 + index * 300, 24, 280, 80, 11000 + index * 1000, 5 + index);
  visual.visual.query.queryState.Values.projections = [columnProjection(table,property)];
  visual.visual.objects.header[0].properties.text.expr.Literal.Value = literal(label);
  return visual;
}

fs.rmSync(pagesRoot, { recursive:true, force:true });
fs.mkdirSync(pagesRoot, { recursive:true });
const pageOrder = [];
for (const page of pages) {
  const pageId = stableId(`portail-rh-page-${page.key}`);
  pageOrder.push(pageId);
  const pageDir = path.join(pagesRoot,pageId);
  const visualDir = path.join(pageDir,'visuals');
  fs.mkdirSync(visualDir,{recursive:true});
  const pageJson = {
    $schema:'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json',
    name:pageId,
    displayName:page.name,
    displayOption:'FitToPage',
    height:1080,
    width:1920,
  };
  fs.writeFileSync(path.join(pageDir,'page.json'), JSON.stringify(pageJson,null,2));
  const visuals = [makeTitle(page,pageId),makeCards(page,pageId),...page.charts.map((c,i)=>makeChart(c,pageId,i)),makeTable(page.table,pageId),...page.slicers.map((s,i)=>makeSlicer(s,pageId,i))];
  for (const visual of visuals) {
    const dir = path.join(visualDir,visual.name);
    fs.mkdirSync(dir,{recursive:true});
    fs.writeFileSync(path.join(dir,'visual.json'),JSON.stringify(visual,null,2));
  }
}
const pagesMeta = {
  $schema:'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json',
  pageOrder,
  activePageName:pageOrder[0],
};
fs.writeFileSync(path.join(pagesRoot,'pages.json'),JSON.stringify(pagesMeta,null,2));
console.log(`Generated ${pages.length} report pages and ${pages.length * 8} visuals.`);