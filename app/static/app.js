// VSA EduAI — hub do aluno (vanilla JS)
let senha = localStorage.getItem('eduai_senha') || '';
let CONT = [], EST = null, CFG = {}, RESP = {}, CUR = {};

function val(id){ const e = document.getElementById(id); return e ? e.value : ''; }
function escapeHtml(s){ return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

async function api(path, opts){
  const sep = path.includes('?') ? '&' : '?';
  let r;
  try { r = await fetch(path + sep + 'senha=' + encodeURIComponent(senha), opts); }
  catch(e){ return { status: 0, data: null }; }
  let d = null; try { d = await r.json(); } catch(e){}
  return { status: r.status, data: d };
}

document.getElementById('senha').addEventListener('keydown', e => { if (e.key === 'Enter') entrar(); });

async function entrar(){
  senha = document.getElementById('senha').value.trim();
  const r = await api('/api/conteudo');
  if (r.status !== 200){ document.getElementById('login-msg').textContent = 'Senha inválida 😕'; return; }
  localStorage.setItem('eduai_senha', senha);
  CONT = r.data.materias; CFG = r.data.config || {};
  document.getElementById('login').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');
  await recarregar(); aba('materias');
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{});
}

async function recarregar(){ const r = await api('/api/estado'); EST = r.data; CFG = (EST && EST.config) || CFG; renderHeader(); }

function renderHeader(){
  const a = EST.aluno;
  document.getElementById('h-nome').textContent = a.nome;
  document.getElementById('h-avatar').textContent = a.avatar || '🧑‍🚀';
  document.getElementById('h-nivel').textContent = a.nivel;
  document.getElementById('h-streak').textContent = a.streak;
  document.getElementById('h-moedas').textContent = a.moedas;
  document.getElementById('h-xpnum').textContent = a.xp;
  const per = a.xp_prox_nivel / a.nivel;
  const dentro = a.xp - (a.nivel - 1) * per;
  document.getElementById('h-xp').style.width = Math.max(4, Math.min(100, (dentro / per) * 100)) + '%';
}

function prog(materiaId){
  const m = CONT.find(x => x.id === materiaId);
  const tot = m.missoes.filter(x => !x.link).length;
  const conc = EST.progresso.filter(p => p.materia === materiaId && p.concluida).length;
  return { conc, tot };
}

function aba(name){
  document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('on', b.dataset.tab === name));
  if (name === 'materias') viewMaterias();
  if (name === 'medalhas') viewMedalhas();
  if (name === 'loja') viewLoja();
}

function viewMaterias(){
  let h = '<div class="grid">';
  CONT.forEach(m => {
    const p = prog(m.id); const pct = p.tot ? Math.round(p.conc / p.tot * 100) : 0;
    h += '<button class="mat" onclick="abrirMateria(\'' + m.id + '\')">'
       + '<div class="ic">' + (m.icone || '📘') + '</div>'
       + '<div class="nm">' + escapeHtml(m.nome) + '</div>'
       + '<div class="pb"><i style="width:' + pct + '%;background:' + (m.cor || '#7c3aed') + '"></i></div>'
       + '<div class="sub">' + p.conc + '/' + p.tot + ' missões</div></button>';
  });
  h += '</div>';
  document.getElementById('view').innerHTML = h;
}

function abrirMateria(id){
  const m = CONT.find(x => x.id === id);
  let h = '<button class="voltar" onclick="aba(\'materias\')">← Matérias</button>'
        + '<h2 class="sec">' + (m.icone||'') + ' ' + escapeHtml(m.nome) + '</h2>';
  m.missoes.forEach(mi => {
    const p = EST.progresso.find(x => x.materia === id && x.missao === mi.id);
    if (mi.link){
      h += '<div class="missao"><div class="info"><div class="tt">' + escapeHtml(mi.titulo) + '</div>'
         + '<div class="ds">' + escapeHtml(mi.descricao) + '</div></div>'
         + '<button class="btn" style="width:auto;padding:10px 14px" onclick="abrirTerminal()">Abrir ▶</button></div>';
      return;
    }
    const est = p ? '⭐'.repeat(p.melhor_estrela) + '☆'.repeat(3 - p.melhor_estrela) : '☆☆☆';
    const ok = (p && p.concluida) ? ' <span class="ok">✔</span>' : '';
    h += '<button class="missao" style="width:100%" onclick="abrirMissao(\'' + id + '\',\'' + mi.id + '\')">'
       + '<div class="info"><div class="tt">' + escapeHtml(mi.titulo) + ok + '</div>'
       + '<div class="ds">' + escapeHtml(mi.descricao) + '</div></div>'
       + '<div class="est">' + est + '</div></button>';
  });
  document.getElementById('view').innerHTML = h; window.scrollTo(0, 0);
}

function abrirTerminal(){ window.open(CFG.terminal_url || '#', '_blank'); }

function abrirMissao(matId, miId){
  const m = CONT.find(x => x.id === matId); const mi = m.missoes.find(x => x.id === miId);
  CUR = { matId, miId, mi }; RESP = {};
  let h = '<button class="voltar" onclick="abrirMateria(\'' + matId + '\')">← ' + escapeHtml(m.nome) + '</button>';
  if (mi.texto) h += '<div class="texto-base">' + escapeHtml(mi.texto) + '</div>';
  mi.exercicios.forEach((e, idx) => { h += renderEx(e, idx); });
  h += '<button class="btn" onclick="responder()">Responder ✅</button><div id="res-msg" class="msg"></div>';
  document.getElementById('view').innerHTML = h; window.scrollTo(0, 0);
}

function renderEx(e, idx){
  let inner = '<div class="qn">Questão ' + (idx + 1) + '</div><div class="q">' + escapeHtml(e.enunciado) + '</div>';
  if (e.tipo === 'multipla'){
    e.opcoes.forEach((o, i) => {
      inner += '<button class="opc" id="op-' + e.id + '-' + i + '" onclick="selOpc(\'' + e.id + '\',' + i + ',' + e.opcoes.length + ')">' + escapeHtml(o) + '</button>';
    });
  } else if (e.tipo === 'vf'){
    inner += '<button class="opc" id="op-' + e.id + '-1" onclick="selVF(\'' + e.id + '\',true)">Verdadeiro</button>'
           + '<button class="opc" id="op-' + e.id + '-0" onclick="selVF(\'' + e.id + '\',false)">Falso</button>';
  } else if (e.tipo === 'numerica'){
    inner += '<input type="number" id="in-' + e.id + '" inputmode="decimal" placeholder="Sua resposta">';
  } else if (e.tipo === 'lacuna'){
    inner += '<input type="text" id="in-' + e.id + '" placeholder="Complete...">';
  }
  return '<div class="ex" id="ex-' + e.id + '">' + inner + '<div class="fb hidden" id="fb-' + e.id + '"></div></div>';
}

function selOpc(id, i, n){
  RESP[id] = i;
  for (let k = 0; k < n; k++){ const el = document.getElementById('op-' + id + '-' + k); if (el) el.classList.toggle('sel', k === i); }
}
function selVF(id, v){
  RESP[id] = v;
  document.getElementById('op-' + id + '-1').classList.toggle('sel', v === true);
  document.getElementById('op-' + id + '-0').classList.toggle('sel', v === false);
}

async function responder(){
  const respostas = {};
  CUR.mi.exercicios.forEach(e => {
    if (e.tipo === 'multipla' || e.tipo === 'vf') respostas[e.id] = RESP[e.id];
    else { const el = document.getElementById('in-' + e.id); respostas[e.id] = el ? el.value : ''; }
  });
  const r = await api('/api/tentativa', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ materia: CUR.matId, missao: CUR.miId, respostas }) });
  if (r.status !== 200){ document.getElementById('res-msg').textContent = 'Erro ao enviar.'; return; }
  r.data.correcoes.forEach(c => {
    const fb = document.getElementById('fb-' + c.id);
    if (fb){ fb.classList.remove('hidden'); fb.classList.add(c.correto ? 'cert' : 'err');
             fb.textContent = (c.correto ? '✔ Certo! ' : '✘ Quase! ') + c.explicacao; }
  });
  await recarregar();
  renderResultado(r.data);
}

function renderResultado(d){
  const estrelas = '⭐'.repeat(d.estrelas) + '☆'.repeat(3 - d.estrelas);
  let h = '<div class="box"><div class="big">' + (d.estrelas >= 2 ? '🎉' : (d.estrelas >= 1 ? '👍' : '💪')) + '</div>'
        + '<div class="estrelas">' + estrelas + '</div>'
        + '<p style="margin:10px 0">Você acertou <b>' + d.acertos + '/' + d.total + '</b> e ganhou <b>' + d.xp_ganho + ' XP</b>!</p>';
  if (d.novas_medalhas && d.novas_medalhas.length)
    h += '<p>🏅 Nova medalha: ' + d.novas_medalhas.map(m => m.emoji + ' ' + m.nome).join(', ') + '</p>';
  if (d.leitura_pendente){
    h += '<p style="color:var(--dim);margin:12px 0">Falta o mais importante: a <b>LEITURA</b>! 📖</p>'
       + '<button class="btn" onclick="renderLeitura()">Ir para a leitura 📖</button>';
  } else {
    h += '<p style="color:var(--verm);margin:12px 0">Você precisa de pelo menos 1 estrela. Tente de novo!</p>'
       + '<button class="btn" onclick="abrirMissao(\'' + CUR.matId + '\',\'' + CUR.miId + '\')">Tentar de novo 🔄</button>';
  }
  h += '<button class="btn-sec" style="margin-top:8px" onclick="abrirMateria(\'' + CUR.matId + '\')">Voltar</button></div>';
  document.getElementById('view').innerHTML = h; window.scrollTo(0, 0);
}

function renderLeitura(){
  document.getElementById('view').innerHTML =
    '<div class="box leitura" style="text-align:left">'
    + '<h2 style="text-align:center">📖 Hora de ler!</h2>'
    + '<p style="color:var(--dim);text-align:center;font-size:14px">Leia um livro ou capítulo e registre. Só assim a missão é concluída — esse é o lema! 💚</p>'
    + '<label>Título do que você leu</label><input id="lt-titulo" placeholder="Ex.: O Pequeno Príncipe">'
    + '<label>Seu resumo (com suas palavras, mín. 50 letras)</label>'
    + '<textarea id="lt-resumo" placeholder="O que você aprendeu..."></textarea>'
    + '<button class="btn" style="margin-top:12px" onclick="enviarLeitura()">Enviar resumo ✅</button>'
    + '<label style="margin-top:16px">Ou envie a FOTO do resumo no papel:</label>'
    + '<input id="lt-foto" type="file" accept="image/*" capture="environment">'
    + '<button class="btn-sec" style="margin-top:8px" onclick="enviarLeituraFoto()">Enviar foto 📸</button>'
    + '<div id="lt-msg" class="msg"></div></div>';
  window.scrollTo(0, 0);
}

async function enviarLeitura(){
  const msg = document.getElementById('lt-msg');
  if (val('lt-resumo').trim().length < 50){ msg.className = 'msg err'; msg.textContent = 'Escreva um resumo maior (mín. 50 letras) ou envie a foto.'; return; }
  const r = await api('/api/leitura', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ materia: CUR.matId, missao: CUR.miId, titulo: val('lt-titulo'), resumo: val('lt-resumo') }) });
  if (r.status === 200 && r.data.ok) await concluido(r.data);
  else { msg.className = 'msg err'; msg.textContent = (r.data && r.data.erro) || 'Erro ao enviar.'; }
}

async function enviarLeituraFoto(){
  const f = document.getElementById('lt-foto').files[0]; const msg = document.getElementById('lt-msg');
  if (!f){ msg.className = 'msg err'; msg.textContent = 'Escolha/tire a foto do resumo.'; return; }
  const fd = new FormData();
  fd.append('materia', CUR.matId); fd.append('missao', CUR.miId); fd.append('titulo', val('lt-titulo')); fd.append('foto', f);
  const r = await api('/api/leitura-foto', { method: 'POST', body: fd });
  if (r.status === 200 && r.data.ok) await concluido(r.data);
  else { msg.className = 'msg err'; msg.textContent = (r.data && r.data.erro) || 'Erro ao enviar.'; }
}

async function concluido(d){
  await recarregar();
  const extra = (d.novas_medalhas && d.novas_medalhas.length)
    ? '<p>🏅 ' + d.novas_medalhas.map(m => m.emoji + ' ' + m.nome).join(', ') + '</p>' : '';
  document.getElementById('view').innerHTML =
    '<div class="box"><div class="big">🏆</div><h2>Missão concluída!</h2>'
    + '<p style="color:var(--dim);margin:10px 0">Leitura registrada. Mandou muito bem!</p>' + extra
    + '<button class="btn" onclick="abrirMateria(\'' + CUR.matId + '\')">Continuar</button></div>';
  window.scrollTo(0, 0);
}

function viewMedalhas(){
  const meds = EST.medalhas || [];
  let h = '<h2 class="sec">Suas medalhas</h2>';
  if (!meds.length) h += '<p style="color:var(--dim)">Ainda nenhuma. Conclua missões para ganhar! 🏅</p>';
  else { h += '<div>'; meds.forEach(m => { h += '<div class="med"><div class="e">' + m.emoji + '</div><div class="n">' + escapeHtml(m.nome) + '</div></div>'; }); h += '</div>'; }
  document.getElementById('view').innerHTML = h;
}

function viewLoja(){
  const a = EST.aluno;
  let h = '<h2 class="sec">Loja • 🪙 ' + a.moedas + ' moedas</h2>';
  (EST.loja || []).forEach(it => {
    const pode = a.moedas >= it.custo;
    h += '<div class="item"><div class="nm">' + escapeHtml(it.nome) + '</div>'
       + '<div class="cs">🪙 ' + it.custo + '</div>'
       + '<button class="btn" ' + (pode ? '' : 'disabled') + ' onclick="comprar(\'' + it.codigo + '\')">Comprar</button></div>';
  });
  const rec = (EST.compras || []).filter(c => c.tipo === 'recompensa');
  if (rec.length){
    h += '<h2 class="sec" style="margin-top:16px">Pedidos de recompensa</h2>';
    rec.forEach(c => { h += '<div class="item"><div class="nm">' + escapeHtml(c.nome) + '</div><div class="cs">' + (c.status === 'pendente' ? '⏳ aguardando pai' : '✔') + '</div></div>'; });
  }
  document.getElementById('view').innerHTML = h;
}

async function comprar(cod){
  const r = await api('/api/loja/comprar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ item: cod }) });
  await recarregar();
  if (r.data && r.data.ok) alert(r.data.status === 'pendente' ? 'Pedido enviado ao seu pai! 🎁' : 'Comprado! 🛍️');
  else alert((r.data && r.data.erro) || 'Não foi possível.');
  viewLoja();
}

// Auto-login se já tem senha salva
window.addEventListener('load', async () => {
  if (!senha) return;
  const r = await api('/api/conteudo');
  if (r.status === 200){
    CONT = r.data.materias; CFG = r.data.config || {};
    document.getElementById('login').classList.add('hidden');
    document.getElementById('app').classList.remove('hidden');
    await recarregar(); aba('materias');
    if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{});
  }
});
