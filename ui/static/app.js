// RubixCON Lab UI. Plain JS, no framework, no libraries.
// Safety rule: model, attacker, catalogue and trace text is ALWAYS inserted with
// textContent (see el()), never innerHTML. Handlers are attached in JS (the CSP forbids inline ones).
"use strict";

const TOKEN = document.querySelector('meta[name="lab-token"]').content;
const MAIN = document.getElementById("main");
const WELCOME = MAIN.querySelector(".welcome").cloneNode(true); // the start page text from index.html
const PATTERN_ORDER = ["02", "04", "05", "03"];                  // workshop blocks 3-6
let CAT = null;   // the catalogue from /api/catalog
let JOB = null;   // {id, n, done, view, es, fails}
let VIEW = null;  // the view on screen
let RUNSEQ = 0;   // guards against two quick clicks on Run

// ------------------------------------------------------------------ helpers
function el(tag, cls, text, kids) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = String(text);
  for (const k of kids || []) if (k) e.appendChild(k);
  return e;
}
function btn(label, onClick, cls) {
  const b = el("button", cls, label);
  b.type = "button";
  b.addEventListener("click", onClick);
  return b;
}
function panel(title, kids) { return el("section", "panel", null, [title ? el("h2", null, title) : null, ...(kids || [])]); }
function field(label, input) { return el("div", null, null, [el("label", null, label), input]); }
function textInput(value, placeholder) {
  const i = el("input"); i.type = "text"; i.value = value || ""; i.placeholder = placeholder || ""; return i;
}
function textArea(value, rows) { const t = el("textarea"); t.value = value || ""; t.rows = rows || 4; return t; }
function checkbox(label, checked) {
  const box = el("input"); box.type = "checkbox"; box.checked = !!checked;
  return { box, root: el("label", "check", null, [box, el("span", null, label)]) };
}
function nearBottom(box) { return box.scrollHeight - box.scrollTop - box.clientHeight < 80; }
function store(key, value) { try { value === null ? sessionStorage.removeItem(key) : sessionStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* private mode */ } }
function load(key) { try { return JSON.parse(sessionStorage.getItem(key)); } catch (_) { return null; } }

// Enter sends, Shift+Enter makes a new line.
function onEnter(textarea, send) {
  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); }
  });
}

async function api(path, body) {
  const opts = { headers: { "X-Lab-Token": TOKEN } };
  if (body !== undefined) {
    opts.method = "POST";
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(path, opts);
  let data = {};
  try { data = await r.json(); } catch (_) { /* not JSON */ }
  if (!r.ok) throw new Error(data.error || `${r.status} ${r.statusText}`);
  return data;
}

// ------------------------------------------------------------------ jobs
// One run at a time. Events stream over SSE; `n` counts what we received so a
// reconnect asks only for the rest (the browser's own retry would start at 0).
async function startJob(req, view) {
  const seq = ++RUNSEQ;
  closeJob(); // the server also stops the old run when the new one starts
  view.onStart();
  let res;
  try {
    res = await api("/api/run", req);
  } catch (e) {
    view.onEvent({ kind: "error", text: `could not start: ${e.message}` });
    view.onEvent({ kind: "done" });
    return;
  }
  if (seq !== RUNSEQ) return; // a newer run replaced this one
  attach(res.job, view);
}

function attach(id, view) {
  JOB = { id, n: 0, done: false, view, es: null, fails: 0 };
  store("lab-job", { id, route: location.hash });
  listen(JOB);
}

function listen(job) {
  const es = new EventSource(`/api/events?job=${encodeURIComponent(job.id)}&since=${job.n}&token=${encodeURIComponent(TOKEN)}`);
  job.es = es;
  es.onmessage = (m) => {
    if (JOB !== job) { es.close(); return; }
    job.n += 1;
    job.fails = 0;
    let ev;
    try { ev = JSON.parse(m.data); } catch (_) { ev = { kind: "console", text: m.data }; }
    if (ev.kind === "done") { job.done = true; es.close(); store("lab-job", null); }
    try { job.view.onEvent(ev); } catch (err) { console.error(err); }
  };
  es.onerror = () => {
    es.close();
    if (JOB !== job || job.done) return;
    job.fails += 1;
    if (job.fails > 4) { // the server forgot the job (restart) or is gone
      job.done = true;
      store("lab-job", null);
      job.view.onEvent({ kind: "error", text: "lost the event stream (is the server still running?)" });
      job.view.onEvent({ kind: "done" });
      return;
    }
    setTimeout(() => { if (JOB === job && !job.done) listen(job); }, 400 * job.fails);
  };
}

// Stop the run and stop listening to it (new run, or leaving the view).
function closeJob() {
  if (!JOB) return;
  if (!JOB.done) api("/api/stop", { job: JOB.id }).catch(() => {});
  if (JOB.es) JOB.es.close();
  JOB = null;
  store("lab-job", null);
}
function stopJob() { if (JOB && !JOB.done) api("/api/stop", { job: JOB.id }).catch(() => {}); }

async function reply(text) {
  if (!JOB || JOB.done) return;
  try { await api("/api/reply", { job: JOB.id, text }); }
  catch (e) { JOB.view.onEvent({ kind: "error", text: `reply failed: ${e.message}` }); }
}

// ------------------------------------------------------------------ shared panels
function promptsPanel(title) {
  const list = el("div");
  const root = panel(title || "What each model saw", [el("p", "muted", "Every prompt sent to a model in this run, newest first."), list]);
  let last = null;
  return {
    root,
    reset() { list.replaceChildren(); last = null; },
    onEvent(ev) {
      if (ev.kind === "llm") last = ev;
      if (ev.kind !== "llm_io") return;
      const head = last ? `${last.purpose} · ${last.role} · ${last.model}` : "model call";
      const io = el("div", "io");
      for (const m of ev.messages || []) {
        io.appendChild(el("div", "role", m.role));
        io.appendChild(el("pre", null, m.content));
      }
      io.appendChild(el("div", "role", "reply"));
      io.appendChild(el("pre", null, ev.reply));
      list.prepend(el("details", "ev llm", null, [el("summary", null, head), io]));
      last = null;
    },
  };
}

function emailsPanel() {
  const list = el("div", null, null, [el("p", "muted", "No email sent yet.")]);
  const root = panel("Emails sent", [list]);
  return {
    root,
    reset() { list.replaceChildren(el("p", "muted", "No email sent yet.")); },
    onEvent(ev) {
      if (ev.kind !== "email") return;
      if (list.querySelector("p.muted")) list.replaceChildren();
      const to = [].concat(ev.to || []);
      const evil = to.some((a) => String(a).toLowerCase().endsWith("evil.example"));
      let body = String(ev.body || "");
      if (ev.attachment) body += `\n\n[attachment] ${ev.attachment}`;
      list.appendChild(el("div", evil ? "mail evil" : "mail", null, [
        el("div", "to", `To: ${to.join(", ")}`),
        el("div", "subj", `Subject: ${ev.subject || ""}`),
        el("pre", null, body),
      ]));
    },
  };
}

function goalsPanel(goals) {
  const rows = {};
  const list = el("div");
  for (const g of goals) {
    const badge = el("span", "badge pending", "PENDING");
    const lesson = el("div", "lesson");
    rows[g.id] = { badge, lesson };
    list.appendChild(el("div", "goal", null, [badge, el("div", null, null, [el("div", null, g.text), lesson])]));
  }
  const reached = el("p", "muted", "Models your text reached: run to find out.");
  const root = panel("Goals", [list, reached]);
  return {
    root,
    reset() {
      for (const r of Object.values(rows)) { r.badge.className = "badge pending"; r.badge.textContent = "PENDING"; r.lesson.textContent = ""; }
      reached.textContent = "Models your text reached: run to find out.";
    },
    onEvent(ev) {
      if (ev.kind !== "scoreboard") return;
      for (const g of ev.goals || []) {
        const r = rows[g.id];
        if (!r) continue;
        r.badge.className = g.won ? "badge pwned" : "badge held";
        r.badge.textContent = g.won ? "PWNED" : "HELD";
        r.lesson.textContent = g.lesson || "";
      }
      reached.textContent = `Models your text reached: ${(ev.reached || []).join(", ") || "none"}`;
    },
  };
}

function modelsPanel(defaults) {
  const env = (CAT && CAT.models) || {};
  const hint = (k) => (env.mock ? "offline mock model" : `.env: ${env[k] || "(not set)"}`);
  const big = textInput(defaults ? defaults[0] : "", hint("LLM_MODEL"));
  const small = textInput(defaults ? defaults[1] : "", hint("QLLM_MODEL"));
  const root = panel("Models for this run", [
    field("Privileged model (LLM_MODEL)", big),
    field("Quarantined model (QLLM_MODEL)", small),
    el("p", "muted", "Empty = use .env. Used on the next run."),
  ]);
  return { root, get: () => ({ LLM_MODEL: big.value.trim(), QLLM_MODEL: small.value.trim() }) };
}

// Run / Stop button plus a status line.
function runBar(onRun, label) {
  const run = btn(label || "Run", onRun);
  const stop = btn("Stop", stopJob, "ghost");
  const status = el("span", "status", "");
  stop.hidden = true;
  return {
    root: el("div", "row", null, [run, stop, status]),
    running() { run.disabled = true; stop.hidden = false; status.textContent = "Running..."; },
    finished() { run.disabled = false; stop.hidden = true; status.textContent = "Run finished"; },
  };
}

// ------------------------------------------------------------------ input cards
// An input card stays usable only while the script waits. Any later event closes it.
function inputHandler(append) {
  let waitingTurn = null; // a model_turn card waiting for its input event
  let open = null;        // the card the script is waiting on now
  return {
    reset() { waitingTurn = open = null; },
    // Returns true when the event was an input event it handled.
    onEvent(ev) {
      if (ev.kind !== "input" && open) { open.close(); open = null; }
      if (ev.kind === "model_turn") {
        waitingTurn = turnCard(ev);
        append(waitingTurn.root);
        return true;
      }
      if (ev.kind === "input") {
        if (open) open.close();
        if (waitingTurn) { open = waitingTurn; waitingTurn = null; }
        else { open = askCard(ev.prompt); append(open.root); }
        open.enable();
        return true;
      }
      return false;
    },
  };
}

function turnCard(ev) {
  const msgs = ev.messages || [];
  const shown = msgs.length > 1 ? [msgs[0], msgs[msgs.length - 1]] : msgs;
  const box = textArea("", 3);
  const sent = el("div", "muted");
  const send = btn("Send", () => finish(box.value));
  const honest = btn("Use honest reply", () => finish(ev.honest), "ghost");
  const full = el("div", "io");
  for (const m of msgs) { full.appendChild(el("div", "role", m.role)); full.appendChild(el("pre", null, m.content)); }
  const root = el("div", "turn", null, [
    el("h3", null, `You are the model: ${ev.role} LLM, purpose "${ev.purpose}"`),
    el("p", "muted", "Your text is in this prompt, so the injection worked. You write the reply."),
    ...shown.flatMap((m) => [el("div", "role", m === msgs[0] ? `${m.role} prompt` : `last ${m.role} message`), el("pre", null, m.content)]),
    el("details", null, null, [el("summary", null, `Full prompt (${msgs.length} messages)`), full]),
    el("div", "honest", null, [el("b", null, "Honest reply: "), el("span", null, ev.honest)]),
    box, el("div", "row", null, [send, honest]), sent,
  ]);
  let live = false;
  function set(on) { live = on; box.disabled = send.disabled = honest.disabled = !on; }
  function finish(text) {
    if (!live) return;
    set(false);
    sent.textContent = `You replied: ${text === ev.honest ? "(the honest reply)" : text}`;
    reply(text);
  }
  onEnter(box, () => finish(box.value));
  set(false);
  return { root, enable() { set(true); box.focus(); }, close() { set(false); } };
}

function askCard(prompt) {
  const text = String(prompt || "").trim() || "The script asks for input:";
  const sent = el("div", "muted");
  const controls = [];
  let live = false;
  function finish(value) {
    if (!live) return;
    live = false;
    controls.forEach((c) => { c.disabled = true; });
    sent.textContent = `You answered: ${value || "(empty)"}`;
    reply(value);
  }
  let row;
  if (text.includes("[y/N]")) {
    controls.push(btn("Yes", () => finish("y")), btn("No", () => finish("n"), "ghost"));
    row = el("div", "row", null, controls);
  } else {
    const box = textArea("", 2);
    controls.push(box, btn("Send", () => finish(box.value)));
    onEnter(box, () => finish(box.value));
    row = el("div", null, null, controls);
  }
  controls.forEach((c) => { c.disabled = true; });
  return {
    root: el("div", "ask", null, [el("pre", null, text), row, sent]),
    enable() { live = true; controls.forEach((c) => { c.disabled = false; }); controls[0].focus(); },
    close() { live = false; controls.forEach((c) => { c.disabled = true; }); },
  };
}

// ------------------------------------------------------------------ timeline
function evBlock(cls, tagCls, tagText, title, body) {
  const head = el("div", "h", null, [tagCls ? el("span", `tag ${tagCls}`, tagText) : null, el("span", null, title)]);
  return el("div", `ev ${cls}`, null, [head, body !== undefined && body !== null && body !== "" ? el("pre", null, body) : null]);
}

function timeline() {
  const box = el("div", "timeline");
  const inputs = inputHandler(add);
  let consoleBlock = null;
  function add(node) {
    const stick = nearBottom(box);
    box.appendChild(node);
    if (node !== consoleBlock) consoleBlock = null;
    if (stick) box.scrollTop = box.scrollHeight;
  }
  function render(ev) {
    switch (ev.kind) {
      case "header": return evBlock("step", null, null, ev.title);
      case "section": return evBlock("step", null, null, ev.title);
      case "step": return evBlock("step", null, null, `» ${ev.text}`);
      case "trusted": return evBlock("trusted", "trusted", "trusted", ev.label, ev.text);
      case "untrusted": return evBlock("untrusted", "untrusted", "untrusted", ev.label, ev.text);
      case "tool": {
        const args = ev.args && Object.keys(ev.args).length ? JSON.stringify(ev.args, null, 2) : "";
        return evBlock("tool", "tool", "tool", ev.name, args);
      }
      case "email": {
        let body = `Subject: ${ev.subject || ""}\n\n${ev.body || ""}`;
        if (ev.attachment) body += `\n\n[attachment] ${ev.attachment}`;
        return evBlock("email", "tool", "email", `sent to ${[].concat(ev.to || []).join(", ")}`, body);
      }
      case "llm": return evBlock("llm", "llm", "model", `${ev.purpose}  (${ev.role}, ${ev.model})`);
      case "render": {
        const links = (ev.links || []).map((l) => `${l[0]}: ${l[1]}`).join("\n");
        return evBlock(ev.links && ev.links.length && !ev.enforced ? "danger" : "", null, null,
          "assistant → user", ev.text + (links ? `\n\nlinks to other domains:\n${links}` : ""));
      }
      case "blocked": return evBlock("blocked", "trusted", "blocked", ev.text);
      case "danger": return evBlock("danger", "untrusted", "compromised", ev.text);
      case "ok": return el("div", "ev ok", `✓ ${ev.text}`);
      case "info": return el("div", "ev note", ev.text);
      case "error": return evBlock("error", "untrusted", "error", ev.text);
      case "done": return el("div", "ev note", "Run finished.");
      case "llm_io": case "scoreboard": case "keeper_turn": case "guess": return null; // shown in the side panels
      default: return el("div", "ev note", JSON.stringify(ev));
    }
  }
  return {
    root: box,
    reset() { box.replaceChildren(); consoleBlock = null; inputs.reset(); },
    onEvent(ev) {
      if (inputs.onEvent(ev)) return;
      if (ev.kind === "console") { // consecutive lines become one block (e.g. the CaMeL data-flow graph)
        if (consoleBlock) { consoleBlock.textContent += `\n${ev.text}`; if (nearBottom(box)) box.scrollTop = box.scrollHeight; }
        else { consoleBlock = el("pre", "console", ev.text); add(consoleBlock); }
        return;
      }
      const node = render(ev);
      if (node) add(node);
    },
  };
}

// ------------------------------------------------------------------ views
// Each view: {crumb, render(resume), onStart(), onEvent(ev)}.
function startView() {
  return {
    crumb: "Start",
    render() {
      const page = WELCOME.cloneNode(true);
      const m = CAT.models;
      const line = m.mock
        ? "Models: the offline mock (it obeys every injection). Set LLM_API_KEY in .env for real models."
        : `Models from .env: LLM_MODEL = ${m.LLM_MODEL || "(not set)"}, QLLM_MODEL = ${m.QLLM_MODEL || "(not set)"}`;
      page.appendChild(el("p", m.mock ? "banner miss" : "muted", line));
      MAIN.replaceChildren(page);
    },
    onStart() {}, onEvent() {},
  };
}

function keeperView(lv) {
  const prompts = promptsPanel("What the model saw");
  const models = modelsPanel(null);
  const chat = el("div", "chat");
  const banner = el("div");
  const box = textArea("", 2);
  box.placeholder = "Type as the customer.  /guess CODE   /prompt   /quit";
  const sendBtn = btn("Send", send);
  const meter = el("div", "meter safe", null, [el("span", null, "No prompts yet"), el("small", null, "Send a message to see the audit.")]);
  let waiting = false, lastBot = null, ask = null;

  function setComposer(on) { waiting = on; box.disabled = sendBtn.disabled = !on; if (on) box.focus(); }
  function send() {
    const text = box.value.trim();
    if (!waiting || !text) return;
    setComposer(false);
    box.value = "";
    reply(text);
  }
  function add(node) {
    const stick = nearBottom(chat);
    chat.appendChild(node);
    if (stick) chat.scrollTop = chat.scrollHeight;
  }
  function sys(text, cls) { add(el("div", cls ? `sys ${cls}` : "sys", text)); }
  function setMeter(n, total) {
    meter.className = n > 0 ? "meter leaky" : "meter safe";
    meter.replaceChildren(el("span", null, `Staff code inside ${n} of ${total} prompts`),
      el("small", null, n > 0 ? "Anything in a prompt can come out." : "There is nothing for the model to leak."));
  }
  function restart() { startJob({ kind: "keeper", level: lv.level, models: models.get() }, view); }
  onEnter(box, send);

  const view = {
    crumb: `Secret keeper · level ${lv.level}`,
    render(resume) {
      const chips = el("div", "chips");
      for (const [k, text] of Object.entries(lv.attacks)) {
        const chip = btn(k, () => { box.value = text; box.focus(); }, "chip");
        chip.title = text;
        chips.appendChild(chip);
      }
      MAIN.replaceChildren(el("div", "grid3", null, [
        el("div", null, null, [
          panel(`Level ${lv.level}`, [el("p", null, null, [el("b", null, lv.title)]), el("div", "doc", lv.doc.split("\n").slice(1).join("\n").trim())]),
          panel("Attacks to try", [el("p", "muted", "Click one to put it in the message box."), chips]),
          models.root,
          panel(null, [btn("Restart chat", restart)]),
        ]),
        el("div", null, null, [panel("Chat with the ticket desk", [chat, banner, el("div", "composer", null, [box, sendBtn])])]),
        el("div", null, null, [panel("Audit", [meter]), prompts.root]),
      ]));
      setComposer(false);
      if (!resume) restart();
    },
    onStart() {
      chat.replaceChildren(); banner.replaceChildren(); prompts.reset();
      setComposer(false); lastBot = null; ask = null;
      meter.className = "meter safe";
      meter.replaceChildren(el("span", null, "No prompts yet"), el("small", null, "Send a message to see the audit."));
    },
    onEvent(ev) {
      prompts.onEvent(ev);
      if (ask && ev.kind !== "input") { ask.close(); ask = null; }
      if (ev.kind !== "input") setComposer(false);
      const text = String(ev.text || "");
      switch (ev.kind) {
        case "input":
          if (String(ev.prompt).trim().endsWith("you>")) setComposer(true);
          else { ask = askCard(ev.prompt); add(ask.root); ask.enable(); }
          break;
        case "untrusted":
          if (String(ev.label).startsWith("customer")) add(el("div", "bubble you", ev.text));
          else add(evBlock("untrusted", "untrusted", "untrusted", ev.label, ev.text));
          break;
        case "trusted": add(evBlock("trusted", "trusted", "trusted", ev.label, ev.text)); break;
        case "render": lastBot = el("div", "bubble bot", ev.text); add(lastBot); break;
        case "danger":
          if (text.startsWith("correct:")) banner.replaceChildren(el("div", "banner win", text));
          else { if (lastBot && chat.lastChild === lastBot) lastBot.classList.add("leak"); sys(text, "bad"); }
          break;
        case "keeper_turn":
          setMeter(ev.in_prompts, ev.total);
          if (ev.leak && lastBot) lastBot.classList.add("leak");
          break;
        case "blocked": sys(text, "good"); break;
        case "ok": case "info": {
          const m = text.match(/inside (\d+) of (\d+) prompts/); // fallback if keeper_turn is missing
          if (text.startsWith("audit:")) { if (m) setMeter(+m[1], +m[2]); break; }
          sys(text, ev.kind === "ok" ? "good" : "");
          break;
        }
        case "console": if (text.trim()) sys(text); break;
        case "error": sys(`error: ${text}`, "bad"); break;
        case "done": sys("Chat ended. Press Restart chat for a new one (new code)."); break;
        default: break; // header, llm, llm_io, guess
      }
    },
  };
  return view;
}

function patternView(lab) {
  const tl = timeline();
  const prompts = promptsPanel();
  const emails = emailsPanel();
  const goals = goalsPanel(lab.goals);
  const models = modelsPanel(lab.models);
  const tabBody = el("div");
  const tabsRow = el("div", "tabs");
  let bar = null, tab = "watch";

  const tabs = {
    watch() {
      const clean = checkbox("--clean  (remove the planted injections)");
      const parts = [el("p", "muted", "Watch the agent run on its own, on the model set in .env or below.")];
      let variant = null, normal = null, naive = null;
      if (lab.lab === "05") {
        const sel = el("select", null, null, [el("option", null, "v2: CaMeL provenance"), el("option", null, "v1: plain code-then-execute")]);
        sel.options[0].value = "v2"; sel.options[1].value = "v1";
        normal = checkbox("--normal  (NORMAL mode: no control-flow dependencies)");
        sel.addEventListener("change", () => { normal.box.disabled = sel.value === "v1"; });
        variant = sel;
        parts.push(field("Version", sel), clean.root, normal.root);
      } else {
        naive = checkbox("--naive  (the unprotected agent on the same data)");
        parts.push(clean.root, naive.root);
      }
      bar = runBar(() => {
        const flags = [];
        if (clean.box.checked) flags.push("--clean");
        if (naive && naive.box.checked) flags.push("--naive");
        if (normal && normal.box.checked && variant.value === "v2") flags.push("--normal");
        const req = { kind: "watch", lab: lab.lab, flags, models: models.get() };
        if (variant) req.variant = variant.value;
        startJob(req, view);
      });
      return [...parts, bar.root];
    },
    model() {
      const target = el("select", null, null, lab.targets.map((t) => { const o = el("option", null, t); o.value = t; return o; }));
      const data = textArea(lab.default_text, 6);
      const hints = el("ol", null, null, lab.hints.map((h) => el("li", null, h)));
      bar = runBar(() => startJob({ kind: "lab", lab: lab.lab, target: target.value, data: data.value, models: models.get() }, view));
      return [
        el("p", "muted", `You plant text in: ${lab.slot}. When a model reads it, you play that model.`),
        field("Target", target),
        field("Your planted text (empty = the built-in text)", data),
        el("details", null, null, [el("summary", null, "Hints"), hints]),
        bar.root,
      ];
    },
    patch() {
      bar = null;
      const mine = CAT.patches.filter((p) => p.module === lab.lab);
      if (!mine.length) return [el("p", "muted", "No patch for this module.")];
      return mine.flatMap((p) => {
        const sw = checkbox(p.applied ? "applied" : "not applied", p.applied);
        const status = el("span", "status");
        sw.root.className = "switch";
        sw.box.addEventListener("change", async () => {
          sw.box.disabled = true;
          try {
            const res = await api("/api/patch", { name: p.name, on: sw.box.checked });
            CAT.patches = res.patches;
            if (!res.ok) status.textContent = "Could not change the patch (the file may have been edited).";
            showTab("patch");
            if (!res.ok) tabBody.appendChild(el("p", "banner miss", status.textContent));
          } catch (e) {
            sw.box.disabled = false; sw.box.checked = !sw.box.checked;
            status.textContent = `error: ${e.message}`;
          }
        });
        const diff = el("pre", "diff");
        for (const line of p.diff.split("\n")) {
          const cls = line.startsWith("+") && !line.startsWith("+++") ? "add" : line.startsWith("-") && !line.startsWith("---") ? "del" : null;
          diff.appendChild(el("span", cls, `${line}\n`));
        }
        return [
          el("p", null, null, [el("b", null, p.name)]),
          el("div", "row", null, [sw.root, status]),
          el("p", "muted", "After switching, rerun Be the model with the same text and compare the scoreboard."),
          diff,
        ];
      });
    },
  };
  const names = { watch: "Watch", model: "Be the model", patch: "Patch" };

  function showTab(name) {
    tab = name;
    tabsRow.replaceChildren(...Object.keys(names).map((k) => btn(names[k], () => showTab(k), k === tab ? "small" : "small ghost")));
    tabBody.replaceChildren(...tabs[name]());
    if (bar && JOB && JOB.view === view && !JOB.done) bar.running();
  }

  const short = lab.title.split(":")[0];
  const view = {
    crumb: `Pattern ${lab.lab} · ${short}`,
    render() {
      MAIN.replaceChildren(el("div", "grid3", null, [
        el("div", null, null, [
          panel(lab.title, [el("p", null, lab.story)]),
          goals.root,
          panel("How it is defended", [el("p", null, lab.defend)]),
          models.root,
        ]),
        el("div", null, null, [panel(null, [tabsRow, tabBody]), panel("Timeline", [tl.root])]),
        el("div", null, null, [prompts.root, emails.root]),
      ]));
      showTab(tab);
    },
    onStart() { tl.reset(); prompts.reset(); emails.reset(); goals.reset(); if (bar) bar.running(); },
    onEvent(ev) {
      tl.onEvent(ev); prompts.onEvent(ev); emails.onEvent(ev); goals.onEvent(ev);
      if (ev.kind === "done" && bar) bar.finished();
    },
  };
  return view;
}

function playgroundView() {
  const tl = timeline();
  const prompts = promptsPanel();
  const emails = emailsPanel();
  const models = modelsPanel(null);
  const code = textArea(CAT.missions.length ? CAT.missions[0].code : "", 14);
  code.spellcheck = false;
  code.wrap = "off";
  const normal = checkbox("NORMAL mode (no control-flow dependencies)");
  const bar = runBar(() => startJob({ kind: "playground", code: code.value, normal: normal.box.checked, models: models.get() }, view));
  const view = {
    crumb: "CaMeL playground",
    render() {
      const chips = el("div", "chips", null, CAT.missions.map((m) => {
        const chip = btn(m.id.replace("play-", ""), () => { code.value = m.code; }, "chip");
        chip.title = m.file;
        return chip;
      }));
      MAIN.replaceChildren(el("div", "grid3", null, [
        el("div", null, null, [
          panel("Your plan program", [
            el("p", "muted", "You are the P-LLM. Write restricted Python; the CaMeL interpreter and its policies decide what runs."),
            chips, field("Program", code), normal.root, bar.root,
          ]),
          models.root,
        ]),
        el("div", null, null, [panel("Timeline", [tl.root])]),
        el("div", null, null, [prompts.root, emails.root]),
      ]));
    },
    onStart() { tl.reset(); prompts.reset(); emails.reset(); bar.running(); },
    onEvent(ev) { tl.onEvent(ev); prompts.onEvent(ev); emails.onEvent(ev); if (ev.kind === "done") bar.finished(); },
  };
  return view;
}

function tracesView() {
  const out = el("pre", "doc", "Pick a trace on the left.");
  out.style.maxHeight = "75vh";
  const list = el("div", "tracelist");
  async function open(name) {
    out.textContent = "Loading...";
    try { out.textContent = (await api(`/api/trace?name=${encodeURIComponent(name)}`)).text; }
    catch (e) { out.textContent = `error: ${e.message}`; }
  }
  function fill() {
    list.replaceChildren(...(CAT.traces.length ? CAT.traces.map((t) => btn(`${t.name}  (${Math.max(1, Math.round(t.size / 1024))} KB)`, () => open(t.name), "ghost small"))
      : [el("p", "muted", "No traces yet. Chat with a Secret keeper level first.")]));
  }
  async function refresh() {
    try { CAT = await api("/api/catalog"); fill(); } catch (e) { out.textContent = `error: ${e.message}`; }
  }
  return {
    crumb: "Traces",
    render() {
      fill();
      MAIN.replaceChildren(el("div", "grid2", null, [
        panel("Secret keeper traces (newest first)", [btn("Refresh", refresh, "ghost small"), list]),
        panel("Trace", [out]),
      ]));
    },
    onStart() {}, onEvent() {},
  };
}

// ------------------------------------------------------------------ router and top bar
function routes() {
  const r = { "#start": startView, "#playground": playgroundView, "#traces": tracesView };
  for (const lv of CAT.keeper) r[`#keeper-${lv.level}`] = () => keeperView(lv);
  for (const lab of CAT.labs) r[`#lab-${lab.lab}`] = () => patternView(lab);
  return r;
}

function buildNav() {
  const nav = document.getElementById("nav");
  const link = (hash, title, small) => {
    const a = el("a", null, title, [small ? el("small", null, small) : null]);
    a.href = hash;
    return a;
  };
  const labs = PATTERN_ORDER.map((id) => CAT.labs.find((l) => l.lab === id)).filter(Boolean);
  nav.replaceChildren(
    el("h3", null, "Welcome"), link("#start", "Start"),
    el("h3", null, "Secret keeper"),
    ...CAT.keeper.map((lv) => link(`#keeper-${lv.level}`, `Level ${lv.level}`, lv.title)),
    el("h3", null, "Patterns"),
    ...labs.map((lab, i) => link(`#lab-${lab.lab}`, `Block ${i + 3} · ${lab.lab}`, lab.title.split(":")[0])),
    el("h3", null, "Tools"), link("#playground", "CaMeL playground"), link("#traces", "Traces"),
  );
}

function showModels() {
  const m = CAT.models;
  const pill = (k, v) => el("span", "pill", `${k} `, [el("b", null, v || "(not set)")]);
  const kids = m.mock ? [el("span", "pill warn", "mock model (offline)")] : [pill("LLM", m.LLM_MODEL), pill("QLLM", m.QLLM_MODEL)];
  document.getElementById("models").replaceChildren(...kids);
}

function route(resumeId) {
  const table = routes();
  if (!table[location.hash]) { history.replaceState(null, "", "#start"); }
  closeJob();
  VIEW = table[location.hash]();
  document.getElementById("crumb").textContent = VIEW.crumb;
  for (const a of document.querySelectorAll("nav a")) a.classList.toggle("active", a.getAttribute("href") === location.hash);
  VIEW.render(!!resumeId);
  if (resumeId) { VIEW.onStart(); attach(resumeId, VIEW); }
}

async function boot() {
  const proj = document.getElementById("projector");
  try { if (localStorage.getItem("lab-projector") === "1") document.body.classList.add("projector"); } catch (_) { /* no storage */ }
  proj.addEventListener("click", () => {
    const on = document.body.classList.toggle("projector");
    try { localStorage.setItem("lab-projector", on ? "1" : "0"); } catch (_) { /* no storage */ }
  });
  try {
    CAT = await api("/api/catalog");
  } catch (e) {
    MAIN.replaceChildren(el("section", "welcome", null, [el("h1", null, "Cannot load the lab"),
      el("p", null, `${e.message}. Open the exact link that python ui/server.py printed (the token changes on every start).`)]));
    return;
  }
  showModels();
  buildNav();
  const saved = load("lab-job"); // a run in progress before a reload
  route(saved && saved.route === location.hash ? saved.id : null);
  window.addEventListener("hashchange", () => route(null));
}

boot();
