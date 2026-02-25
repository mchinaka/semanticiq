(function () {

  // ---------------------------------------------------------
  // ELEMENT REFERENCES
  // ---------------------------------------------------------
  const chatBox       = document.getElementById('chat-box');
  const chatInput     = document.getElementById('chat-input');
  const chatSend      = document.getElementById('chat-send');
  const modelSelect   = document.getElementById('model-select');
  const tenantIdEl    = document.getElementById('tenant-id');
  const actorIdEl     = document.getElementById('actor-id');
  const actorRolesEl  = document.getElementById('actor-roles');

  const entitySelect  = document.getElementById('entity-select');
  const loadBtn       = document.getElementById('load-form');
  const dynForm       = document.getElementById('dyn-form');
  const submitBtn     = document.getElementById('submit-form');
  const formResult    = document.getElementById('form-result');

  const backBtn       = document.getElementById("back-to-workspace");
  const actionBar     = document.getElementById("action-bar");

  const workspacePanel = document.getElementById("workspace-panel");
  const chatPanel      = document.getElementById("chat-panel");
  const formPanel      = document.getElementById("form-panel");


  // ---------------------------------------------------------
  // UTILITIES
  // ---------------------------------------------------------
  function addMsg(text, type) {
  if (!chatBox) return;
  if (!chatBox.classList.contains("expanded")) chatBox.classList.add("expanded");

  const msg = document.createElement("div");
  msg.className = "msg " + (type === "user" ? "user-msg" : "bot-msg");

  // Ensure text is ALWAYS a string
  let safeText = text;
  if (typeof safeText !== "string") {
    safeText = JSON.stringify(safeText, null, 2);
  }

  // Convert Markdown → HTML
  const html = marked.parse(safeText);

  msg.innerHTML = html;

  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
}

  function parseModelSelect() {
    const raw = modelSelect?.value || '';
    const parts = raw.split('::');
    return {
      model_id: parts[0] || '',
      version:  parts[1] || '1.0.0',
    };
  }

  function parseRoles(input) {
    return (input || '')
      .split(',')
      .map(s => s.trim())
      .filter(Boolean);
  }

  async function safeJson(res) {
    const text = await res.text();
    try { return JSON.parse(text); }
    catch { return { error: text || res.statusText }; }
  }


  // ---------------------------------------------------------
// CHAT LOGIC (Markdown-aware)
// ---------------------------------------------------------
async function sendChat() {
  const message = chatInput.value.trim();
  if (!message) return;

  // Show user message immediately
  addMsg(message, 'user');
  chatInput.value = '';

  const { model_id, version } = parseModelSelect();

  const payload = {
    tenant_id: tenantIdEl.value,
    model_id,
    version,
    message,
    actor_id: actorIdEl.value,
    actor_roles: parseRoles(actorRolesEl.value),
  };

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const json = await safeJson(res);
    console.log("CHAT RESPONSE:", json);

    if (!res.ok) {
      addMsg(`Error: ${json.error || res.statusText}`, 'bot');
      return;
    }

    // Ensure reply is a string
    if (json.reply && typeof json.reply !== "string") {
      console.warn("Non-string reply from backend:", json.reply);
      json.reply = JSON.stringify(json.reply, null, 2);
    }

    // 1. Conversational reply (knowledge, fallback, clarifications)
    if (json.reply && (!json.intent || json.state?.done === false)) {
      addMsg(json.reply, 'bot');
      return;
    }

    // 2. Workflow execution reply (intent + result)
    if (json.intent && json.result) {
      const friendly = renderFriendlyChatResponse(json.intent, json.result);
      addMsg(friendly, 'bot');
      return;
    }

    // 3. Fallback
    addMsg("I processed your request.", 'bot');

  } catch (e) {
    addMsg(`Network error: ${e}`, 'bot');
  }
}

chatSend?.addEventListener('click', sendChat);
chatInput?.addEventListener('keydown', e => {
  if (e.key === 'Enter') sendChat();
});

// ---------------------------------------------------------
// FRIENDLY WORKFLOW RESPONSE RENDERER (Markdown)
// ---------------------------------------------------------
function renderFriendlyChatResponse(intent, result) {
  let intentText = "";
  let resultText = "";

  const intentName = intent?.intent;
  const entityName = intent?.entity;

  const humanizeEntity = (name) =>
    name ? name.replace(/([A-Z])/g, " $1").trim() : "";

  if (intentName) {
    const readableIntent = intentName
      .replace(/([A-Z])/g, " $1")
      .trim()
      .toLowerCase(); // "create purchase order"

    const humanEntity = humanizeEntity(entityName); // "Purchase Order"

    if (humanEntity && !readableIntent.includes(humanEntity.toLowerCase())) {
      intentText = `I understood that you're trying to **${readableIntent}** for **${humanEntity}**.`;
    } else {
      intentText = `I understood that you're trying to **${readableIntent}**.`;
    }
  } else {
    intentText = "I processed your request.";
  }

  if (result?.action) {
    resultText = `The workflow has **${result.action.toLowerCase()}**.`;
  }

  if (result?.instance_id) {
    resultText += ` Reference ID: **${result.instance_id}**.`;
  }

  if (result?.state) {
    resultText += ` Current state: **${humanizeEntity(result.state)}**.`;
  }

  if (!resultText) resultText = "Here’s what I found.";

  return `${intentText}\n${resultText}`;
}

  // ---------------------------------------------------------
  // WORKSPACE NAVIGATION
  // ---------------------------------------------------------
  window.selectModel = function(modelId) {
    workspacePanel.style.display = "none";
    // Hide workspace action bar
    document.getElementById("workspace-action-bar").style.display = "none";
    chatPanel.style.display = "block";
    formPanel.style.display = "block";
    actionBar.style.display = "flex";

    if (modelSelect) modelSelect.value = modelId;

    loadEntities();
  };

  function backToWorkspace() {
    chatPanel.style.display = "none";
    formPanel.style.display = "none";
    actionBar.style.display = "none";
    workspacePanel.style.display = "block";
    // Show workspace action bar
    document.getElementById("workspace-action-bar").style.display = "flex";


  }

  backBtn.addEventListener("click", backToWorkspace);


  // ---------------------------------------------------------
  // ENTITY LOADER
  // ---------------------------------------------------------
  async function loadEntities() {
    entitySelect.innerHTML = '';

    const { model_id, version } = parseModelSelect();
    const tenantValue = tenantIdEl.value || '';

    const params = new URLSearchParams({
      tenant_id: tenantValue,
      model_id,
      version,
    });

    try {
      const res = await fetch(`/runtime/entities?${params.toString()}`);
      const text = await res.text();

      let data;
      try { data = JSON.parse(text); }
      catch { data = {}; }

      const entities = Array.isArray(data.entities) ? data.entities : [];

      if (entities.length) {
        entities.forEach(e => {
          const opt = document.createElement('option');
          opt.value = String(e);
          opt.textContent = String(e);
          entitySelect.appendChild(opt);
        });
        return;
      }

      // fallback
      ['PurchaseOrder', 'Vendor', 'Item', 'Approval'].forEach(e => {
        const opt = document.createElement('option');
        opt.value = e;
        opt.textContent = e;
        entitySelect.appendChild(opt);
      });

    } catch (err) {
      ['PurchaseOrder', 'Vendor', 'Item', 'Approval'].forEach(e => {
        const opt = document.createElement('option');
        opt.value = e;
        opt.textContent = e;
        entitySelect.appendChild(opt);
      });
    }
  }

  loadEntities();
  modelSelect?.addEventListener('change', loadEntities);


  // ---------------------------------------------------------
  // WORKFLOW ACTION DROPDOWN
  // ---------------------------------------------------------
  function buildActionDropdown(workflow, currentState = "Draft") {
    const select = document.getElementById("submit-mode");
    if (!select) return;

    select.innerHTML = "";

    const draftOpt = document.createElement("option");
    draftOpt.value = "Draft";
    draftOpt.textContent = "Save as Draft";
    select.appendChild(draftOpt);

    const transitions = workflow.transitions || [];
    const valid = transitions.filter(t => t.from === currentState);

    valid.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.event;
      opt.textContent = `Submit → ${t.to}`;
      select.appendChild(opt);
    });
  }


  // ---------------------------------------------------------
  // LOAD FORM SCHEMA + RENDER DYNAMIC FORM
  // ---------------------------------------------------------
  loadBtn?.addEventListener('click', async () => {

    dynForm.innerHTML = '';
    formResult.textContent = '';

    const entity = entitySelect.value;
    const { model_id, version } = parseModelSelect();

    if (!tenantIdEl.value || !model_id || !entity) {
      formResult.textContent = 'Please choose tenant, model and entity.';
      return;
    }

    const params = new URLSearchParams({
      tenant_id: tenantIdEl.value,
      model_id,
      version,
      entity,
    });

    try {
      const res = await fetch(`/runtime/form-schema?${params.toString()}`);
      const schema = await safeJson(res);

      if (!res.ok) {
        formResult.textContent = `Error loading form schema: ${schema.error || res.statusText}`;
        return;
      }

      // ---------------------------------------------------------
      // Render dynamic fields (using f.id + f.enum)
      // ---------------------------------------------------------
      for (const f of (schema.fields || [])) {

  console.log("Field:", f.name, "Options:", f.options);

  // APPROVER FIELD HANDLING
  if (f.name === "approver") {
    const users = await fetch(`/runtime/tenant-users?tenant_id=${tenantIdEl.value}`)
      .then(r => r.json());

    // Populate options dynamically
    f.options = users.map(u => ({label: u.full_name || u.username, value: u.username}));
    }

  const wrap = document.createElement('div');
  wrap.className = 'field';

  const label = document.createElement('label');
  label.textContent = f.label + (f.required ? ' *' : '');
  label.htmlFor = `dyn-${f.name}`;

  let input;

  // Dropdown if options exist
  if (Array.isArray(f.options) && f.options.length) {
    input = document.createElement('select');
    input.id = `dyn-${f.name}`;
    input.name = f.name;

    f.options.forEach(o => {
      const opt = document.createElement('option');
      if (typeof o === "string") {
        opt.value = o;
        opt.textContent = o;
      } else {
        opt.value = o.value;
        opt.textContent = o.label;
      }     
      input.appendChild(opt);
    });

  } else {
    // Fallback: input field
    input = document.createElement('input');
    input.id = `dyn-${f.name}`;
    input.name = f.name;

    if (f.type === 'number') input.type = 'number';
    else if (f.type === 'boolean') input.type = 'checkbox';
    else if (f.type === 'date') input.type = 'date';
    else input.type = 'text';

    if (f.required) input.required = true;
  }

    wrap.appendChild(label);
    wrap.appendChild(input);
    dynForm.appendChild(wrap);
    }

      if ((schema.fields || []).length === 0) {
        formResult.textContent = 'No fields defined for this entity.';
      }

      document.getElementById("action-row").classList.remove("hidden");
      document.getElementById("submit-form").classList.remove("hidden");

      if (schema.workflow) {
        buildActionDropdown(schema.workflow);
      }

    } catch (e) {
      formResult.textContent = `Network error loading schema: ${e}`;
    }
  });


  // ---------------------------------------------------------
  // SUBMIT FORM
  // ---------------------------------------------------------
  submitBtn?.addEventListener('click', async (e) => {
    e.preventDefault();
    formResult.textContent = '';

    const entity = entitySelect.value;
    const { model_id, version } = parseModelSelect();

    if (!tenantIdEl.value || !model_id || !entity) {
      formResult.textContent = 'Please choose tenant, model and entity.';
      return;
    }

    const eventName = document.getElementById("submit-mode")?.value || null;

    // Collect form data using f.id
    const data = {};
    Array.from(dynForm.elements).forEach(el => {
      if (!el.name) return;

      if (el.type === 'checkbox') data[el.name] = !!el.checked;
      else if (el.type === 'number') data[el.name] = el.value ? Number(el.value) : null;
      else data[el.name] = el.value || null;
    });

    const payload = {
      tenant_id: tenantIdEl.value,
      model_id,
      version,
      entity,
      data,
      actor_id: actorIdEl.value,
      actor_roles: parseRoles(actorRolesEl.value),
      event: eventName,      
    };

    try {
      const res = await fetch('/runtime/form-submit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
      });

      const json = await safeJson(res);

      if (!res.ok) {
        formResult.textContent = `Submit error: ${json.error || res.statusText}`;
        return;
      }

      renderFriendlyResult(json, entity, data);

      dynForm.querySelectorAll('.field').forEach(el => el.remove());

    } catch (e) {
      formResult.textContent = `Network error submitting form: ${e}`;
    }

    console.log("SUBMIT PAYLOAD:", payload);
  });


  // ---------------------------------------------------------
  // FRIENDLY RESULT
  // ---------------------------------------------------------
  function renderFriendlyResult(json, entity, data) {
    const workflowId = json.instance_id || json.id || "N/A";
    const status =
      json.instance?.state ||
      json.entity_instance?.state ||
      json.state ||
      json.status ||
      "Unknown";

    const approver =
      json.instance?.payload?.approver ||
      json.entity_instance?.payload?.approver ||
      json.data?.approver ||
      "N/A";

    const summaryHtml = `
      <div class="result-card">
        <h3>Workflow Started</h3>
        <div class="result-summary">
          <p><strong>Entity:</strong> ${entity}</p>
          <p><strong>Status:</strong> ${status}</p>
          <p><strong>Reference ID:</strong> ${workflowId}</p>
          <p><strong>Approver:</strong> ${approver}</p>
        </div>
        <button class="toggle-details">Show Details ▼</button>
        <div class="result-details">${JSON.stringify(json, null, 2)}</div>
      </div>
    `;

    formResult.innerHTML = summaryHtml;

    const toggleBtn = formResult.querySelector(".toggle-details");
    const detailsBox = formResult.querySelector(".result-details");

    toggleBtn.addEventListener("click", () => {
      const isOpen = detailsBox.style.display === "block";
      detailsBox.style.display = isOpen ? "none" : "block";
      toggleBtn.textContent = isOpen ? "Show Details ▼" : "Hide Details ▲";
    });
  }

  window.loadEntities = loadEntities;

  // ---------------------------------------------------------
// WORK ITEMS: My Workflows & My Approvals
// ---------------------------------------------------------
const workItemsPanel   = document.getElementById("work-items-panel");
const viewWorkItemsBtn = document.getElementById("view-work-items");
const myWorkflowsBody  = document.getElementById("my-workflows-body");
const myApprovalsBody  = document.getElementById("my-approvals-body");
const tabMyWorkflows   = document.getElementById("tab-my-workflows");
const tabMyApprovals   = document.getElementById("tab-my-approvals");
const myWorkflowsView  = document.getElementById("my-workflows-view");
const myApprovalsView  = document.getElementById("my-approvals-view");

viewWorkItemsBtn?.addEventListener("click", () => {
  // Show panel, hide others if you want
  workItemsPanel.classList.remove("hidden");
  loadMyWorkflows();
  loadMyApprovals();
});

tabMyWorkflows?.addEventListener("click", () => {
  tabMyWorkflows.classList.add("active");
  tabMyApprovals.classList.remove("active");
  myWorkflowsView.classList.remove("hidden");
  myApprovalsView.classList.add("hidden");
});

tabMyApprovals?.addEventListener("click", () => {
  tabMyApprovals.classList.add("active");
  tabMyWorkflows.classList.remove("active");
  myApprovalsView.classList.remove("hidden");
  myWorkflowsView.classList.add("hidden");
});

async function loadMyWorkflows() {
  myWorkflowsBody.innerHTML = "";

  const { model_id, version } = parseModelSelect();
  const actorId = actorIdEl.value;

  const params = new URLSearchParams({
    tenant_id: tenantIdEl.value,
    model_id,
    version,
    actor_id: actorId,
  });

  try {
    const res = await fetch(`/runtime/workflows?${params.toString()}`);
    const items = await res.json();

    items.forEach(wf => {
      const tr = document.createElement("tr");

      const created = wf.created_at ? new Date(wf.created_at).toLocaleString() : "";
      const updated = wf.updated_at ? new Date(wf.updated_at).toLocaleString() : "";

      tr.innerHTML = `
        <td style="display:none;">${wf.instance_id}</td>
        <td>${wf.entity}</td>
        <td>${wf.state}</td>
        <td>${created}</td>
        <td>${updated}</td>
      `;

      tr.addEventListener("click", () => openWorkflowDetail(wf));
      myWorkflowsBody.appendChild(tr);
    });

  } catch (e) {
    console.error("Error loading my workflows", e);
  }
}

async function loadMyApprovals() {
  myApprovalsBody.innerHTML = "";

  const { model_id, version } = parseModelSelect();
  const actorId = actorIdEl.value;

  const params = new URLSearchParams({
    tenant_id: tenantIdEl.value,
    model_id,
    version,
    actor_id: actorId,
  });

  try {
    const res = await fetch(`/runtime/pending-approvals?${params.toString()}`);
    const items = await res.json();

    items.forEach(wf => {
      const tr = document.createElement("tr");

      const payload = wf.payload || {};
      const summary = `${payload.invoiceNumber || ""} ${payload.amount || ""} ${payload.currency || ""}`.trim();
      const createdBy = payload.created_by || "N/A";

      tr.innerHTML = `
        <td style="display:none;">${wf.instance_id}</td>
        <td>${wf.entity}</td>
        <td>${createdBy}</td>
        <td>${summary}</td>
        <td>${wf.state}</td>
        <td>
          <button class="approve-btn">Approve</button>
          <button class="reject-btn">Reject</button>
        </td>
      `;

      const approveBtn = tr.querySelector(".approve-btn");
      const rejectBtn  = tr.querySelector(".reject-btn");

      approveBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        triggerApprovalAction(wf, "approve");
      });

      rejectBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        triggerApprovalAction(wf, "reject");
      });

      tr.addEventListener("click", () => openWorkflowDetail(wf));
      myApprovalsBody.appendChild(tr);
    });

  } catch (e) {
    console.error("Error loading my approvals", e);
  }
}

async function triggerApprovalAction(wf, eventName) {
  const { model_id, version } = parseModelSelect();

  const payload = {
    tenant_id: tenantIdEl.value,
    model_id,
    version,
    entity: wf.entity,
    instance_id: wf.instance_id,
    data: {}, // no extra fields for now
    actor_id: actorIdEl.value,
    actor_roles: parseRoles(actorRolesEl.value),
    event: eventName,
  };

  try {
    const res = await fetch('/runtime/transition', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });

    const json = await res.json();

    if (!res.ok) {
      alert(`Error: ${json.error || res.statusText}`);
      return;
    }

    // Refresh lists after action
    loadMyApprovals();
    loadMyWorkflows();

  } catch (e) {
    console.error("Error triggering approval action", e);
  }
}

// Simple detail view hook – you can wire this into your existing result card if you like
function openWorkflowDetail(wf) {
  console.log("WORKFLOW DETAIL:", wf);
  // You could reuse renderFriendlyResult here with a small adapter if needed
}


})();