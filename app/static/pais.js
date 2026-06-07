// VSA EduAI — painel dos pais
let senha = localStorage.getItem('eduai_pai_senha') || '';
let EST = null;

function escapeHtml(s){ return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

async function api(path, opts){
  const sep = path.includes('?') ? '&' : '?';
  let r; try { r = await fetch(path + sep + 'senha=' + encodeURIComponent(senha), opts); }
  catch(e){ return { status: 0, data: null }; }
  let d = null; try { d = await r.json(); } catch(e){}
  return { status: r.status, data: d };
}

document.getElementById('senha').addEventListener('keydown', e => { if (e.key === 'Enter') entrar(); });

async function entrar(){
  senha = document.getElementById('senha').value.trim();
  const r = await api('/api/pais/estado');
  if (r.status !== 200){ document.getElementById('login-msg').textContent = 'Senha inválida 😕'; return; }
  localStorage.setItem('eduai_pai_senha', senha);
  EST = r.data;
  document.getElementById('login').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');
  render();
}

async function recarregar(){ const r = await api('/api/pais/estado'); if (r.status === 200){ EST = r.data; render(); } }

function render(){
  const a = EST.aluno, cat = EST.catalogo || {};
  document.getElementById('h-nome').textContent = a.nome;
  document.getElementById('h-avatar').textContent = a.avatar || '🧑‍🚀';
  document.getElementById('h-nivel').textContent = a.nivel;
  document.getElementById('h-xp').textContent = a.xp;
  document.getElementById('h-streak').textContent = a.streak;
  document.getElementById('h-moedas').textContent = a.moedas;

  let h = '<h2 class="sec">Progresso por matéria</h2>';
  Object.keys(cat).forEach(mid => {
    const c = cat[mid];
    const conc = EST.progresso.filter(p => p.materia === mid && p.concluida).length;
    const est = EST.progresso.filter(p => p.materia === mid).reduce((s, p) => s + (p.melhor_estrela || 0), 0);
    const pct = c.total_missoes ? Math.round(conc / c.total_missoes * 100) : 0;
    h += '<div class="mat" style="margin-bottom:10px"><div style="display:flex;gap:8px;align-items:center">'
       + '<span class="ic" style="font-size:24px">' + (c.icone||'') + '</span>'
       + '<b style="flex:1">' + escapeHtml(c.nome) + '</b><span class="est">' + est + ' ⭐</span></div>'
       + '<div class="pb"><i style="width:' + pct + '%;background:' + (c.cor||'#7c3aed') + '"></i></div>'
       + '<div class="sub">' + conc + '/' + c.total_missoes + ' missões concluídas</div></div>';
  });

  // Medalhas
  h += '<h2 class="sec" style="margin-top:16px">Medalhas</h2>';
  if (!(EST.medalhas||[]).length) h += '<p style="color:var(--dim)">Nenhuma ainda.</p>';
  else { h += '<div>'; EST.medalhas.forEach(m => { h += '<div class="med"><div class="e">' + m.emoji + '</div><div class="n">' + escapeHtml(m.nome) + '</div></div>'; }); h += '</div>'; }

  // Pedidos de recompensa
  const rec = (EST.compras||[]).filter(c => c.tipo === 'recompensa');
  h += '<h2 class="sec" style="margin-top:16px">Pedidos de recompensa</h2>';
  if (!rec.length) h += '<p style="color:var(--dim)">Nenhum pedido.</p>';
  else rec.forEach(c => {
    const pend = c.status === 'pendente';
    h += '<div class="item"><div class="nm">' + escapeHtml(c.nome) + '</div>'
       + (pend ? '<button class="btn" style="width:auto;padding:8px 14px" onclick="aprovar(' + c.id + ')">Aprovar ✅</button>'
               : '<div class="cs" style="color:var(--verde)">✔ aprovado</div>') + '</div>';
  });

  // Últimas atividades
  h += '<h2 class="sec" style="margin-top:16px">Últimas atividades</h2>';
  const ult = EST.ultimas || [];
  if (!ult.length) h += '<p style="color:var(--dim)">Sem atividades ainda.</p>';
  else ult.slice(0, 12).forEach(t => {
    const cat2 = (EST.catalogo[t.materia] || {});
    const nomeMi = (cat2.missoes && cat2.missoes[t.missao]) || t.missao;
    const dia = (t.ts || '').slice(0, 16).replace('T', ' ');
    h += '<div class="item"><div class="nm" style="font-weight:600">' + (cat2.icone||'') + ' ' + escapeHtml(nomeMi)
       + '<div style="font-size:12px;color:var(--dim)">' + dia + '</div></div>'
       + '<div class="est">' + t.acertos + '/' + t.total + ' • ' + '⭐'.repeat(t.estrelas) + '</div></div>';
  });

  document.getElementById('view').innerHTML = h;
}

async function aprovar(id){
  await api('/api/pais/aprovar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }) });
  await recarregar();
}

window.addEventListener('load', async () => {
  if (!senha) return;
  const r = await api('/api/pais/estado');
  if (r.status === 200){ EST = r.data; document.getElementById('login').classList.add('hidden'); document.getElementById('app').classList.remove('hidden'); render(); }
});
