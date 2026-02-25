(function () {

const qs = sel => document.querySelector(sel);

// Original core elements
const tenantIdEl = qs('#tenantId');
const modelIdEl = qs('#modelId');
const btnLoad = qs('#btnLoad');
const btnSave = qs('#btnSave');
const btnPublish = qs('#btnPublish');
const entitySel = qs('#entitySelect');
const attrWrap = qs('#attributes');
const btnAddAttr = qs('#btnAddAttribute');
const btnAddEnt = qs('#btnAddEntity');
const btnRmEnt = qs('#btnRemoveEntity');
const jsonEditor = qs('#jsonEditor');
const btnFormat = qs('#btnFormat');
const btnExport = qs('#btnExport');
const status = qs('#status');

// Optional features
const btnValidate = qs('#btnValidate');
const validateOut = qs('#validateOut');
const tabs = Array.from(document.querySelectorAll('.tab'));
const paneAttrs = qs('#pane-attributes');
const paneRels = qs('#pane-relationships');
const relationshipsEl = qs('#relationships');
const relEntityName = qs('#relEntityName');
const btnAddRel = qs('#btnAddRelationship');

// New view switcher
const viewTabs = Array.from(document.querySelectorAll('.view-tab'));
const viewJSON = qs('#view-json');
const viewTable = qs('#view-table');
const viewGraph = qs('#view-graph');
const modelTable = qs('#modelTable');
const modelGraph = qs('#modelGraph');

const patchEditor = qs('#patchEditor');
const btnApplyPatch = qs('#btnApplyPatch');

let model = null;

function getCSRFToken() {
  const name = 'csrftoken=';
  const cookies = document.cookie.split(';');
  for (let c of cookies) {
    c = c.trim();
    if (c.startsWith(name)) {
      return c.substring(name.length, c.length);
    }
  }
  return '';
}

function showError(msg) {
  const el = document.querySelector('#promptStatus');
  if (el) el.textContent = `Error: ${msg}`;
  console.error(msg);
}

function showSuccess(msg) {
  const el = document.querySelector('#promptStatus');
  if (el) el.textContent = msg;
  console.log(msg);
}

function setStatus(msg){ if (status) status.textContent = 'Status: ' + msg; }
function setButtons(enabled){
  if (btnSave) btnSave.disabled = !enabled;
  if (btnPublish) btnPublish.disabled = !enabled;
  if (btnValidate) btnValidate.disabled = !enabled;
}

// ---------- ORIGINAL: Entities & Attributes ----------
function renderEntities(){
  if (!entitySel) return;
  entitySel.innerHTML = '';
  if(!model || !Array.isArray(model.entities)) return;

  model.entities.forEach(e => {
    const opt = document.createElement('option');
    opt.value = e.id; 
    opt.textContent = e.label || e.id;
    entitySel.appendChild(opt);
  });

  renderAttributes();
  renderRelationships();
  renderTableView();
  renderGraphView();
}

function getSelectedEntity(){
  if (!model || !Array.isArray(model.entities) || model.entities.length === 0) {
    return { id:'', label:'', attributes:[], relationships:[], workflow:{states:[{id:'Draft'}], transitions:[]} };
  }
  const id = entitySel && entitySel.value || model.entities[0].id;
  return model.entities.find(e => e.id === id) || model.entities[0];
}

function renderAttributes(){
  if (!attrWrap) return;
  const ent = getSelectedEntity();
  attrWrap.innerHTML = '';

  (ent.attributes || []).forEach((a) => {
    const row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = `
      <input class="id" value="${a.id ?? ''}" />
      <select class="type">
        <option ${a.type==='string'?'selected':''}>string</option>
        <option ${a.type==='number'?'selected':''}>number</option>
        <option ${a.type==='boolean'?'selected':''}>boolean</option>
        <option ${a.type==='date'?'selected':''}>date</option>
        <option ${a.type==='datetime'?'selected':''}>datetime</option>
      </select>
      <label><input type="checkbox" class="required" ${a.required?'checked':''}/> required</label>
      <input class="def" placeholder="default" value="${a.default ?? ''}" />
    `;

    const idEl = row.querySelector('.id');
    const typeEl = row.querySelector('.type');
    const reqEl = row.querySelector('.required');
    const defEl = row.querySelector('.def');

    if (idEl) idEl.addEventListener('input', e => { a.id = e.target.value; syncEditor(); });
    if (typeEl) typeEl.addEventListener('change', e => { a.type = e.target.value; syncEditor(); });
    if (reqEl) reqEl.addEventListener('change', e => { a.required = e.target.checked; syncEditor(); });
    if (defEl) defEl.addEventListener('input', e => { a.default = e.target.value; syncEditor(); });

    attrWrap.appendChild(row);
  });
}

function syncEditor(){
  if (jsonEditor){ jsonEditor.value = JSON.stringify(model, null, 2); }
  setButtons(true);
}

// ---------- ORIGINAL: Load / Save / Publish ----------
if (btnLoad) {
  btnLoad.addEventListener('click', async () => {
    if (!tenantIdEl || !modelIdEl) { setStatus('error: missing tenant/model inputs'); return; }
    const tenantId = tenantIdEl.value.trim();
    const modelId = modelIdEl.value.trim();
    setStatus('loading...');

    try{
      const res = await fetch(`/api/tenants/${tenantId}/models/${modelId}`);
      if(!res.ok){ throw new Error(await res.text()); }
      model = await res.json();
      syncEditor();
      renderEntities();
      setStatus('model loaded');
    }catch(err){ setStatus('error: '+err.message); }
  });
}

if (btnSave) {
  btnSave.addEventListener('click', async ()=>{
    if (!tenantIdEl || !modelIdEl) { setStatus('error: missing tenant/model inputs'); return; }
    const tenantId = tenantIdEl.value.trim();
    const modelId = modelIdEl.value.trim();

    try{
      model = JSON.parse(jsonEditor.value);
    }catch(err){ setStatus('invalid JSON'); return; }

    setStatus('saving...');
    try{
      const res = await fetch(`/api/tenants/${tenantId}/models/${modelId}/update`, {
        method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(model)
      });
      if(!res.ok){ throw new Error(await res.text()); }
      setButtons(false);
      setStatus('saved');
      renderTableView(); 
      renderGraphView();
    }catch(err){ setStatus('error: '+err.message); }
  });
}

if (btnPublish) {
  btnPublish.addEventListener('click', async ()=>{
    if (!tenantIdEl || !modelIdEl) { setStatus('error: missing tenant/model inputs'); return; }
    const tenantId = tenantIdEl.value.trim();
    const modelId = modelIdEl.value.trim();
    setStatus('publishing...');   

    try{
      const res = await fetch(`/api/tenants/${tenantId}/models/${modelId}/publish`, { method:'POST' });
      if(!res.ok){ throw new Error(await res.text()); }
      setStatus('published');
      btnPublish.disabled = true;
    }catch(err){ setStatus('error: '+err.message); }
  });
}

// ---------- ORIGINAL: Add attribute / entity / remove entity ----------
if (btnAddAttr) {
  btnAddAttr.addEventListener('click', () => {
    if(!model) return;
    const ent = getSelectedEntity();
    ent.attributes = ent.attributes || [];
    ent.attributes.push({ id:'newField', type:'string', required:false });
    renderAttributes();
    syncEditor();
    renderTableView(); 
    renderGraphView();
  });
}

if (btnAddEnt) {
  btnAddEnt.addEventListener('click', () => {
    if(!model) return;
    const newId = prompt('New entity id', 'NewEntity');
    if(!newId) return;

    model.entities = model.entities || [];
    model.entities.push({ id:newId, label:newId, attributes:[], relationships:[], workflow:{states:[{id:'Draft'}], transitions:[]} });

    renderEntities();
    if (entitySel) entitySel.value = newId;
    renderAttributes();
    renderRelationships();
    syncEditor();
    renderTableView(); 
    renderGraphView();
  });
}

if (btnRmEnt) {
  btnRmEnt.addEventListener('click', () => {
    if(!model) return;
    const id = entitySel && entitySel.value;
    model.entities = (model.entities||[]).filter(e => e.id !== id);
    renderEntities();
    syncEditor();
    renderTableView(); 
    renderGraphView();
  });
}

// ---------- ORIGINAL: Format / Export ----------
if (btnFormat) {
  btnFormat.addEventListener('click', ()=>{
    try{ 
      const obj = JSON.parse(jsonEditor.value); 
      jsonEditor.value = JSON.stringify(obj, null, 2); 
      setStatus('formatted'); 
    }
    catch{ setStatus('invalid JSON'); }
  });
}

if (btnExport) {
  btnExport.addEventListener('click', ()=>{
    const blob = new Blob([jsonEditor.value || '{}'], {type:'application/json'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = (model && model.modelId ? model.modelId : 'model') + '.json';
    a.click();
  });
}

// ---------- OPTIONAL: Validate ----------
if (btnValidate) {
  btnValidate.addEventListener('click', async () => {
    if (validateOut) validateOut.textContent = '';
    if (!tenantIdEl || !modelIdEl) { setStatus('error: missing tenant/model inputs'); return; }

    const tenantId = tenantIdEl.value.trim();
    const modelId = modelIdEl.value.trim();
    setStatus('validating...');

    try{
      model = JSON.parse(jsonEditor.value);
    }catch{ setStatus('invalid JSON'); return; }

    try{
      await fetch(`/api/tenants/${tenantId}/models/${modelId}/update`, {
        method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(model)
      });
    }catch { /* ignore */ }

    try{
      const res = await fetch(`/api/tenants/${tenantId}/models/${modelId}/validate`, { method:'POST' });
      const payload = await res.json().catch(()=>({}));

      if (res.ok && payload.ok) {
        setStatus('validation passed');
      } else {
        setStatus('validation failed');
        if (validateOut) validateOut.textContent = (payload.errors||[]).map(e => `• ${e}`).join('\n');
      }
    }catch(err){ setStatus('error: '+err.message); }
  });
}

// ---------- OPTIONAL: Relationships ----------
function renderRelationships(){
  if (!relationshipsEl || !relEntityName || !paneRels) return;

  const ent = getSelectedEntity() || { id:'', label:'', relationships:[] };
  relEntityName.textContent = ent.label || ent.id || '(none)';
  relationshipsEl.innerHTML = '';

  const rels = Array.isArray(ent.relationships) ? ent.relationships : [];

  rels.forEach(r => {
    const row = document.createElement('div');
    row.className = 'row';
    row.style.gridTemplateColumns = '140px 160px 160px 160px 1fr';

    row.innerHTML = `
      <input class="rid" value="${r.id || ''}" placeholder="id" />
      <select class="rtype">
        ${['references','aggregates','dependsOn','parentOf','childOf'].map(t => `<option ${r.type===t?'selected':''}>${t}</option>`).join('')}
      </select>
      <select class="rto">
        <option value="">Select target entity…</option>
        ${model.entities
        .filter(e => e.id !== ent.id)   // exclude the entity itself
        .map(e => `
        <option value="${e.id}" ${r.to === e.id ? 'selected' : ''}>
          ${e.label || e.id} (entity)
        </option>
        `)
        .join('')}
      </select>
      <select class="rcard">
        ${['one-to-one','one-to-many','many-to-one','many-to-many'].map(c => `<option ${r.cardinality===c?'selected':''}>${c}</option>`).join('')}
      </select>
      <select class="rkmfrom">
  <option value="">Select reference attribute…</option>
  ${
    (ent.attributes || [])
      .map(a => `
        <option value="${a.id}" ${((r.keyMapping||{}).fromAttr === a.id) ? 'selected' : ''}>
          ${a.id}
        </option>
      `)
      .join('')
    }
    </select>
    `;

    row.querySelector('.rid') .addEventListener('input', e => { r.id = e.target.value; syncEditor(); renderGraphView(); });
    row.querySelector('.rtype') .addEventListener('change', e => { r.type = e.target.value; syncEditor(); renderGraphView(); });
    row.querySelector('.rto').addEventListener('change', e => { r.to = e.target.value; syncEditor(); renderGraphView(); });
    row.querySelector('.rcard') .addEventListener('change', e => { r.cardinality = e.target.value; syncEditor(); renderGraphView(); });
    row.querySelector('.rkmfrom').addEventListener('input', e => {
      r.keyMapping = r.keyMapping || {}; 
      r.keyMapping.fromAttr = e.target.value; 
      syncEditor(); 
      renderGraphView();
    });

    relationshipsEl.appendChild(row);
  });
}

if (tabs.length && paneAttrs && paneRels) {
  tabs.forEach(t => t.addEventListener('click', () => {
    tabs.forEach(x => x.classList.remove('active'));
    t.classList.add('active');

    const tabName = t.getAttribute('data-tab') || 'attributes';
    paneAttrs.style.display = (tabName === 'attributes') ? '' : 'none';
    paneRels .style.display = (tabName === 'relationships') ? '' : 'none';

    if (tabName === 'relationships') renderRelationships();
  }));
}

if (btnAddRel) {
  btnAddRel.addEventListener('click', () => {
    if(!model) return;
    const ent = getSelectedEntity();
    ent.relationships = ent.relationships || [];

    ent.relationships.push({
      id: 'rel_' + Math.random().toString(36).slice(2, 7),
      type: 'references',
      to: '',
      cardinality: 'many-to-one',
      keyMapping: { fromAttr: '' }
    });

    renderRelationships();
    syncEditor();
    renderGraphView();
  });
}

// ---------- OPTIONAL: JSON Patch ----------
if (btnApplyPatch && patchEditor) {
  btnApplyPatch.addEventListener('click', async () => {
    if (!tenantIdEl || !modelIdEl) { setStatus('error: missing tenant/model inputs'); return; }

    const tenantId = tenantIdEl.value.trim();
    const modelId = modelIdEl.value.trim();
    setStatus('applying patch...');

    let ops;
    try { 
      ops = JSON.parse(patchEditor.value || '[]'); 
      if (!Array.isArray(ops)) throw 0; 
    }
    catch { setStatus('invalid patch JSON'); return; }

    try{
      const res = await fetch(`/api/tenants/${tenantId}/models/${modelId}/patch`, {
        method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(ops)
      });

      const payload = await res.json().catch(()=>({ok:false,error:'invalid server response'}));
      if (!res.ok || !payload.ok) throw new Error(payload.error || 'Patch error');

      model = payload.model;
      syncEditor(); 
      renderEntities();
      setStatus('patch applied');
    }catch(err){ setStatus('error: '+err.message); }
  });
}

// ---------- OPTIONAL: View tabs (JSON / Table / Graph) ----------
if (viewTabs.length) {
  viewTabs.forEach(btn => {
    btn.addEventListener('click', () => {
      viewTabs.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const view = btn.getAttribute('data-view') || 'json';

      if (viewJSON)  viewJSON.style.display  = (view === 'json')  ? '' : 'none';
      if (viewTable) viewTable.style.display = (view === 'table') ? '' : 'none';
      if (viewGraph) viewGraph.style.display = (view === 'graph') ? '' : 'none';

      // Option A: re-render on tab switch
      if (view === 'table') renderTableView();
      if (view === 'graph') renderGraphView();
    });
  });
}

// ---------- OPTIONAL: Table & Graph render stubs ----------
function renderTableView(){
  if (!modelTable) return;
  if (!model || !Array.isArray(model.entities)) { 
    modelTable.innerHTML = ''; 
    return; 
  }

  const rows = [];
  rows.push('<table><thead><tr><th>Entity</th><th>Attribute</th><th>Type</th></tr></thead><tbody>');

  model.entities.forEach(e => {
    (e.attributes || []).forEach(a => {
      rows.push(`<tr><td>${e.id}</td><td>${a.id}</td><td>${a.type}</td></tr>`);
    });
  });

  rows.push('</tbody></table>');
  modelTable.innerHTML = rows.join('');
}

function renderGraphView() {
  if (!modelGraph || !model) return;

  // Clear old graph
  modelGraph.innerHTML = "";

  const nodes = [];
  const edges = [];

  // Build nodes
  model.entities.forEach(ent => {
    nodes.push({
      id: ent.id,
      label: ent.label || ent.id,
      shape: "box",
      color: "#e8f0fe"
    });

    // Build edges from relationships
    (ent.relationships || []).forEach(r => {
      if (!r.to) return; // skip invalid relationships

      edges.push({
        from: ent.id,
        to: r.to,
        arrows: "to",
        label: r.type || "",
        font: { align: "middle" }
      });
    });
  });

  const data = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) };

  const options = {
    layout: { hierarchical: false },
    physics: { enabled: true },
    edges: { smooth: true }
  };

  new vis.Network(modelGraph, data, options);
}
// ---------- NEW: Multi-step Studio flow (home / create / edit) ----------

// Sections
const studioHome = qs('#studioHome');
const createOptions = qs('#createOptions');
const templatePicker = qs('#templatePicker');
const promptBuilder = qs('#promptBuilder');
const spreadsheetUpload = qs('#spreadsheetUpload');
const dataConnector = qs('#dataConnector');
const existingModelsSec = qs('#existingModels');
const studioEditorSec = qs('#studioEditor');

// Buttons
const btnCreateNew           = qs('#btnCreateNew');
const btnEditExisting        = qs('#btnEditExisting');
const btnBackToHomeFromCreate   = qs('#btnBackToHomeFromCreate');
const btnBackToHomeFromExisting= qs('#btnBackToHomeFromExisting');
const btnBackToCreateFromTemplate = qs('#btnBackToCreateFromTemplate');
const btnBackToCreateFromPrompt   = qs('#btnBackToCreateFromPrompt');
const btnBackToCreateFromSheet    = qs('#btnBackToCreateFromSheet');
const btnBackToCreateFromData     = qs('#btnBackToCreateFromData');

const cardUseTemplate      = qs('#cardUseTemplate');
const cardUsePrompt        = qs('#cardUsePrompt');
const cardUploadSpreadsheet= qs('#cardUploadSpreadsheet');
const cardConnectData      = qs('#cardConnectData');

// Template controls
const tenantIdTpl = qs('#tenantIdTpl');
const templateSelect = qs('#templateSelect');
const newModelIdInput = qs('#newModelId');
const btnLoadTemplate = qs('#btnLoadTemplate');
const templateStatus = qs('#templateStatus');

// Prompt controls
const tenantIdPrompt = qs('#tenantIdPrompt');
const promptModelId = qs('#promptModelId');
const promptInput = qs('#promptInput');
const btnGenerateFromPrompt = qs('#btnGenerateFromPrompt');
const promptStatus = qs('#promptStatus');
const promptTemplateSelect = qs('#promptTemplate');

// Spreadsheet controls
const tenantIdSheet = qs('#tenantIdSheet');
const sheetModelId = qs('#sheetModelId');
const spreadsheetFile = qs('#spreadsheetFile');
const btnProcessSpreadsheet = qs('#btnProcessSpreadsheet');
const sheetStatus = qs('#sheetStatus');

// Data connector controls
const tenantIdData = qs('#tenantIdData');
const dataModelId = qs('#dataModelId');
const dataSourceType = qs('#dataSourceType');
const btnConnectDataSource = qs('#btnConnectDataSource');
const dataStatus = qs('#dataStatus');

// Existing models controls
const tenantIdExisting = qs('#tenantIdExisting');
const existingModelSelect = qs('#existingModelSelect');
const btnOpenExistingModel= qs('#btnOpenExistingModel');
const existingStatus = qs('#existingStatus');

function showSectionById(id) {
  const all = [
    studioHome, createOptions, templatePicker, promptBuilder,
    spreadsheetUpload, dataConnector, existingModelsSec, studioEditorSec
  ];

  all.forEach(sec => {
    if (!sec) return;
    sec.style.display = (sec.id === id ? 'block' : 'none');
  });
}

// Initial view: home, editor hidden
if (studioHome) showSectionById('studioHome');

// Home navigation
if (btnCreateNew) {
  btnCreateNew.addEventListener('click', () => {
    showSectionById('createOptions');
  });
}

if (btnEditExisting) {
  btnEditExisting.addEventListener('click', async () => {
    showSectionById('existingModels');
    await loadExistingModels();
  });
}

if (btnBackToHomeFromCreate) {
  btnBackToHomeFromCreate.addEventListener('click', () => {
    showSectionById('studioHome');
  });
}

if (btnBackToHomeFromExisting) {
  btnBackToHomeFromExisting.addEventListener('click', () => {
    showSectionById('studioHome');
  });
}

if (btnBackToCreateFromTemplate) {
  btnBackToCreateFromTemplate.addEventListener('click', () => {
    showSectionById('createOptions');
  });
}

if (btnBackToCreateFromPrompt) {
  btnBackToCreateFromPrompt.addEventListener('click', () => {
    showSectionById('createOptions');
  });
}

if (btnBackToCreateFromSheet) {
  btnBackToCreateFromSheet.addEventListener('click', () => {
    showSectionById('createOptions');
  });
}

if (btnBackToCreateFromData) {
  btnBackToCreateFromData.addEventListener('click', () => {
    showSectionById('createOptions');
  });
}

// Create options → subflows
if (cardUseTemplate) {
  cardUseTemplate.addEventListener('click', async () => {
    showSectionById('templatePicker');
    await loadTemplates();
  });
}

if (cardUsePrompt) {
  cardUsePrompt.addEventListener('click', async() => {
    showSectionById('promptBuilder');
    await loadPromptTemplates();
  });
}

if (cardUploadSpreadsheet) {
  cardUploadSpreadsheet.addEventListener('click', () => {
    showSectionById('spreadsheetUpload');
  });
}

if (cardConnectData) {
  cardConnectData.addEventListener('click', () => {
    showSectionById('dataConnector');
  });
}

// ----- Template flow -----
async function loadTemplates() {
  if (!templateSelect) return;

  if (templateStatus) templateStatus.textContent = 'Loading templates...';
  setStatus('loading templates...');

  try {
    const res = await fetch('/api/templates');
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json(); // {templates: [...]}

    templateSelect.innerHTML = '';
    (data.templates || []).forEach(name => {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name;
      templateSelect.appendChild(opt);
    });

    if (templateStatus) {
      templateStatus.textContent = (data.templates || []).length
        ? 'Templates loaded.'
        : 'No templates available.';
    }

    setStatus('templates loaded');
  } catch (err) {
    console.error(err);
    if (templateStatus) templateStatus.textContent = 'Error loading templates.';
    setStatus('error loading templates');
  }
}

async function createFromTemplate() {
  if (!tenantIdTpl || !templateSelect) return;

  const tenantId = tenantIdTpl.value.trim() || 'tenantA';
  const tempateID = templateSelect.value;
  const newModelId = (newModelIdInput && newModelIdInput.value.trim()) || 'new-model';

  if (templateStatus) templateStatus.textContent = 'Creating model from template...';
  setStatus('creating model from template...');

  try {
    const res = await fetch(`/api/tenants/${tenantId}/models`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ modelId: newModelId, template: tempateID })
    });

    if (!res.ok) throw new Error(await res.text());
    const payload = await res.json();

    if (tenantIdEl) tenantIdEl.value = tenantId;
    if (modelIdEl) modelIdEl.value = payload.modelId || newModelId;

    showSectionById('studioEditor');
    if (btnLoad) btnLoad.click();

    if (templateStatus) templateStatus.textContent = 'Model created from template.';
    setStatus('model created from template');
  } catch (err) {
    console.error(err);
    if (templateStatus) templateStatus.textContent = 'Error creating model from template.';
    setStatus('error creating model from template');
  }
}

if (btnLoadTemplate) {
  btnLoadTemplate.addEventListener('click', createFromTemplate);
}

// ----- Existing models flow (edit existing) -----
async function loadExistingModels() {
  if (!tenantIdExisting || !existingModelSelect) return;

  const tenantId = tenantIdExisting.value.trim() || 'tenantA';

  if (existingStatus) existingStatus.textContent = 'Loading models...';
  setStatus('loading models...');

  try {
    const res = await fetch(`/api/tenants/${tenantId}/list_models`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json(); // {models:[{model_id,status,version}, ...]}

    existingModelSelect.innerHTML = '';
    (data.models || []).forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.model_id;
      opt.textContent = `${m.model_id} (${m.status}, v${m.version})`;
      existingModelSelect.appendChild(opt);
    });

    if (existingStatus) {
      existingStatus.textContent = (data.models || []).length
        ? 'Select a model and open in editor.'
        : 'No models found.';
    }

    setStatus('models loaded');
    btnPublish.disabled = false;
  } catch (err) {
    console.error(err);
    if (existingStatus) existingStatus.textContent = 'Error loading models.';
    setStatus('error loading models');
  }
}

async function openExistingModel() {
  if (!tenantIdExisting || !existingModelSelect) return;

  const tenantId = tenantIdExisting.value.trim() || 'tenantA';
  const modelId = existingModelSelect.value;

  if (!modelId) {
    if (existingStatus) existingStatus.textContent = 'Please select a model first.';
    return;
  }

  if (tenantIdEl) tenantIdEl.value = tenantId;
  if (modelIdEl) modelIdEl.value = modelId;

  showSectionById('studioEditor');
  if (btnLoad) btnLoad.click();
}

if (btnOpenExistingModel) {
  btnOpenExistingModel.addEventListener('click', openExistingModel);
}

// ----- Prompt flow -----
async function loadPromptTemplates() {
  const sel = qs('#promptTemplate');
  if (!sel) return;

  sel.innerHTML = '<option>Loading...</option>';

  try {
    const res = await fetch('/api/prompt-templates');
    const data = await res.json();

    sel.innerHTML = '';

    (data.templates || []).forEach(tpl => {
      const opt = document.createElement('option');
      opt.value = tpl.id;          // what you POST to backend
      opt.textContent = tpl.name;  // what user sees
      opt.title = tpl.description; // optional tooltip
      sel.appendChild(opt);
    });

  } catch (err) {
    console.error(err);
    sel.innerHTML = '<option>Error loading templates</option>';
  }
}

if (btnGenerateFromPrompt) {
  btnGenerateFromPrompt.addEventListener('click', async () => {
      console.log("CLICK FIRED");
      const tenantId = qs('#tenantIdPrompt').value;
      const modelId = qs('#promptModelId').value;
      const prompt = qs('#promptInput').value;
      const templateId = qs('#promptTemplate')?.value || null;

      const payload = { modelId, prompt, templateId };

      try {
          const res = await fetch(`/api/${tenantId}/models_from_prompt`, {
              method: "POST",
              headers: {
                  "Content-Type": "application/json",
                  "X-CSRFToken": getCSRFToken()
              },
              body: JSON.stringify(payload)
          });

          const data = await res.json();

          if (!data.ok) {
              showError(data.error || data.errors);
              return;
          }

          showSuccess(`Model ${data.modelId} created`);

          // Redirect back to Studio Home (no page reload)
          console.log("Redirecting to studioHome...");
          showSectionById("studioHome");

      } catch (err) {
          showError("Network or server error");
          console.error(err);
      }
  });
}

})();   // ← END OF IIFE — nothing should appear after this line