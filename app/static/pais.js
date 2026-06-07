// VSA EduAI — Painel dos Pais (dados reais via API)
let senha = localStorage.getItem('eduai_pai_senha') || '';
let EST = null;
const $ = id => document.getElementById(id);
function esc(s){ return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function estrelasStr(n){ return '★'.repeat(n) + '☆'.repeat(3-n); }

async function api(path, opts){
  const sep = path.includes('?') ? '&' : '?';
  let r; try { r = await fetch(path + sep + 'senha=' + encodeURIComponent(senha), opts); }
  catch(e){ return { status:0, data:null }; }
  let d=null; try { d = await r.json(); } catch(e){}
  return { status:r.status, data:d };
}

$('senha-inp').addEventListener('keydown', e => { if (e.key==='Enter') entrar(); });

async function entrar(){
  senha = $('senha-inp').value.trim();
  const r = await api('/api/pais/estado');
  if (r.status !== 200){ $('login-msg').textContent='Senha inválida 😕'; return; }
  localStorage.setItem('eduai_pai_senha', senha);
  EST = r.data; $('login').classList.add('hidden'); $('app').classList.remove('hidden'); render();
}
async function recarregar(){ const r = await api('/api/pais/estado'); if (r.status===200){ EST=r.data; render(); } }

function fmtData(ts){ return (ts||'').slice(0,16).replace('T',' '); }

function render(){
  const a = EST.aluno, cat = EST.catalogo || {};
  const per = a.xp_prox_nivel / a.nivel;
  const dentro = a.xp - (a.nivel-1)*per;
  const pct = Math.max(0.03, Math.min(1, dentro/per));
  const faltam = Math.max(0, Math.round(per - dentro));
  const leituras = (EST.progresso||[]).filter(p=>p.leitura_ok).length;
  const R=30, C=2*Math.PI*R;

  let h = '';
  // Hero
  h += `<div class="card hero">
    <div class="avc">
      <svg width="74" height="74" viewBox="0 0 74 74">
        <circle cx="37" cy="37" r="${R}" fill="none" stroke="#2a2740" stroke-width="5"/>
        <circle cx="37" cy="37" r="${R}" fill="none" stroke="url(#g)" stroke-width="5" stroke-linecap="round"
          stroke-dasharray="${C.toFixed(1)}" stroke-dashoffset="${(C*(1-pct)).toFixed(1)}"/>
        <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#a78bfa"/><stop offset="1" stop-color="#7c3aed"/></linearGradient></defs>
      </svg>
      <div class="face">${a.avatar||'🧑‍🚀'}</div><div class="lv">Nv ${a.nivel}</div>
    </div>
    <div class="who">
      <div class="nm">${esc(a.nome)}</div>
      <div class="role">Fundamental • estudante</div>
      <div class="xpline"><span>Progresso de nível</span><span>faltam <b>${faltam} XP</b> para o Nv ${a.nivel+1}</span></div>
      <div class="xpbar"><i style="width:${(pct*100).toFixed(0)}%"></i></div>
    </div>
  </div>`;

  // Stats
  h += `<div class="stats">
    <div class="stat fire"><div class="v">🔥 ${a.streak}</div><div class="k">dias seguidos</div></div>
    <div class="stat coin"><div class="v">🪙 ${a.moedas}</div><div class="k">moedas</div></div>
    <div class="stat xp"><div class="v">⭐ ${a.xp}</div><div class="k">XP total</div></div>
    <div class="stat med"><div class="v">📖 ${leituras}</div><div class="k">leituras</div></div>
  </div>`;

  // Pedidos de recompensa
  const rec = (EST.compras||[]).filter(c=>c.tipo==='recompensa');
  const pend = rec.filter(r=>r.status==='pendente').length;
  h += `<div class="sec">🎁 Pedidos de recompensa ${pend?`<span class="count">${pend} pendente${pend>1?'s':''}</span>`:''}</div>`;
  if (!rec.length) h += `<div class="card" style="color:var(--dim);font-weight:600">Nenhum pedido ainda.</div>`;
  rec.forEach(r=>{
    h += `<div class="card req"><div class="ic">⛏️</div>
      <div class="info"><div class="t">${esc(r.nome)}</div><div class="s">${fmtData(r.ts)}</div></div>
      ${r.status==='pendente'?`<button class="aprovar" onclick="aprovar(${r.id})">Aprovar ✓</button>`:`<span class="done">✓ Aprovado</span>`}</div>`;
  });

  // Progresso por matéria
  h += `<div class="sec">📚 Progresso por matéria</div>`;
  Object.keys(cat).forEach(mid=>{
    const c = cat[mid];
    const conc = (EST.progresso||[]).filter(p=>p.materia===mid && p.concluida).length;
    const estrelas = (EST.progresso||[]).filter(p=>p.materia===mid).reduce((s,p)=>s+(p.melhor_estrela||0),0);
    const tot = c.total_missoes||0, pc = tot?Math.round(conc/tot*100):0;
    h += `<div class="card mat" style="--mc:${c.cor}"><div class="ic">${c.icone}</div>
      <div class="body"><div class="row1"><div class="nm">${esc(c.nome)}</div><div class="stars">${estrelas} ⭐</div></div>
      <div class="pb"><i style="width:${pc}%"></i></div>
      <div class="meta"><span>${conc}/${tot} missões</span>${conc===tot&&tot?'<span class="ok">✓ Completo</span>':`<span>${pc}%</span>`}</div></div></div>`;
  });

  // Medalhas
  const catm = EST.medalhas_catalogo||[]; const got = catm.filter(m=>m.tem).length;
  h += `<div class="sec">🏅 Medalhas <span class="count">${got}/${catm.length}</span></div><div class="card"><div class="medwrap">`;
  catm.forEach(m=>{ h += `<div class="med ${m.tem?'got':'lock'}"><div class="e">${m.emoji}</div><div class="n">${esc(m.nome)}</div></div>`; });
  h += `</div></div>`;

  // Últimas atividades
  h += `<div class="sec">🕑 Últimas atividades</div><div class="card acts">`;
  const ult = EST.ultimas||[];
  if (!ult.length) h += `<div style="color:var(--dim);font-weight:600;padding:6px">Sem atividades ainda.</div>`;
  ult.slice(0,12).forEach(t=>{
    const c = cat[t.materia]||{}; const titulo=(c.missoes&&c.missoes[t.missao])||t.missao;
    const leu = (EST.progresso||[]).some(p=>p.materia===t.materia&&p.missao===t.missao&&p.leitura_ok);
    h += `<div class="act"><div class="ai">${c.icone||'📘'}</div>
      <div class="ab"><div class="at">${esc(titulo)}</div>
      <div class="ad"><span>${fmtData(t.ts)}</span>${leu?'<span class="read">• 📖 leu</span>':''}</div></div>
      <div class="ar"><div class="sc">${t.acertos}/${t.total} acertos</div><div class="st">${estrelasStr(t.estrelas)}</div></div></div>`;
  });
  h += `</div>`;

  $('view').innerHTML = h;
}

async function aprovar(id){
  await api('/api/pais/aprovar', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id}) });
  await recarregar();
  showToast('✓ Recompensa liberada!');
}
function showToast(msg){ const t=$('toast'); t.textContent=msg; t.classList.add('show'); clearTimeout(window.__tt); window.__tt=setTimeout(()=>t.classList.remove('show'),2600); }

window.addEventListener('load', async ()=>{
  if (!senha) return;
  const r = await api('/api/pais/estado');
  if (r.status===200){ EST=r.data; $('login').classList.add('hidden'); $('app').classList.remove('hidden'); render(); }
});
