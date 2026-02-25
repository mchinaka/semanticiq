
// semanticiq/core/static/core/studio.js
(function () {
  const qs = sel => document.querySelector(sel);

  // Original core elements
  const tenantIdEl = qs('#tenantId');
  const modelIdEl  = qs('#modelId');
  const btnLoad    = qs('#btnLoad');
  const btnSave    = qs('#btnSave');
  const btnPublish = qs('#btnPublish');
  const entitySel  = qs('#entitySelect');
  const attrWrap   = qs('#attributes');
  const btnAddAttr = qs('#btnAddAttribute');
  const btnAddEnt  = qs('#btnAddEntity');
  const btnRmEnt   = qs('#btnRemoveEntity');
  const jsonEditor = qs('#jsonEditor');
  const btnFormat  = qs('#btnFormat');
  const btnExport  = qs('#btnExport');
  const status     = qs('#status');

  // Optional features
  const btnValidate     = qs('#btnValidate');
  const validateOut     = qs('#validateOut');
  const tabs            = Array.from(document.querySelectorAll('.tab'));
  const paneAttrs       = qs('#pane-attributes');
  const paneRels        = qs('#pane-relationships');
  const relationshipsEl = qs('#relationships');
  const relEntityName   = qs('#relEntityName');
  const btnAddRel       = qs('#btnAddRelationship');

  // New view switcher
  const viewTabs   = Array.from(document.querySelectorAll('.view-tab'));
  const viewJSON   = qs('#view-json');
  const viewTable  = qs('#view-table');
  const viewGraph  = qs('#view-graph');
  const modelTable = qs('#modelTable');
  const modelGraph = qs('#modelGraph');
  const patchEditor= qs('#patchEditor');
  const btnApplyPatch = qs('#btnApplyPatch');

  let model = null;

  function setStatus(msg){ if (status) status.textContent = 'Status: ' + msg; }
  function setButtons(enabled){
    if (btnSave)    btnSave.disabled    = !enabled;
    if (btnPublish) btnPublish.disabled = !enabled;
    if (btnValidate)btnValidate.disabled= !enabled;
  }

  // ---------- ORIGINAL: Entities & Attributes ----------
  function renderEntities(){
    if (!entitySel) return;
    entitySel.innerHTML = '';
    if(!model || !Array.isArray(model.entities)) return;
    model.entities.forEach(e => {
      const opt = document.createElement('option');
      opt.value = e.id; opt.textContent = e.label || e.id;
      entitySel.appendChild(opt);
    });
    renderAttributes();
    renderRelationships();
    renderTableView();     // refresh table if visible
    renderGraphView();     // refresh graph if visible
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
      if (idEl)  idEl.addEventListener('input',  e => { a.id = e.target.value; syncEditor(); });
      if (typeEl)typeEl.addEventListener('change', e => { a.type = e.target.value; syncEditor(); });
      if (reqEl) reqEl.addEventListener('change', e => { a.required = e.target.checked; syncEditor(); });
      if (defEl) defEl.addEventListener('input',  e => { a.default = e.target.value; syncEditor(); });
      attrWrap.appendChild(row);
    });
  }

  function syncEditor(){ if (jsonEditor){ jsonEditor.value = JSON.stringify(model, null, 2); } setButtons(true); }

  // ---------- ORIGINAL: Load / Save / Publish ----------
  if (btnLoad) {
    btnLoad.addEventListener('click', async () => {
      if (!tenantIdEl || !modelIdEl) { setStatus('error: missing tenant/model inputs'); return; }
      const tenantId = tenantIdEl.value.trim();
      const modelId  = modelIdEl.value.trim();
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
      const modelId  = modelIdEl.value.trim();
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
        renderTableView(); renderGraphView();
      }catch(err){ setStatus('error: '+err.message); }
    });
  }

  if (btnPublish) {
    btnPublish.addEventListener('click', async ()=>{
      if (!tenantIdEl || !modelIdEl) { setStatus('error: missing tenant/model inputs'); return; }
      const tenantId = tenantIdEl.value.trim();
      const modelId  = modelIdEl.value.trim();
      setStatus('publishing...');
      try{
        const res = await fetch(`/api/tenants/${tenantId}/models/${modelId}/publish`, { method:'POST' });
        if(!res.ok){ throw new Error(await res.text()); }
        setStatus('published');
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
      renderTableView(); renderGraphView();
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
      renderTableView(); renderGraphView();
    });
  }

  if (btnRmEnt) {
    btnRmEnt.addEventListener('click', () => {
      if(!model) return;
      const id = entitySel && entitySel.value;
      model.entities = (model.entities||[]).filter(e => e.id !== id);
      renderEntities();
      syncEditor();
      renderTableView(); renderGraphView();
    });
  }

  // ---------- ORIGINAL: Format / Export ----------
  if (btnFormat) {
    btnFormat.addEventListener('click', ()=>{
      try{ const obj = JSON.parse(jsonEditor.value); jsonEditor.value = JSON.stringify(obj, null, 2); setStatus('formatted'); }
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
      const modelId  = modelIdEl.value.trim();
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
        <input class="rto" value="${r.to || ''}" placeholder="to entity (e.g., Vendor)" />
        <select class="rcard">
          ${['one-to-one','one-to-many','many-to-one','many-to-many'].map(c => `<option ${r.cardinality===c?'selected':''}>${c}</option>`).join('')}
        </select>
        <input class="rkmfrom" value="${(r.keyMapping||{}).fromAttr || ''}" placeholder="keyMapping.fromAttr" />
      `;
      row.querySelector('.rid')   .addEventListener('input',  e => { r.id = e.target.value; syncEditor(); renderGraphView(); });
      row.querySelector('.rtype') .addEventListener('change', e => { r.type = e.target.value; syncEditor(); renderGraphView(); });
      row.querySelector('.rto')   .addEventListener('input',  e => { r.to = e.target.value; syncEditor(); renderGraphView(); });
      row.querySelector('.rcard') .addEventListener('change', e => { r.cardinality = e.target.value; syncEditor(); renderGraphView(); });
      row.querySelector('.rkmfrom').addEventListener('input', e => {
        r.keyMapping = r.keyMapping || {}; r.keyMapping.fromAttr = e.target.value; syncEditor(); renderGraphView();
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
      const modelId  = modelIdEl.value.trim();
      setStatus('applying patch...');
      let ops;
      try { ops = JSON.parse(patchEditor.value || '[]'); if (!Array.isArray(ops)) throw 0; }
      catch { setStatus('invalid patch JSON'); return; }
      try{
        const res = await fetch(`/api/tenants/${tenantId}/models/${modelId}/patch`, {
          method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(ops)
        });
        const payload = await res.json().catch(()=>({ok:false,error:'invalid server response'}));
        if (!res.ok || !payload.ok) throw new Error(payload.error || 'Patch error');
        model = payload.model;
        syncEditor(); renderEntities();
        setStatus('patch applied');
      }catch(err){ setStatus('error: '+err.message); }
    });
  }

  // ---------- NEW: View switcher (JSON/Table/Graph) ----------
  function showView(name){
    if (viewJSON)  viewJSON.style.display  = (name==='json')  ? '' : 'none';
    if (viewTable) viewTable.style.display = (name==='table') ? '' : 'none';
    if (viewGraph) viewGraph.style.display = (name==='graph') ? '' : 'none';
    viewTabs.forEach(v => v.classList.toggle('active', v.getAttribute('data-view')===name));
    if (name==='table') renderTableView();
    if (name==='graph') renderGraphView();
  }

  if (viewTabs.length) {
    viewTabs.forEach(v => v.addEventListener('click', () => showView(v.getAttribute('data-view')||'json')));
  }

  // ---------- NEW: Table renderer ----------
  function renderTableView(){
    if (!modelTable || !model || !Array.isArray(model.entities)) return;
    const rows = [];
    model.entities.forEach(e => {
      (e.attributes || []).forEach(a => {
        rows.push({
          entity: e.label || e.id,
          attr: a.id,
          type: a.type || '',
          required: !!a.required,
          default: (a.default!==undefined && a.default!==null) ? String(a.default) : ''
        });
      });
    });
    if (rows.length===0) { modelTable.innerHTML = '<p>No attributes to display.</p>'; return; }
    const html = `
      <table>
        <thead>
          <tr><th>Entity</th><th>Attribute</th><th>Type</th><th>Required</th><th>Default</th></tr>
        </thead>
        <tbody>
          ${rows.map(r=>`
            <tr>
              <td>${escapeHTML(r.entity)}</td>
              <td>${escapeHTML(r.attr)}</td>
              <td>${escapeHTML(r.type)}</td>
              <td>${r.required ? 'Yes' : 'No'}</td>
              <td>${escapeHTML(r.default)}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    `;
    modelTable.innerHTML = html;
  }

  // ---------- NEW: Graph renderer (simple layout) ----------
  function renderGraphView(){
    if (!modelGraph || !model || !Array.isArray(model.entities)) return;
    const svg = modelGraph;
    // clear
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    // layout: place nodes in a grid
    const entities = model.entities.map((e, i) => ({
      id: e.id,
      label: e.label || e.id,
      x: 100 + (i % 4) * 180,
      y: 80 + Math.floor(i / 4) * 140
    }));

    // draw relations as arrows
    model.entities.forEach(e => {
      (e.relationships || []).forEach(r => {
        const from = entities.find(n => n.id === e.id);
        const to   = entities.find(n => n.id === r.to);
        if (!from || !to) return;
        const line = createSVG('line', {
          x1: from.x, y1: from.y, x2: to.x, y2: to.y,
          stroke: '#888', 'stroke-width': 1.5, 'marker-end': 'url(#arrow)'
        });
        svg.appendChild(line);

        const midx = (from.x + to.x)/2, midy = (from.y + to.y)/2;
        const label = createSVG('text', { x: midx, y: midy - 5, 'font-size': 11, fill: '#555', 'text-anchor':'middle' });
        label.textContent = r.type || 'rel';
        svg.appendChild(label);
      });
    });

    // defs: arrow marker
    const defs = createSVG('defs', {});
    const marker = createSVG('marker', { id:'arrow', viewBox:'0 0 10 10', refX:'8', refY:'5', markerWidth:'6', markerHeight:'6', orient:'auto-start-reverse' });
    marker.appendChild(createSVG('path', { d:'M 0 0 L 10 5 L 0 10 z', fill:'#888' }));
    defs.appendChild(marker);
    svg.appendChild(defs);

    // draw nodes
    entities.forEach(n => {
      const g = createSVG('g', {});
      const rect = createSVG('rect', { x: n.x-50, y: n.y-24, width: 100, height: 48, rx:8, ry:8, fill:'#fff', stroke:'#9ec5fe', 'stroke-width':1.5 });
      const text = createSVG('text', { x: n.x, y: n.y, 'text-anchor':'middle', 'dominant-baseline':'middle', 'font-size':12, fill:'#333' });
      text.textContent = n.label;
      g.appendChild(rect);
      g.appendChild(text);
      svg.appendChild(g);
    });
  }

  // Utils
  function createSVG(tag, attrs){
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([k,v]) => el.setAttribute(k,v));
    return el;
  }
  function escapeHTML(str){
    return String(str).replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[s]));
  }

  // ---------- View tabs wiring ----------
  function showView(name){
    if (viewJSON)  viewJSON.style.display  = (name==='json')  ? '' : 'none';
    if (viewTable) viewTable.style.display = (name==='table') ? '' : 'none';
    if (viewGraph) viewGraph.style.display = (name==='graph') ? '' : 'none';
    viewTabs.forEach(v => v.classList.toggle('active', v.getAttribute('data-view')===name));
    if (name==='table') renderTableView();
    if (name==='graph') renderGraphView();
  }
  if (viewTabs.length){
    viewTabs.forEach(v => v.addEventListener('click', () => showView(v.getAttribute('data-view')||'json')));
  }

  // ---------- Keep original initial state ----------
  setButtons(false);
  setStatus('idle');
})();
