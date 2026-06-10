// VSA EduAI — Painel dos Pais (dados reais via API)
let senha = localStorage.getItem('eduai_pai_senha') || '';
let EST = null;
const $ = id => document.getElementById(id);
function esc(s){ return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function estrelasStr(n){ return '★'.repeat(n) + '☆'.repeat(3-n); }
function avatarFace(){
  const av=EST.avatares||{}; const url=av.url||'';
  return `<div class="face">${url?`<img class="av-img${av.url_contain?' con':''}" src="${url}" alt="avatar">`:'🤖'}</div>`;
}

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
      ${avatarFace()}<div class="lv">Nv ${a.nivel}</div>
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

  // Progresso por matéria
  h += `<div class="sec">📚 Progresso por matéria</div>`;
  Object.keys(cat).forEach(mid=>{
    const c = cat[mid];
    const conc = (EST.progresso||[]).filter(p=>p.materia===mid && p.concluida).length;
    const fezQ = (EST.progresso||[]).filter(p=>p.materia===mid && !p.concluida && (p.melhor_estrela||0)>0).length;
    const estrelas = (EST.progresso||[]).filter(p=>p.materia===mid).reduce((s,p)=>s+(p.melhor_estrela||0),0);
    const tot = c.total_missoes||0, pc = tot?Math.round(conc/tot*100):0;
    h += `<div class="card mat" style="--mc:${c.cor}"><div class="ic">${c.icone}</div>
      <div class="body"><div class="row1"><div class="nm">${esc(c.nome)}</div><div class="stars">${estrelas} ⭐</div></div>
      <div class="pb"><i style="width:${pc}%"></i></div>
      <div class="meta"><span>${conc}/${tot} missões${fezQ?` • <b style="color:var(--amar)">${fezQ} aguardando leitura 📖</b>`:''}</span>${conc===tot&&tot?'<span class="ok">✓ Completo</span>':`<span>${pc}%</span>`}</div></div></div>`;
  });

  // Questões feitas — aguardando a leitura para concluir
  const pendLeitura = (EST.progresso||[]).filter(p=>!p.concluida && (p.melhor_estrela||0)>0)
    .sort((a,b)=>String(b.ultima_ts||'').localeCompare(String(a.ultima_ts||'')));
  h += `<div class="sec">📝 Questões feitas ${pendLeitura.length?`<span class="count">${pendLeitura.length} aguardando leitura</span>`:''}</div><div class="card acts">`;
  if (!pendLeitura.length) h += `<div style="color:var(--dim);font-weight:600;padding:6px">Nada pendente — todas as missões feitas já foram lidas. 🎉</div>`;
  pendLeitura.forEach(p=>{
    const c = cat[p.materia]||{}; const titulo=(c.missoes&&c.missoes[p.missao])||p.missao;
    h += `<div class="act"><div class="ai">${c.icone||'📘'}</div>
      <div class="ab"><div class="at">${esc(titulo)}</div>
      <div class="ad"><span>${fmtData(p.ultima_ts)}</span><span style="color:var(--amar);font-weight:700">• 📖 falta a leitura</span></div></div>
      <div class="ar"><div class="st">${estrelasStr(p.melhor_estrela||0)}</div></div></div>`;
  });
  h += `</div>`;

  // Conquistas (níveis bronze/prata/ouro)
  const cs = EST.conquistas||[];
  const got = cs.reduce((s,c)=>s+c.tier,0), tot = cs.reduce((s,c)=>s+c.niveis.length,0);
  h += `<div class="sec">🏅 Conquistas <span class="count">${got}/${tot}</span></div><div class="card">`;
  cs.forEach(c=>{
    const pct=Math.min(100,Math.round(c.progresso/c.meta*100));
    h += `<div class="pcq"><div class="e">${c.tier>0?c.tier_emoji:c.emoji}</div>
      <div class="pcb"><div class="pct">${esc(c.nome)}${c.tier>0?' • '+esc(c.tier_nome):''}</div>
      <div class="pcpb"><i style="width:${pct}%"></i></div></div>
      <div class="pcn">${c.maxed?'🏆':esc(c.valor+'/'+c.meta)}</div></div>`;
  });
  h += `</div>`;

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

function showToast(msg){ const t=$('toast'); t.textContent=msg; t.classList.add('show'); clearTimeout(window.__tt); window.__tt=setTimeout(()=>t.classList.remove('show'),2600); }

window.addEventListener('load', async ()=>{
  if (!senha) return;
  const r = await api('/api/pais/estado');
  if (r.status===200){ EST=r.data; $('login').classList.add('hidden'); $('app').classList.remove('hidden'); render(); }
});
