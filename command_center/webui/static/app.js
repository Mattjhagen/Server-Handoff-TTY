const labels={intake:'Intake','pm-scope':'PM Scope',build:'Build',security:'Security',human:'Human',merged:'Merged',released:'Released'},stageNode={'pm-scope':'t310-pm',build:'r510-dev',security:'r410-sec','security-review':'r410-sec'},stages=['intake','pm-scope','build','security','human','merged','released'];let state=null,selected='ALL',autoFollow=true,lastStatusSignature='',lastHeartbeat=Date.now(),rotationIndex=0;
const $=id=>document.getElementById(id),text=(el,v)=>{el.textContent=v==null?'':String(v)};
const age=e=>{if(!e)return'never';const s=Math.max(0,Date.now()/1000-e);return s<60?`${Math.floor(s)}s ago`:s<3600?`${Math.floor(s/60)}m ago`:`${Math.floor(s/3600)}h ago`};
const duration=s=>{s=Math.max(0,Number(s)||0);const d=Math.floor(s/86400),h=Math.floor(s%86400/3600);return d?`${d}d ${h}h`:`${h}h`};
const central=d=>new Intl.DateTimeFormat('en-US',{timeZone:'America/Chicago',hour:'numeric',minute:'2-digit',second:'2-digit',timeZoneName:'short'}).format(d);

function renderWorkflow(w){const r=$('workflow');r.replaceChildren();const c=stages.indexOf(w.current_stage);stages.forEach((s,i)=>{const d=document.createElement('div');d.className=`stage ${i<c?'done':''} ${i===c?'active':''}`;text(d,labels[s]);r.append(d)})}

function card(n){
  const c=$('nodeTemplate').content.firstElementChild.cloneNode(true);
  text(c.querySelector('.node-role'),n.role);
  text(c.querySelector('.node-name'),n.host_alias);
  const st=c.querySelector('.node-status');
  st.classList.add(n.status);
  text(st,n.status);
  
  const isRunning = !['', 'idle', 'unknown'].includes((n.opencode_state || '').toLowerCase()) ||
                    (state?.workflow?.state === 'working' && stageNode[state?.workflow?.current_stage] === n.node_id);
  if (isRunning) {
    c.classList.add('running', 'active-runner');
  }

  const isAffectedServer = (stageNode[state?.workflow?.current_stage] === n.node_id) || (n.opencode_state === 'review');
  const serverNeedsReview = isAffectedServer && (state?.workflow?.state === 'awaiting-human' || state?.workflow?.current_stage === 'security-review' || state?.workflow?.current_stage === 'human');
  
  if (serverNeedsReview) {
    c.classList.add('needs-manual-review');
  }
  
  text(c.querySelector('.node-summary'),n.status_summary||n.offline_reason||'No current summary');
  const t=n.telemetry||{},rp=t.ram_total_mb?100*t.ram_used_mb/t.ram_total_mb:0;
  text(c.querySelector('.cpu'),`${t.cpu_percent||0}%`);
  c.querySelector('.cpu-bar').style.width=`${Math.min(100,t.cpu_percent||0)}%`;
  text(c.querySelector('.ram'),`${Math.round(rp)}%`);
  c.querySelector('.ram-bar').style.width=`${Math.min(100,rp)}%`;
  text(c.querySelector('.load'),t.load_1||0);
  text(c.querySelector('.uptime'),duration(t.uptime_s));
  text(c.querySelector('.issue'),n.current_issue||'No active issue');
  const a=(n.todos?.items||[]).find(x=>x.status==='active');
  text(c.querySelector('.activity'),a?.activity||n.opencode_state||'idle');
  const p=c.querySelector('.processes');
  (n.processes||[]).slice(0,5).forEach(x=>{const q=document.createElement('span');text(q,`${x.pid} ${x.name}`);p.append(q)});
  c.addEventListener('click',()=>choose(n.node_id,false));
  return c;
}

function renderNodes(ns){const r=$('nodes');r.replaceChildren();ns.slice(0,3).forEach(n=>r.append(card(n)))}
function choose(id,follow){selected=id;autoFollow=follow;$('followActive').classList.toggle('active',follow);renderTabs();renderTodos()}

function renderTabs(){
  if(!state)return;
  const r=$('serverTabs');
  r.replaceChildren();

  // Unified All-Servers Tab
  const allBtn = document.createElement('button');
  allBtn.type = 'button';
  allBtn.className = `server-tab ${selected==='ALL'?'active':''}`;
  allBtn.setAttribute('role','tab');
  text(allBtn, '⚡ ALL SERVERS (UNIFIED LOGS)');
  allBtn.onclick = () => choose('ALL', false);
  r.append(allBtn);

  state.nodes.slice(0,3).forEach(n=>{
    const isRunning = !['', 'idle', 'unknown'].includes((n.opencode_state || '').toLowerCase());
    const isAffectedServer = (stageNode[state?.workflow?.current_stage] === n.node_id) || (n.opencode_state === 'review');
    const serverNeedsReview = isAffectedServer && (state?.workflow?.state === 'awaiting-human' || state?.workflow?.current_stage === 'security-review' || state?.workflow?.current_stage === 'human');
    
    const b=document.createElement('button');
    b.type='button';
    b.className=`server-tab ${n.node_id===selected?'active':''} ${isRunning?'running':''} ${serverNeedsReview?'needs-manual-review':''}`;
    b.setAttribute('role','tab');
    b.setAttribute('aria-selected',String(n.node_id===selected));
    text(b,`${serverNeedsReview ? '🚨 ' : isRunning ? '⚡ ' : ''}${n.host_alias} · ${n.role}`);
    b.onclick=()=>choose(n.node_id,false);
    r.append(b);
  });
}

function renderTodos(){
  if(!state)return;
  
  const r=$('todos');
  r.replaceChildren();

  if (selected === 'ALL') {
    // --- Unified Live Execution Logs across all 3 nodes ---
    text($('todoMeta'), `Unified Multi-Server Stream · T310, R510, R410 · live sync`);

    const logBox = document.createElement('li');
    logBox.className = 'todo active live-log-box';
    logBox.style.cssText = "display:flex;flex-direction:column;gap:8px;padding:12px;background:rgba(8,13,24,0.85);border:1px solid rgba(139,92,246,0.35);border-radius:12px;margin-bottom:12px;box-shadow:inset 0 1px 1px rgba(255,255,255,0.05);";

    const headDiv = document.createElement('div');
    headDiv.style.cssText = "display:flex;justify-content:space-between;align-items:center;";

    const titleSpan = document.createElement('strong');
    titleSpan.style.cssText = "font-size:12px;color:#22d3ee;letter-spacing:0.05em;display:flex;align-items:center;gap:6px;";
    titleSpan.textContent = `⚡ UNIFIED LIVE PIPELINE LOGS (T310 / R510 / R410)`;

    const statusBadge = document.createElement('span');
    statusBadge.style.cssText = "background:linear-gradient(135deg,#7c3aed,#06b6d4);color:#fff;font-size:9px;font-weight:800;letter-spacing:0.1em;padding:3px 9px;border-radius:999px;";
    statusBadge.textContent = '● UNIFIED CLUSTER STREAM';

    const copyBtn = document.createElement('button');
    copyBtn.style.cssText = "background:rgba(255,255,255,0.08);color:#a7f3d0;border:1px solid rgba(52,211,153,0.3);font-size:10px;font-weight:700;padding:3px 10px;border-radius:6px;cursor:pointer;transition:all 0.2s ease;display:flex;align-items:center;gap:4px;";
    copyBtn.innerHTML = "📋 Copy All Logs";
    copyBtn.onclick = () => {
      const textToCopy = unifiedLines.length ? unifiedLines.join('\n') : '> Pipeline active across T310, R510, R410.';
      navigator.clipboard.writeText(textToCopy).then(() => {
        copyBtn.innerHTML = "✅ Copied!";
        copyBtn.style.background = "rgba(16,185,129,0.3)";
        setTimeout(() => {
          copyBtn.innerHTML = "📋 Copy All Logs";
          copyBtn.style.background = "rgba(255,255,255,0.08)";
        }, 2000);
      }).catch(err => {
        console.error("Clipboard write failed:", err);
      });
    };

    const actionGroup = document.createElement('div');
    actionGroup.style.cssText = "display:flex;align-items:center;gap:8px;";
    actionGroup.append(copyBtn, statusBadge);

    headDiv.append(titleSpan, actionGroup);
    logBox.append(headDiv);

    // Merge logs from all nodes with server tags
    let unifiedLines = [];
    (state.nodes || []).forEach(n => {
      const lines = (n.agent_report_lines || []).filter(l => l && l.trim());
      lines.forEach(l => {
        unifiedLines.push(`[${n.host_alias} ${n.role.split(' ')[0]}] ${l}`);
      });
    });

    // Newest logs at top, oldest at bottom
    unifiedLines.reverse();

    const logContainer = document.createElement('div');
    logContainer.style.cssText = "font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:11px;line-height:1.55;color:#cbd5e1;background:#050811;padding:10px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.08);max-height:220px;overflow-y:auto;white-space:pre-wrap;";
    logContainer.textContent = unifiedLines.length ? unifiedLines.join('\n') : '> Pipeline active across T310, R510, R410.';

    logBox.append(logContainer);
    r.append(logBox);
    return;
  }

  // Single Focused Server View
  const n=state.nodes.find(x=>x.node_id===selected)||state.nodes[0];
  if(!n)return;

  const isRunning = !['', 'idle', 'unknown'].includes((n.opencode_state || '').toLowerCase());
  const fresh=state.demo_mode?'synthetic snapshot':`updated ${age(n.last_update_epoch_s || n.todos?.updated_at_epoch_s)}`;
  text($('todoMeta'),`${n.host_alias} · ${n.role} · ${fresh}`);

  const isAffectedServer = (stageNode[state?.workflow?.current_stage] === n.node_id) || (n.opencode_state === 'review');
  const serverNeedsReview = isAffectedServer && (state?.workflow?.state === 'awaiting-human' || state?.workflow?.current_stage === 'security-review' || state?.workflow?.current_stage === 'human');

  const logBox = document.createElement('li');
  logBox.className = `todo active live-log-box ${isRunning ? 'running' : ''} ${serverNeedsReview ? 'needs-manual-review' : ''}`;
  logBox.style.cssText = serverNeedsReview
    ? "display:flex;flex-direction:column;gap:8px;padding:12px;background:rgba(24,8,8,0.9);border:2px solid #ef4444;border-radius:12px;margin-bottom:12px;box-shadow:0 0 20px rgba(239,68,68,0.4);"
    : "display:flex;flex-direction:column;gap:8px;padding:12px;background:rgba(8,13,24,0.85);border:1px solid rgba(139,92,246,0.35);border-radius:12px;margin-bottom:12px;box-shadow:inset 0 1px 1px rgba(255,255,255,0.05);";

  const headDiv = document.createElement('div');
  headDiv.style.cssText = "display:flex;justify-content:space-between;align-items:center;";
  
  const titleSpan = document.createElement('strong');
  titleSpan.style.cssText = serverNeedsReview ? "font-size:12px;color:#f87171;letter-spacing:0.05em;display:flex;align-items:center;gap:6px;" : "font-size:12px;color:#22d3ee;letter-spacing:0.05em;display:flex;align-items:center;gap:6px;";
  titleSpan.textContent = serverNeedsReview ? `🚨 MANUAL REVIEW NEEDED — ${n.host_alias} (${n.role})` : `⚡ LIVE EXECUTION LOGS — ${n.host_alias} (${n.role})`;

  const statusBadge = document.createElement('span');
  statusBadge.style.cssText = serverNeedsReview
    ? "background:#ef4444;color:#fff;font-size:9px;font-weight:900;letter-spacing:0.1em;padding:3px 9px;border-radius:999px;box-shadow:0 0 12px rgba(239,68,68,0.8);"
    : isRunning 
    ? "background:linear-gradient(135deg,#7c3aed,#06b6d4);color:#fff;font-size:9px;font-weight:800;letter-spacing:0.1em;padding:3px 9px;border-radius:999px;box-shadow:0 0 10px rgba(34,211,238,0.5);"
    : "color:#8d9bb4;font-size:9px;border:1px solid rgba(141,155,180,0.3);padding:2px 8px;border-radius:999px;";
  statusBadge.textContent = serverNeedsReview ? '🚨 AWAITING HUMAN' : isRunning ? '● RUNNING AGENT' : `IDLE (${n.opencode_state || 'idle'})`;

  const nodeCopyBtn = document.createElement('button');
  nodeCopyBtn.style.cssText = "background:rgba(255,255,255,0.08);color:#a7f3d0;border:1px solid rgba(52,211,153,0.3);font-size:10px;font-weight:700;padding:3px 10px;border-radius:6px;cursor:pointer;transition:all 0.2s ease;display:flex;align-items:center;gap:4px;";
  nodeCopyBtn.innerHTML = "📋 Copy Logs";
  nodeCopyBtn.onclick = () => {
    const textToCopy = logLines.length ? logLines.join('\n') : (n.status_summary ? `> ${n.status_summary}` : `> Host ${n.host_alias} (${n.role}) is reachable.`);
    navigator.clipboard.writeText(textToCopy).then(() => {
      nodeCopyBtn.innerHTML = "✅ Copied!";
      nodeCopyBtn.style.background = "rgba(16,185,129,0.3)";
      setTimeout(() => {
        nodeCopyBtn.innerHTML = "📋 Copy Logs";
        nodeCopyBtn.style.background = "rgba(255,255,255,0.08)";
      }, 2000);
    });
  };

  const nodeActionGroup = document.createElement('div');
  nodeActionGroup.style.cssText = "display:flex;align-items:center;gap:8px;";
  nodeActionGroup.append(nodeCopyBtn, statusBadge);

  headDiv.append(titleSpan, nodeActionGroup);
  logBox.append(headDiv);

  const logLines = (n.agent_report_lines || []).filter(l => l && l.trim()).slice().reverse();
  const logContainer = document.createElement('div');
  logContainer.style.cssText = "font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:11px;line-height:1.55;color:#cbd5e1;background:#050811;padding:10px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.08);max-height:180px;overflow-y:auto;white-space:pre-wrap;";

  if (logLines.length) {
    logContainer.textContent = logLines.join('\n');
  } else if (n.status_summary) {
    logContainer.textContent = `> ${n.status_summary}`;
  } else {
    logContainer.textContent = `> Host ${n.host_alias} (${n.role}) is reachable and waiting for assigned queue tasks.`;
  }

  logBox.append(logContainer);
  r.append(logBox);

  const p=n.todos||{};
  if((p.items||[]).length){
    p.items.forEach(i=>{
      const li=document.createElement('li');
      li.className=`todo ${i.status}`;
      const g=document.createElement('span');
      g.className='todo-glyph';
      text(g,`[${i.glyph}]`);
      const box=document.createElement('div'),l=document.createElement('label');
      text(l,i.label);
      box.append(l);
      if(i.activity){
        const s=document.createElement('small');
        text(s,i.activity);
        box.append(s);
      }
      li.append(g,box);
      r.append(li);
    });
  }
}

function renderQueue(xs){text($('queueCount'),xs.length);const r=$('queue');r.replaceChildren();xs.slice(0,8).forEach(q=>{const row=document.createElement('div');row.className='queue-item';const box=document.createElement('div'),t=document.createElement('strong'),m=document.createElement('small'),s=document.createElement('span');s.className='queue-state';text(t,q.title);text(m,`${q.key} · ${labels[q.stage]||q.stage}${q.badge?' · '+q.badge:''}`);text(s,q.state);box.append(t,m);row.append(box,s);r.append(row)})}

function render(d){
  state=d;
  const ns=d.nodes||[];
  
  const reviewNodes = ns.filter(n => {
    const isAffected = (stageNode[d.workflow?.current_stage] === n.node_id) || (n.opencode_state === 'review');
    return isAffected && (d.workflow?.state === 'awaiting-human' || d.workflow?.current_stage === 'security-review' || d.workflow?.current_stage === 'human');
  });

  if (!selected) selected = 'ALL';

  const needsIntervention = reviewNodes.length > 0 || (d.queue || []).some(q => q.state === 'awaiting-human' || q.state === 'blocked' || q.stage === 'human');

  if (needsIntervention) {
    $('chatToggle').classList.add('blink-manual-intervention');
    $('chatUnread').hidden = false;
    $('chatUnread').classList.add('blink-manual-intervention');
  } else {
    $('chatToggle').classList.remove('blink-manual-intervention');
    $('chatUnread').classList.remove('blink-manual-intervention');
    if ($('chatPanel').hidden) $('chatUnread').hidden = true;
  }

  text($('sourceBadge'),d.demo_mode?'DEMO DATA':d.github_stale?'GITHUB STALE':'LIVE');
  $('sourceBadge').style.color=d.demo_mode?'var(--amber)':'var(--green)';
  text($('heroTitle'),d.workflow?.item_label||'No active delivery');
  text($('heroMeta'),`${labels[d.workflow?.current_stage]||'Intake'} · ${d.workflow?.state||'queued'}`);
  const off=ns.some(n=>n.status==='offline'),stale=ns.some(n=>n.status==='stale'),ok=!off&&!stale&&d.github_reachable;
  text($('healthLabel'),ok?'SYSTEM HEALTHY':off?'NODE OFFLINE':'ATTENTION');
  $('healthLabel').style.color=ok?'var(--green)':'var(--amber)';
  text($('freshness'),`updated ${age(d.generated_at_epoch_s)} · ${central(new Date(d.generated_at_epoch_s*1000))}`);
  renderWorkflow(d.workflow||{});
  renderNodes(ns);
  renderTabs();
  renderTodos();
  renderQueue(d.queue||[]);
  text($('schema'),d.schema||'');
}

$('followActive').onclick=()=>{
  autoFollow=true;
  selected='ALL';
  $('followActive').classList.add('active');
  renderTabs();
  renderTodos();
};

setInterval(()=>{text($('clock'),central(new Date()));if(state)text($('freshness'),`updated ${age(state.generated_at_epoch_s)} · ${central(new Date(state.generated_at_epoch_s*1000))}`)},1000);

function chatMessage(value,kind){const p=document.createElement('p');p.className=kind==='user'?'user-message':kind==='status'?'status-message':'assistant-message';text(p,value);$('chatMessages').append(p);while($('chatMessages').children.length>60)$('chatMessages').firstElementChild.remove();$('chatMessages').scrollTop=$('chatMessages').scrollHeight}
function applyUiAction(action){if(action==='refresh')fetchState();else if(action==='follow-active')$('followActive').click();else if(action.startsWith('focus:'))choose(action.slice(6),false)}

$('chatToggle').onclick=()=>{$('chatPanel').hidden=false;$('chatToggle').setAttribute('aria-expanded','true');$('chatUnread').hidden=true;$('chatInput').focus()};
$('chatClose').onclick=()=>{$('chatPanel').hidden=true;$('chatToggle').setAttribute('aria-expanded','false')};
$('chatForm').onsubmit=async e=>{e.preventDefault();const input=$('chatInput'),question=input.value.trim();if(!question)return;input.value='';chatMessage(question,'user');chatMessage('Thinking with the current live snapshot…','assistant');const pending=$('chatMessages').lastElementChild;try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question})});const reply=await r.json();text(pending,reply.answer||'No answer returned.');if(reply.ui_action)applyUiAction(reply.ui_action)}catch(err){text(pending,'Big Pickle chat is unavailable. Live monitoring is still running.')}};

async function fetchState(){try{const r=await fetch('/api/state',{cache:'no-store'});if(!r.ok)throw Error(r.status);render(await r.json())}catch(e){text($('sourceBadge'),'DISCONNECTED');$('sourceBadge').style.color='var(--red)'}}
fetchState();setInterval(fetchState,5000);
