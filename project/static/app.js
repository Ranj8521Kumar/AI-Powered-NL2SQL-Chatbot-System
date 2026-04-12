/**
 * app.js — NL2SQL Chatbot Frontend
 *
 * Handles:
 *  - Sending questions to POST /chat
 *  - Rendering chat messages, SQL blocks, data tables, and Plotly charts
 *  - Health check polling
 *  - Sidebar suggestion chips
 *  - Auto-resizing textarea
 */

'use strict';

// ── Suggested questions (sidebar + welcome chips) ─────────────────────────────
const SUGGESTIONS = [
  'How many patients do we have?',
  'List all doctors and their specializations',
  'Show me appointments for last month',
  'Which doctor has the most appointments?',
  'What is the total revenue?',
  'Show revenue by doctor',
  'How many cancelled appointments last quarter?',
  'Top 5 patients by spending',
  'Average treatment cost by specialization',
  'Show monthly appointment count for the past 6 months',
  'Which city has the most patients?',
  'List patients who visited more than 3 times',
  'Show unpaid invoices',
  'What percentage of appointments are no-shows?',
  'Show the busiest day of the week for appointments',
  'Revenue trend by month',
  'Average appointment duration by doctor',
  'List patients with overdue invoices',
  'Compare revenue between departments',
  'Show patient registration trend by month',
];

// ── DOM refs ──────────────────────────────────────────────────────────────────
const chatWindow      = document.getElementById('chatWindow');
const messages        = document.getElementById('messages');
const welcomeScreen   = document.getElementById('welcomeScreen');
const welcomeChips    = document.getElementById('welcomeChips');
const questionInput   = document.getElementById('questionInput');
const sendBtn         = document.getElementById('sendBtn');
const newChatBtn      = document.getElementById('newChatBtn');
const sidebarToggle   = document.getElementById('sidebarToggle');
const sidebar         = document.getElementById('sidebar');
const suggestionList  = document.getElementById('suggestionList');
const healthDot       = document.getElementById('healthDot');
const healthText      = document.getElementById('healthText');

// ── State ─────────────────────────────────────────────────────────────────────
let isLoading = false;

// ── Init ──────────────────────────────────────────────────────────────────────
function init() {
  populateSuggestions();
  checkHealth();
  bindEvents();
  autoResize();
}

// ── Suggestions ────────────────────────────────────────────────────────────────
function populateSuggestions() {
  // Sidebar list
  let isExpanded = false;
  const suggestionElements = [];

  SUGGESTIONS.forEach((q, index) => {
    const btn = document.createElement('button');
    btn.className = 'suggestion-item';
    btn.textContent = q;
    btn.title = q;
    if (index >= 10) {
      btn.style.display = 'none'; // Initially hidden
    }
    btn.addEventListener('click', () => submitQuestion(q));
    suggestionList.appendChild(btn);
    suggestionElements.push(btn);
  });

  // Expandable button
  const toggleBtn = document.createElement('button');
  toggleBtn.className = 'suggestion-toggle-btn';
  toggleBtn.innerHTML = `<span>Show all 20 questions</span>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="6 9 12 15 18 9"></polyline>
    </svg>`;
  
  toggleBtn.addEventListener('click', () => {
    isExpanded = !isExpanded;
    suggestionElements.forEach((btn, idx) => {
      if (idx >= 10) {
        btn.style.display = isExpanded ? 'block' : 'none';
      }
    });
    toggleBtn.innerHTML = isExpanded 
      ? `<span>Show fewer questions</span>
         <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
           <polyline points="18 15 12 9 6 15"></polyline>
         </svg>`
      : `<span>Show all 20 questions</span>
         <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
           <polyline points="6 9 12 15 18 9"></polyline>
         </svg>`;
  });
  
  suggestionList.appendChild(toggleBtn);

  // Welcome chips (first 6)
  SUGGESTIONS.slice(0, 6).forEach(q => {
    const chip = document.createElement('button');
    chip.className = 'chip';
    chip.textContent = q;
    chip.addEventListener('click', () => submitQuestion(q));
    welcomeChips.appendChild(chip);
  });
}

// ── Health check ──────────────────────────────────────────────────────────────
async function checkHealth() {
  healthDot.className = 'dot loading';
  healthText.textContent = 'Connecting...';
  try {
    const res  = await fetch('/health');
    const data = await res.json();
    if (data.status === 'ok' && data.database === 'connected') {
      healthDot.className  = 'dot ok';
      healthText.textContent = `Live · ${data.agent_memory_items} examples`;
    } else {
      throw new Error('DB not connected');
    }
  } catch {
    healthDot.className  = 'dot error';
    healthText.textContent = 'Offline';
  }
}

// ── Event bindings ────────────────────────────────────────────────────────────
function bindEvents() {
  sendBtn.addEventListener('click', () => {
    const q = questionInput.value.trim();
    if (q) submitQuestion(q);
  });

  questionInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const q = questionInput.value.trim();
      if (q && !isLoading) submitQuestion(q);
    }
  });

  questionInput.addEventListener('input', autoResize);

  newChatBtn.addEventListener('click', clearChat);

  sidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
  });
}

// ── Auto-resize textarea ──────────────────────────────────────────────────────
function autoResize() {
  questionInput.style.height = 'auto';
  questionInput.style.height = Math.min(questionInput.scrollHeight, 160) + 'px';
}

// ── Submit question ───────────────────────────────────────────────────────────
async function submitQuestion(question) {
  if (isLoading) return;

  // Hide welcome screen on first question
  if (welcomeScreen.style.display !== 'none') {
    welcomeScreen.style.display = 'none';
  }

  questionInput.value = '';
  autoResize();

  // Render user bubble
  appendUserMessage(question);

  // Show loading indicator
  const loadingEl = appendLoading();
  setLoading(true);

  try {
    const res  = await fetch('/chat', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ question }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    loadingEl.remove();
    appendAssistantMessage(data, question);

  } catch (err) {
    loadingEl.remove();
    appendErrorMessage('Could not reach the server. Is it running?');
    console.error(err);
  } finally {
    setLoading(false);
    scrollToBottom();
  }
}

// ── Loading state ─────────────────────────────────────────────────────────────
function setLoading(state) {
  isLoading = state;
  sendBtn.disabled = state;
  questionInput.disabled = state;
}

// ── Render: user message ──────────────────────────────────────────────────────
function appendUserMessage(question) {
  const group = document.createElement('div');
  group.className = 'message-group';

  const bubble = document.createElement('div');
  bubble.className = 'bubble-user';
  bubble.textContent = question;

  group.appendChild(bubble);
  messages.appendChild(group);
  scrollToBottom();
}

// ── Render: loading dots ──────────────────────────────────────────────────────
function appendLoading() {
  const group = document.createElement('div');
  group.className = 'message-group';

  const label = document.createElement('div');
  label.className = 'assistant-label';
  label.textContent = 'NL2SQL';

  const dots = document.createElement('div');
  dots.className = 'loading-dots';
  for (let i = 0; i < 3; i++) dots.appendChild(document.createElement('span'));

  group.appendChild(label);
  group.appendChild(dots);
  messages.appendChild(group);
  scrollToBottom();
  return group;
}

// ── Render: assistant message ─────────────────────────────────────────────────
function appendAssistantMessage(data, question) {
  const group = document.createElement('div');
  group.className = 'message-group';

  const label = document.createElement('div');
  label.className = 'assistant-label';
  label.textContent = 'NL2SQL';
  group.appendChild(label);

  const wrapper = document.createElement('div');
  wrapper.className = 'bubble-assistant';

  // Error state
  if (data.error && !data.sql_query) {
    const err = document.createElement('div');
    err.className = 'bubble-error';
    err.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>${escHtml(data.message || data.error)}`;
    wrapper.appendChild(err);
    group.appendChild(wrapper);
    messages.appendChild(group);
    return;
  }

  // Summary message
  const msg = document.createElement('div');
  msg.className = 'result-message';
  msg.innerHTML = renderMarkdownBold(escHtml(data.message || ''));
  wrapper.appendChild(msg);

  // SQL block
  if (data.sql_query) {
    wrapper.appendChild(buildSqlBlock(data.sql_query));
  }

  // Data table
  if (data.columns && data.columns.length > 0 && data.rows && data.rows.length > 0) {
    wrapper.appendChild(buildTable(data.columns, data.rows, data.row_count));
  }

  // Chart
  if (data.chart) {
    wrapper.appendChild(buildChart(data.chart, data.chart_type));
  }

  // Timing
  if (data.execution_time_ms) {
    const t = document.createElement('div');
    t.className = 'timing';
    t.textContent = `${data.execution_time_ms}ms`;
    wrapper.appendChild(t);
  }

  group.appendChild(wrapper);
  messages.appendChild(group);
}

// ── Render: error ─────────────────────────────────────────────────────────────
function appendErrorMessage(text) {
  const group = document.createElement('div');
  group.className = 'message-group';

  const err = document.createElement('div');
  err.className = 'bubble-error';
  err.textContent = text;
  group.appendChild(err);
  messages.appendChild(group);
}

// ── Build: SQL block ──────────────────────────────────────────────────────────
function buildSqlBlock(sql) {
  const block = document.createElement('div');
  block.className = 'sql-block';

  const header = document.createElement('div');
  header.className = 'sql-header';
  header.innerHTML = `
    <span class="sql-label">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
      </svg>
      SQL Query
    </span>
    <span class="sql-actions">
      <button class="copy-btn" title="Copy SQL">Copy</button>
      <span class="chevron">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </span>
    </span>`;

  const body = document.createElement('div');
  body.className = 'sql-body';

  const code = document.createElement('code');
  code.className = 'sql-code';
  code.innerHTML = highlightSQL(sql);

  body.appendChild(code);
  block.appendChild(header);
  block.appendChild(body);

  // Toggle open/close
  const chevron = header.querySelector('.chevron');
  header.addEventListener('click', () => {
    body.classList.toggle('open');
    chevron.classList.toggle('open');
  });

  // Auto-open on load
  body.classList.add('open');
  chevron.classList.add('open');

  // Copy button
  const copyBtn = header.querySelector('.copy-btn');
  copyBtn.addEventListener('click', e => {
    e.stopPropagation();
    navigator.clipboard.writeText(sql).then(() => {
      copyBtn.textContent = 'Copied!';
      setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1500);
    });
  });

  return block;
}

// ── Build: data table ─────────────────────────────────────────────────────────
function buildTable(columns, rows, rowCount) {
  const block = document.createElement('div');
  block.className = 'table-block';

  const meta = document.createElement('div');
  meta.className = 'table-meta';
  const showing = Math.min(rows.length, 50);
  meta.innerHTML = `<span>Results</span><span>${showing}${rowCount > 50 ? ' of ' + rowCount : ''} row${rowCount !== 1 ? 's' : ''}</span>`;
  block.appendChild(meta);

  const scroll = document.createElement('div');
  scroll.className = 'table-scroll';

  const table = document.createElement('table');
  const thead = document.createElement('thead');
  const tbody = document.createElement('tbody');

  const headerRow = document.createElement('tr');
  columns.forEach(col => {
    const th = document.createElement('th');
    th.textContent = col.replace(/_/g, ' ');
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);

  // Show max 50 rows
  rows.slice(0, 50).forEach(row => {
    const tr = document.createElement('tr');
    row.forEach(cell => {
      const td = document.createElement('td');
      td.textContent = cell === null ? '—' : cell;
      td.title = cell === null ? 'NULL' : String(cell);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });

  table.appendChild(thead);
  table.appendChild(tbody);
  scroll.appendChild(table);
  block.appendChild(scroll);
  return block;
}

// ── Build: Plotly chart ───────────────────────────────────────────────────────
function buildChart(chartDict, chartType) {
  const block = document.createElement('div');
  block.className = 'chart-block';

  const meta = document.createElement('div');
  meta.className = 'chart-meta';
  meta.textContent = `Visualization · ${chartType || 'chart'}`;
  block.appendChild(meta);

  const container = document.createElement('div');
  container.className = 'chart-container';
  const plotDiv = document.createElement('div');
  plotDiv.style.width  = '100%';
  plotDiv.style.height = '320px';
  container.appendChild(plotDiv);
  block.appendChild(container);

  // Defer to ensure element is in DOM
  setTimeout(() => {
    try {
      Plotly.newPlot(plotDiv, chartDict.data || [], chartDict.layout || {}, {
        responsive:  true,
        displaylogo: false,
        modeBarButtonsToRemove: ['sendDataToCloud', 'select2d', 'lasso2d'],
      });
    } catch (e) {
      plotDiv.textContent = 'Chart render failed: ' + e.message;
      console.error(e);
    }
  }, 50);

  return block;
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function scrollToBottom() {
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function clearChat() {
  messages.innerHTML = '';
  welcomeScreen.style.display = '';
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderMarkdownBold(str) {
  return str.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
}

function highlightSQL(sql) {
  const keywords = /\b(SELECT|FROM|WHERE|JOIN|ON|GROUP BY|ORDER BY|HAVING|LIMIT|OFFSET|LEFT|RIGHT|INNER|OUTER|AS|AND|OR|NOT|IN|LIKE|IS|NULL|COUNT|SUM|AVG|MIN|MAX|DISTINCT|CASE|WHEN|THEN|ELSE|END|WITH|UNION|ALL|BY|ASC|DESC|BETWEEN|EXISTS)\b/gi;
  const strings  = /'([^']*)'/g;
  const nums     = /\b(\d+(?:\.\d+)?)\b/g;

  return escHtml(sql)
    .replace(keywords, '<span class="kw">$&</span>')
    .replace(strings,  '<span class="str">\'$1\'</span>')
    .replace(nums,     '<span class="num">$1</span>');
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
