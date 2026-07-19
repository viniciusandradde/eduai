// VSA EduAI — módulo Olimpíadas de Matemática (estilo Canguru) 🏆🦘
// Usa os globals de app.js: api(), esc(), $, flow, render(), EST, burstConfetti().
// Views: oli_home, oli_nivelamento, oli_nivel_result, oli_unidade, oli_player,
//        oli_simulado, oli_relatorio.

let OLI = { est: null, unidade: null, quest: null, nivel: null, sim: null, rel: null };
let oliTimerInt = null;

const OLI_EIXO_NOMES = { numeros: '🔢 Números Engenhosos', geometria: '📐 Geometria e Visualização',
                         logica: '🧩 Lógica e Dedução', contagem: '🎲 Contagem e Padrões' };
const OLI_LETRAS = ['A', 'B', 'C', 'D', 'E'];

function oliMmss(seg){ seg = Math.max(0, seg|0); const m = Math.floor(seg/60), s = seg%60; return m + ':' + String(s).padStart(2, '0'); }

// ── entrada e estado ──────────────────────────────────
async function oliAbrir(){
  const r = await api('/api/oli/estado');
  if (r.status !== 200){ alert('Não consegui abrir as Olimpíadas agora 😕'); return; }
  OLI.est = r.data;
  flow = { view: 'oli_home' }; render();
}
async function oliRecarregar(){
  const r = await api('/api/oli/estado');
  if (r.status === 200) OLI.est = r.data;
}

// ── dispatcher chamado pelo render() de app.js ────────
function oliRender(f){
  switch (f.view){
    case 'oli_home':        return { flowBar: flowNav('Hub', "oliVoltarHub()"), body: oliHomeHTML() };
    case 'oli_nivelamento': return { flowBar: flowNav('Nivelamento', "oliSairNivelamento()"), body: oliNivelamentoHTML() };
    case 'oli_nivel_result':return { flowBar: '', body: oliNivelResultHTML() };
    case 'oli_unidade':     return { flowBar: flowNav('Olimpíadas', "oliVoltar()"), body: oliUnidadeHTML() };
    case 'oli_player':      return { flowBar: flowNav(OLI_EIXO_NOMES[OLI.unidade.eixo.id]||'Questão', "oliVoltarUnidade()"), body: oliPlayerHTML() };
    case 'oli_simulado':    return { flowBar: '', body: oliSimuladoHTML() };   // imersivo, sem voltar
    case 'oli_relatorio':   return { flowBar: flowNav('Olimpíadas', "oliVoltar()"), body: oliRelatorioHTML() };
  }
  return { flowBar: '', body: '' };
}

// Hook chamado no fim de todo render() — liga/desliga o cronômetro do simulado.
function oliAfterRender(){
  const emSimulado = flow && flow.view === 'oli_simulado' && OLI.sim && !OLI.sim.encerrado;
  if (emSimulado && !oliTimerInt) oliTimerInt = setInterval(oliTick, 1000);
  if (!emSimulado && oliTimerInt){ clearInterval(oliTimerInt); oliTimerInt = null; }
}

function oliVoltarHub(){ flow = null; render(); }
function oliVoltar(){ flow = { view: 'oli_home' }; render(); }
function oliVoltarUnidade(){ flow = { view: 'oli_unidade' }; render(); }

// ── HOME da trilha ────────────────────────────────────
function oliHomeHTML(){
  const e = OLI.est;
  if (!e) return `<div class="pad"><div class="card">Carregando… 🦘</div></div>`;
  const p = e.perfil;
  let h = `<div class="pad fade-in">`;
  h += `<div class="oli-hero"><div class="oli-hero-ic">🏆</div>
    <div><div class="oli-hero-t">Olimpíadas de Matemática</div>
    <div class="oli-hero-s">treino estilo Canguru • raciocínio, não decoreba</div></div></div>`;

  if (!p || !p.trilha){
    h += `<div class="box oli-cta">
      <div class="emoji">🦘</div><h2>Descubra sua trilha!</h2>
      <p>Responda <b>12 questões divertidas</b> (sem nota, sem pressa!) para descobrirmos a trilha perfeita para você: P, E ou B.</p>
      <button class="btn" onclick="oliNivelamentoStart()">Começar o desafio 🚀</button></div></div>`;
    return h;
  }

  h += `<div class="oli-trilha-card"><div class="oli-tr-badge">${p.trilha}</div>
    <div class="oli-tr-info"><div class="oli-tr-nm">${esc(e.trilha_nome||('Trilha '+p.trilha))}</div>
    <div class="oli-tr-sub">${p.origem==='pais' ? 'ajustada pelos seus pais 💜' : 'sugerida pelo nivelamento 🎯'}</div></div>
    <div class="oli-saltos"><span class="v">🦘 ${p.saltos||0}</span><span class="k">saltos</span></div></div>`;

  h += `<div class="sec">Unidades de treino</div>`;
  (e.unidades||[]).forEach(u => {
    const done = u.total && u.feitas >= u.total;
    h += `<button class="oli-unidade${done?' ok':''}" onclick="oliAbrirUnidade('${u.id}')">
      <div class="oli-u-ic">${u.emoji}</div>
      <div class="oli-u-b"><div class="oli-u-t">${esc(u.nome)}</div>
        <div class="oli-u-pb"><i style="width:${u.pct}%"></i></div>
        <div class="oli-u-s">${u.feitas}/${u.total} questões${done?' • completa! ✔':''}</div></div>
      <div class="go">›</div></button>`;
  });

  h += `<div class="sec">Simulado oficial</div>`;
  const aberto = e.simulado_aberto;
  (e.simulados||[]).forEach(s => {
    const emAndamento = aberto && aberto.simulado === s.id;
    h += `<div class="oli-sim-card"><div class="oli-sim-ic">⏱️</div>
      <div class="oli-sim-b"><div class="oli-u-t">${esc(s.nome)}</div>
      <div class="oli-u-s">${s.n_questoes} questões • ${Math.round(s.duracao_seg/60)} min • máx. ${s.nota_max} pts<br>
      ✅ +pontos &nbsp; ❌ −25% do valor &nbsp; ⬜ em branco 0</div></div>
      <button class="btn oli-sim-btn" onclick="${emAndamento ? 'oliSimRetomar()' : `oliSimIniciar('${s.id}')`}">${emAndamento ? 'Retomar ⏳' : 'Começar'}</button></div>`;
  });

  const hist = e.simulados_hist||[];
  if (hist.length){
    h += `<div class="sec">Sua evolução</div><div class="card oli-hist">`;
    hist.slice(-5).forEach((s2, i, arr) => {
      const ant = i > 0 ? arr[i-1].nota : null;
      const seta = ant == null ? '' : (s2.nota > ant ? ' <span class="oli-up">▲</span>' : (s2.nota < ant ? ' <span class="oli-down">▼</span>' : ' ▬'));
      h += `<div class="oli-hist-row" onclick="oliVerRelatorio(${s2.id})">
        <span class="oli-hist-d">${(s2.enviado_ts||'').slice(0,10).split('-').reverse().join('/')}</span>
        <span class="oli-hist-n"><b>${s2.nota}</b> pts${seta}</span>
        <span class="go">›</span></div>`;
    });
    h += `</div>`;
  }
  h += `<div class="foot">🦘 Pratique livre: as Olimpíadas não contam no limite diário de leitura!</div></div>`;
  return h;
}

// ── NIVELAMENTO ───────────────────────────────────────
async function oliNivelamentoStart(){
  const r = await api('/api/oli/nivelamento');
  if (r.status === 409){ await oliRecarregar(); flow = { view: 'oli_home' }; render(); return; }
  if (r.status !== 200 || !r.data.questoes){ alert('Não consegui carregar o desafio 😕'); return; }
  OLI.nivel = { questoes: r.data.questoes, idx: 0, respostas: {}, sel: null, resultado: null };
  flow = { view: 'oli_nivelamento' }; render();
}
function oliSairNivelamento(){
  if (confirm('Sair do nivelamento? Suas respostas até aqui serão perdidas.')){ OLI.nivel = null; oliVoltar(); }
}
function oliNivelamentoHTML(){
  const n = OLI.nivel; if (!n) return '';
  const q = n.questoes[n.idx], total = n.questoes.length, last = n.idx === total - 1;
  let dots = ''; n.questoes.forEach((_, i) => { dots += `<i class="${i < n.idx ? 'on' : i === n.idx ? 'cur' : ''}"></i>`; });
  let opts = '';
  q.alternativas.forEach((o, i) => {
    opts += `<button class="opc${n.sel===i?' sel':''}" onclick="oliNivelSel(${i})"><span class="mk">${OLI_LETRAS[i]}</span><span>${esc(o)}</span></button>`;
  });
  return `<div class="pad fade-in" style="display:flex;flex-direction:column;min-height:70vh">
    <div class="progdots">${dots}</div>
    <div class="ex"><div class="qn">Desafio ${n.idx+1} de ${total} <span class="oli-chip-val">${q.valor_pontos} pts</span></div>
      <div class="q">${esc(q.enunciado)}</div>${opts}</div>
    <div style="flex:1"></div>
    <div class="ctabar"><button class="btn" id="oli-cta" ${n.sel==null?'disabled':''} onclick="oliNivelProx()">${last?'Descobrir minha trilha 🎯':'Próxima →'}</button></div></div>`;
}
function oliNivelSel(i){ OLI.nivel.sel = i; render(); }
async function oliNivelProx(){
  const n = OLI.nivel;
  n.respostas[n.questoes[n.idx].id] = n.sel;
  if (n.idx < n.questoes.length - 1){ n.idx++; n.sel = null; render(); return; }
  const r = await api('/api/oli/nivelamento', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ respostas: n.respostas }) });
  if (r.status !== 200 || !r.data.ok){ alert((r.data&&r.data.erro)||'Não consegui enviar 😕'); return; }
  n.resultado = r.data;
  await oliRecarregar(); await recarregar();
  flow = { view: 'oli_nivel_result' }; render(); burstConfetti();
}
function oliNivelResultHTML(){
  const d = OLI.nivel && OLI.nivel.resultado; if (!d) return '';
  return `<div class="pad fade-in" style="padding-top:18px"><div class="box">
    <div class="emoji pop">🦘</div>
    <h2>Sua trilha é a ${d.trilha}!</h2>
    <p><b>${esc(d.trilha_nome||'')}</b></p>
    <p>Você acertou <b>${d.acertos} de ${d.total}</b> desafios — agora é treinar e saltar cada vez mais alto! 🏔️</p>
    ${(d.novas_medalhas||[]).length?`<div class="medal-toast">🏅 Nova medalha: ${d.novas_medalhas.map(m=>m.emoji+' '+esc(m.nome)).join(', ')}</div>`:''}
    <p style="color:var(--dim);font-size:13px;margin-top:10px">Seus pais podem ajustar a trilha no painel deles, se preferirem.</p>
    <button class="btn" style="margin-top:14px" onclick="oliVoltar()">Ver minha trilha 🚀</button></div></div>`;
}

// ── UNIDADE (eixo) ────────────────────────────────────
async function oliAbrirUnidade(eixo){
  const r = await api('/api/oli/unidade?eixo=' + encodeURIComponent(eixo));
  if (r.status !== 200){ alert('Não consegui abrir a unidade 😕'); return; }
  OLI.unidade = r.data;
  flow = { view: 'oli_unidade' }; render();
}
function oliUnidadeHTML(){
  const u = OLI.unidade; if (!u) return '';
  let h = `<div class="pad fade-in"><div class="subhead"><span class="big">${u.eixo.emoji}</span>
    <div><h2>${esc(u.eixo.nome)}</h2><div class="meta">Trilha ${u.trilha} • ${u.questoes.filter(q=>q.acertou).length}/${u.questoes.length} conquistadas</div></div></div>`;
  (u.estrategias||[]).forEach(s => {
    h += `<details class="oli-aula"><summary>${s.emoji} <b>Estratégia: ${esc(s.nome)}</b> <span class="oli-aula-tip">toque para ler</span></summary>
      <div class="oli-aula-tx">${esc(s.aula)}</div></details>`;
  });
  h += `<div class="sec">Questões (fácil → difícil)</div>`;
  u.questoes.forEach((q, i) => {
    const st = q.acertou ? '✔' : (q.feita ? '↻' : (i+1));
    h += `<button class="missao${q.acertou?' ok':''}" onclick="oliAbrirQuestao(${i})">
      <div class="num">${st}</div>
      <div class="info"><div class="tt">Questão ${i+1} <span class="oli-chip-val">${q.valor_pontos} pts</span></div>
      <div class="ds">${q.acertou?'Conquistada! 🦘':(q.feita?'Tente de novo — você consegue!':'Valendo '+q.valor_pontos+' saltos')}</div></div>
      <div class="go">›</div></button>`;
  });
  h += `</div>`;
  return h;
}

// ── PLAYER de questão (prática) ───────────────────────
function oliAbrirQuestao(idx){
  OLI.quest = { idx, sel: null, resultado: null };
  flow = { view: 'oli_player' }; render();
}
function oliPlayerHTML(){
  const u = OLI.unidade, st = OLI.quest; if (!u || !st) return '';
  const q = u.questoes[st.idx], d = st.resultado, last = st.idx === u.questoes.length - 1;
  let opts = '';
  q.alternativas.forEach((o, i) => {
    let cls = 'opc', mk = OLI_LETRAS[i];
    if (!d){ if (st.sel === i) cls += ' sel'; }
    else if (i === d.gabarito){ cls += ' cert'; mk = '✓'; }
    else if (i === st.sel){ cls += ' err'; mk = '✕'; }
    else cls += ' dim';
    opts += `<button class="${cls}" ${d?'disabled':''} onclick="oliQSel(${i})"><span class="mk">${mk}</span><span>${esc(o)}</span></button>`;
  });
  let fb = '';
  if (d){
    const estrat = (OLI.est && OLI.est.estrategias || []).find(e2 => e2.id === d.estrategia);
    if (d.correto){
      fb = `<div class="fb cert"><span class="fi">✅</span><span><b>Salto perfeito! +${d.saltos_ganhos||0} 🦘</b>${d.xp_ganho?` +${d.xp_ganho} XP`:''}</span></div>`;
    } else {
      fb = `<div class="fb err"><span class="fi">🤔</span><span><b>Essa pegou!</b> ${esc(d.distrator_explicado||'')}</span></div>`;
    }
    fb += `<div class="oli-solucao"><div class="oli-sol-h">📝 Solução passo a passo</div><div class="oli-sol-tx">${esc(d.solucao||'')}</div>
      ${estrat?`<div class="oli-chip-eixo">${estrat.emoji} Estratégia: <b>${esc(estrat.nome)}</b></div>`:''}</div>`;
    if ((d.novas_medalhas||[]).length)
      fb += `<div class="medal-toast">🏅 ${d.novas_medalhas.map(m=>m.emoji+' '+esc(m.nome)).join(', ')}</div>`;
  }
  const cta = !d
    ? `<button class="btn" ${st.sel==null?'disabled':''} onclick="oliQVerificar()">Verificar</button>`
    : (d.correto
        ? `<button class="btn" onclick="${last?'oliVoltarUnidade()':'oliAbrirQuestao('+(st.idx+1)+')'}">${last?'Concluir unidade 🏁':'Próxima →'}</button>`
        : `<button class="btn" onclick="oliAbrirQuestao(${st.idx})">Tentar de novo 🔄</button>
           <button class="btn-sec" style="margin-top:8px" onclick="${last?'oliVoltarUnidade()':'oliAbrirQuestao('+(st.idx+1)+')'}">${last?'Voltar à unidade':'Pular para a próxima →'}</button>`);
  return `<div class="pad fade-in" style="display:flex;flex-direction:column;min-height:70vh">
    <div class="ex"><div class="qn">Questão ${st.idx+1} de ${u.questoes.length} <span class="oli-chip-val">${q.valor_pontos} pts</span></div>
      <div class="q">${esc(q.enunciado)}</div>${opts}${fb}</div>
    <div style="flex:1"></div><div class="ctabar">${cta}</div></div>`;
}
function oliQSel(i){ if (!OLI.quest.resultado){ OLI.quest.sel = i; render(); } }
async function oliQVerificar(){
  const u = OLI.unidade, st = OLI.quest, q = u.questoes[st.idx];
  const r = await api('/api/oli/responder', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ questao: q.id, resposta: st.sel }) });
  if (r.status !== 200){ alert('Não consegui corrigir 😕'); return; }
  st.resultado = r.data;
  q.feita = true; if (r.data.correto) q.acertou = true;
  if (r.data.correto && r.data.primeira_vez_certa){ burstConfetti(); }
  await recarregar();          // XP/streak no header
  if (OLI.est && OLI.est.perfil && r.data.saltos_ganhos) OLI.est.perfil.saltos += r.data.saltos_ganhos;
  render();
}

// ── SIMULADO (modo imersivo) ──────────────────────────
async function oliSimIniciar(simuladoId){
  const r = await api('/api/oli/simulado/iniciar', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ simulado: simuladoId }) });
  if (r.status === 409){ alert((r.data&&r.data.erro)||'Você já tem um simulado em andamento.'); return; }
  if (r.status !== 200){ alert('Não consegui iniciar o simulado 😕'); return; }
  oliSimMontar(r.data);
}
function oliSimMontar(d){
  OLI.sim = { sim_id: d.sim_id, nome: d.nome, questoes: d.questoes,
    respostas: d.respostas || {}, marcadas: new Set(d.marcadas || []),
    idx: 0, deadline: Date.now() + (d.restante_seg||0) * 1000,
    fila: [], enviando: false, encerrado: false };
  flow = { view: 'oli_simulado' }; render();
}
function oliSimRestante(){ return Math.max(0, Math.round((OLI.sim.deadline - Date.now()) / 1000)); }

function oliSimuladoHTML(){
  const s = OLI.sim; if (!s) return '';
  const q = s.questoes[s.idx], total = s.questoes.length;
  const resp = s.respostas[q.id];
  const respondida = resp && resp.r != null, branco = resp && resp.branco;
  const rest = oliSimRestante();
  let grid = '';
  s.questoes.forEach((qq, i) => {
    const rr = s.respostas[qq.id];
    let cls = 'oli-nav';
    if (i === s.idx) cls += ' cur';
    if (rr && rr.r != null) cls += ' resp';
    else if (rr && rr.branco) cls += ' branco';
    if (s.marcadas.has(qq.id)) cls += ' marc';
    grid += `<button class="${cls}" onclick="oliSimIr(${i})">${i+1}</button>`;
  });
  let opts = '';
  q.alternativas.forEach((o, i) => {
    const sel = respondida && resp.r === i;
    opts += `<button class="opc${sel?' sel':''}" onclick="oliSimResp(${i})"><span class="mk">${OLI_LETRAS[i]}</span><span>${esc(o)}</span></button>`;
  });
  const marcada = s.marcadas.has(q.id);
  return `<div class="pad fade-in oli-sim">
    <div class="oli-sim-top">
      <button class="oli-sair" onclick="oliSimSair()">‹ Sair</button>
      <div class="oli-timer${rest <= 300 ? ' urg' : ''}" id="oli-timer">⏱️ ${oliMmss(rest)}</div>
      <button class="btn oli-entregar" onclick="oliSimEntregar()">Entregar ✅</button>
    </div>
    <div class="oli-navgrid">${grid}</div>
    <div class="ex"><div class="qn">Questão ${s.idx+1} de ${total} <span class="oli-chip-val">${q.valor_pontos} pts</span>
      ${branco?'<span class="oli-tag-branco">⬜ em branco</span>':''}</div>
      <div class="q">${esc(q.enunciado)}</div>${opts}</div>
    <div class="oli-sim-acoes">
      <button class="btn-sec${marcada?' on':''}" onclick="oliSimMarcar()">${marcada?'🔖 Marcada':'🔖 Marcar p/ revisão'}</button>
      <button class="btn-sec${branco?' on':''}" onclick="oliSimBranco()">${branco?'⬜ Em branco ✓':'⬜ Deixar em branco'}</button>
    </div>
    <div class="oli-sim-nav">
      <button class="btn-sec" ${s.idx===0?'disabled':''} onclick="oliSimIr(${s.idx-1})">‹ Anterior</button>
      <button class="btn-sec" ${s.idx===total-1?'disabled':''} onclick="oliSimIr(${s.idx+1})">Próxima ›</button>
    </div>
    <div class="foot">Sem dicas no simulado — igual à prova! Erro desconta 25% do valor; em branco vale 0. 🍀</div></div>`;
}

function oliTick(){
  const s = OLI.sim; if (!s || s.encerrado) return;
  const el = $('oli-timer'); const rest = oliSimRestante();
  if (el){ el.textContent = '⏱️ ' + oliMmss(rest); el.className = 'oli-timer' + (rest <= 300 ? ' urg' : ''); }
  oliSimFlush();
  if (rest <= 0){ s.encerrado = true; oliSimEnviar(true); }
}

function oliSimIr(i){ const s = OLI.sim; if (i >= 0 && i < s.questoes.length){ s.idx = i; render(); } }
function oliSimResp(i){
  const s = OLI.sim, q = s.questoes[s.idx];
  s.respostas[q.id] = { r: i };
  oliSimSalvar({ sim_id: s.sim_id, questao: q.id, resposta: i });
  render();
}
function oliSimBranco(){
  const s = OLI.sim, q = s.questoes[s.idx];
  const resp = s.respostas[q.id];
  if (resp && resp.branco){                      // reversível: tira o branco
    delete s.respostas[q.id];
    oliSimSalvar({ sim_id: s.sim_id, questao: q.id, limpar: true });
  } else {
    s.respostas[q.id] = { r: null, branco: 1 };
    oliSimSalvar({ sim_id: s.sim_id, questao: q.id, branco: true });
  }
  render();
}
function oliSimMarcar(){
  const s = OLI.sim, q = s.questoes[s.idx];
  if (s.marcadas.has(q.id)) s.marcadas.delete(q.id); else s.marcadas.add(q.id);
  oliSimSalvar({ sim_id: s.sim_id, marcadas: [...s.marcadas] });
  render();
}
async function oliSimSalvar(payload){
  const s = OLI.sim;
  const r = await api('/api/oli/simulado/salvar', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(payload) });
  if (r.status === 0){ s.fila.push(payload); return; }         // sem rede: re-tenta no tick
  if (r.data && r.data.expirado){ oliSimResultado(r.data.resultado); return; }
  if (r.data && r.data.restante_seg != null)                   // re-sincroniza com o servidor
    s.deadline = Date.now() + r.data.restante_seg * 1000;
}
async function oliSimFlush(){
  const s = OLI.sim;
  if (!s || !s.fila.length || s.enviando) return;
  const fila = s.fila; s.fila = [];
  for (const p of fila) await oliSimSalvar(p);
}
function oliSimSair(){
  if (confirm('Sair do simulado? O cronômetro CONTINUA correndo e suas respostas ficam salvas. Você pode retomar em "Simulado oficial".')){
    flow = { view: 'oli_home' }; oliRecarregar().then(render); render();
  }
}
function oliSimEntregar(){
  const s = OLI.sim;
  const n = Object.values(s.respostas).filter(r => r && r.r != null).length;
  const brancos = s.questoes.length - n;
  if (!confirm(`Entregar o simulado?\n\n✏️ ${n} respondidas\n⬜ ${brancos} em branco (valem 0, não descontam)\n\nDepois de entregar não dá para mudar!`)) return;
  s.encerrado = true;
  oliSimEnviar(false);
}
async function oliSimEnviar(auto){
  const s = OLI.sim; s.enviando = true;
  const r = await api('/api/oli/simulado/enviar', { method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ sim_id: s.sim_id }) });
  if (r.status !== 200 || !r.data){
    s.enviando = false; s.encerrado = false;
    alert('Não consegui entregar (sem internet?). Suas respostas estão salvas — tente de novo.');
    render(); return;
  }
  const rel = r.data.relatorio || (r.data.resultado && r.data.resultado.relatorio);
  oliSimResultado({ relatorio: rel, auto, novas_medalhas: r.data.novas_medalhas || [],
                    xp_ganho: r.data.xp_ganho, moedas_ganhas: r.data.moedas_ganhas });
}
async function oliSimResultado(res){
  if (oliTimerInt){ clearInterval(oliTimerInt); oliTimerInt = null; }
  OLI.sim = null;
  OLI.rel = { relatorio: res.relatorio, auto: !!res.auto, novas_medalhas: res.novas_medalhas || [],
              xp_ganho: res.xp_ganho || 0, moedas_ganhas: res.moedas_ganhas || 0 };
  await oliRecarregar(); await recarregar();
  flow = { view: 'oli_relatorio' }; render();
  if (res.relatorio && res.relatorio.nota >= 0.5 * res.relatorio.nota_max) burstConfetti();
}
async function oliVerRelatorio(id){
  const r = await api('/api/oli/simulado/relatorio?id=' + id);
  if (r.status !== 200){ alert('Relatório não encontrado 😕'); return; }
  OLI.rel = { relatorio: r.data.relatorio, auto: r.data.auto, novas_medalhas: [], xp_ganho: 0, moedas_ganhas: 0 };
  flow = { view: 'oli_relatorio' }; render();
}

// ── RELATÓRIO pós-simulado ────────────────────────────
function oliBar(label, ac, tot, extra){
  const pct = tot ? Math.round(100 * ac / tot) : 0;
  return `<div class="oli-bar-row"><span class="oli-bar-lb">${label}</span>
    <div class="oli-bar"><i style="width:${pct}%"></i></div>
    <span class="oli-bar-n">${ac}/${tot}${extra||''}</span></div>`;
}
function oliRelatorioHTML(){
  const R = OLI.rel; if (!R || !R.relatorio) return '';
  const d = R.relatorio;
  const pct = d.nota_max ? Math.round(100 * d.nota / d.nota_max) : 0;
  const emoji = pct >= 80 ? '🏆' : pct >= 60 ? '🎉' : pct >= 40 ? '💪' : '🦘';
  let delta = '';
  if (d.delta != null) delta = d.delta >= 0
    ? `<span class="oli-up">▲ +${d.delta} vs. simulado anterior</span>`
    : `<span class="oli-down">▼ ${d.delta} vs. simulado anterior</span>`;
  let h = `<div class="pad fade-in"><div class="box">
    <div class="emoji pop">${emoji}</div>
    ${R.auto ? '<div class="oli-tag-auto">⏱️ Tempo esgotado — entregue automaticamente</div>' : ''}
    <h2>${d.nota} pontos</h2>
    <p>de ${d.nota_max} possíveis (${pct}%) ${delta ? '· ' + delta : ''}</p>
    <div class="reward-row">
      ${R.xp_ganho ? `<div class="reward" style="color:var(--rox2)"><span class="k">XP</span>+${R.xp_ganho}</div>` : ''}
      ${R.moedas_ganhas ? `<div class="reward" style="color:var(--amar)"><span class="k">moedas</span>🪙 +${R.moedas_ganhas}</div>` : ''}
    </div>
    ${(R.novas_medalhas||[]).length ? `<div class="medal-toast">🏅 ${R.novas_medalhas.map(m=>m.emoji+' '+esc(m.nome)).join(', ')}</div>` : ''}
  </div>`;

  h += `<div class="card oli-resumo"><div class="oli-res-3">
    <div class="oli-res-c"><b>✅ ${d.acertos}</b><span>acertos</span></div>
    <div class="oli-res-c"><b>❌ ${d.chutes}</b><span>erros (−25%)</span></div>
    <div class="oli-res-c"><b>⬜ ${d.brancos}</b><span>em branco</span></div></div>
    <div class="oli-u-s" style="text-align:center;margin-top:8px">⏱️ tempo médio por questão: <b>${oliMmss(d.tempo_medio_seg)}</b></div></div>`;

  h += `<div class="sec">Por dificuldade</div><div class="card">`;
  [3,4,5].forEach(v => { const pv = d.por_valor[v]; if (pv) h += oliBar(v+' pts', pv.acertos, pv.total); });
  h += `</div><div class="sec">Por assunto</div><div class="card">`;
  Object.keys(d.por_eixo).forEach(e2 => {
    const pe = d.por_eixo[e2]; if (pe.total) h += oliBar(OLI_EIXO_NOMES[e2]||e2, pe.acertos, pe.total);
  });
  h += `</div>`;

  const erradas = (d.questoes||[]).filter(q => q.status === 'erro');
  if (erradas.length){
    h += `<div class="sec">Revisar erros (${erradas.length})</div>`;
    erradas.forEach(q => {
      h += `<details class="oli-aula"><summary><b>Questão ${q.n}</b> <span class="oli-chip-val">${q.valor_pontos} pts</span> ${esc(q.enunciado.slice(0,60))}…</summary>
        <div class="oli-aula-tx">
          <div class="q" style="margin-bottom:8px">${esc(q.enunciado)}</div>
          <div class="oli-rev">Você marcou: <b>${OLI_LETRAS[q.resposta]}) ${esc(q.alternativas[q.resposta]||'')}</b></div>
          ${q.distrator_explicado?`<div class="fb err" style="margin:8px 0"><span class="fi">🤔</span><span>${esc(q.distrator_explicado)}</span></div>`:''}
          <div class="oli-rev ok">Resposta certa: <b>${OLI_LETRAS[q.gabarito]}) ${esc(q.alternativas[q.gabarito])}</b></div>
          <div class="oli-sol-tx" style="margin-top:8px">${esc(q.solucao)}</div>
        </div></details>`;
    });
  }
  h += `<button class="btn" style="margin-top:16px" onclick="oliVoltar()">Voltar às Olimpíadas 🏆</button>
    <div class="foot">Treine as unidades e tente de novo — a evolução aparece aqui! 📈</div></div>`;
  return h;
}

// ── retomada automática ao entrar no módulo ───────────
async function oliSimRetomar(){
  const r = await api('/api/oli/simulado/atual');
  if (r.status !== 200) return false;
  if (r.data.expirado){ oliSimResultado(r.data.resultado); return true; }
  oliSimMontar(r.data); return true;
}
