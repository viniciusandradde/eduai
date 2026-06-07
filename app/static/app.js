// VSA EduAI — hub do aluno (vanilla, design "Lovable")
let senha = localStorage.getItem('eduai_senha') || '';
let CONT = [], CFG = {}, EST = null;
let tab = 'materias';
let flow = null;          // {view, subject, missao, result, novasMedalhas}
let logged = false;
// estado do exercício
let exIdx = 0, exResp, exReveal = false, exAcertos = 0, exRespostas = {};

const $ = id => document.getElementById(id);
function esc(s){ return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function stars(n){ let o=''; for(let i=0;i<3;i++) o+= i<n?'⭐':'☆'; return o; }

async function api(path, opts){
  const sep = path.includes('?') ? '&' : '?';
  let r; try { r = await fetch(path + sep + 'senha=' + encodeURIComponent(senha), opts); }
  catch(e){ return { status:0, data:null }; }
  let d=null; try { d = await r.json(); } catch(e){}
  return { status:r.status, data:d };
}

// ── helpers de dados ──────────────────────────────────
function subj(id){ return CONT.find(m => m.id === id); }
function progOf(mat, mis){ return (EST.progresso||[]).find(p => p.materia===mat && p.missao===mis) || null; }
function subjStats(s){
  const reais = s.missoes.filter(m => !m.link);
  const conc = reais.filter(m => { const p=progOf(s.id,m.id); return p && p.concluida; }).length;
  return { conc, tot: reais.length, pct: reais.length ? conc/reais.length : 0 };
}

// ── boot ──────────────────────────────────────────────
async function carregar(){
  const r = await api('/api/conteudo');
  if (r.status !== 200) return false;
  CONT = r.data.materias; CFG = r.data.config || {};
  const e = await api('/api/estado'); EST = e.data; CFG = (EST && EST.config) || CFG;
  return true;
}
async function recarregar(){ const e = await api('/api/estado'); EST = e.data; }

async function entrar(){
  senha = $('senha-inp').value.trim();
  if (!(await carregar())){ const m=$('login-msg'); if(m){m.textContent='Senha inválida 😕';} return; }
  localStorage.setItem('eduai_senha', senha);
  logged = true; render();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{});
}

// ── render principal ──────────────────────────────────
function render(){
  if (!logged){ $('root').innerHTML = `<div class="eduai">${splashHTML()}</div>`;
    const i=$('senha-inp'); if(i) i.addEventListener('keydown',e=>{ if(e.key==='Enter') entrar(); }); return; }

  let flowBar='', header='', nav='', body='';
  if (flow){
    if (flow.view==='missoes'){ flowBar=flowNav('Matérias', "voltar('hub')"); body=missoesHTML(flow.subject); }
    else if (flow.view==='exercicio'){ flowBar=flowNav(flow.subject.nome, `voltar('missoes')`); body=exercicioHTML(); }
    else if (flow.view==='resultado'){ flowBar=flowNav(flow.missao.titulo, `voltar('missoes')`); body=resultadoHTML(); }
    else if (flow.view==='leitura'){ flowBar=flowNav('Leitura obrigatória', `voltar('missoes')`); body=leituraHTML(); }
    else if (flow.view==='concluido'){ body=concluidoHTML(); }
  } else {
    header = headerHTML();
    nav = navHTML();
    if (tab==='materias') body = materiasHTML();
    if (tab==='medalhas') body = medalhasHTML();
    if (tab==='loja') body = lojaHTML();
  }
  $('root').innerHTML = `<div class="eduai">${flowBar}${header}<div class="scroll">${body}</div>${nav}</div>`;
  // listeners pós-render
  const lt = $('lt-resumo'); if (lt) lt.addEventListener('input', ()=>{ const n=lt.value.trim().length; const c=$('lt-cc'); if(c){c.textContent=n+'/50 letras '+(n>=50?'✓':''); c.className='charcount'+(n>=50?' ok':'');} });
  const fi = $('lt-foto'); if (fi) fi.addEventListener('change', e=>{ const f=e.target.files[0]; const d=$('lt-drop'); if(f&&d){ d.classList.add('has'); d.querySelector('.dl').textContent=f.name+' selecionada'; d.querySelector('.ic').textContent='📸'; } });
}

function flowNav(title, backCall){
  return `<div class="flownav"><button class="back" onclick="${backCall}">‹ Voltar</button>${title?`<span class="ttl">${esc(title)}</span>`:''}</div>`;
}

function splashHTML(){
  return `<div class="splash">
    <div class="logo">📚</div>
    <h1>VSA EduAI</h1>
    <div class="tag">Leia · Aprenda · Evolua</div>
    <div class="sform">
      <input id="senha-inp" type="password" placeholder="Sua senha" autocomplete="current-password">
      <button class="btn" onclick="entrar()">Entrar</button>
    </div>
    <div class="hint" id="login-msg">🧑‍🚀 Explorador · Fundamental</div>
  </div>`;
}

function headerHTML(){
  const a = EST.aluno;
  const per = a.xp_prox_nivel / a.nivel;
  const dentro = a.xp - (a.nivel-1)*per;
  const pct = Math.max(0.02, Math.min(1, dentro/per));
  const faltam = Math.max(0, Math.round(per - dentro));
  const R=26, C=2*Math.PI*R, off=C*(1-pct);
  return `<div class="topbar">
    <div class="av-ring">
      <svg width="66" height="66" viewBox="0 0 58 58">
        <circle cx="29" cy="29" r="${R}" fill="none" stroke="#2a3040" stroke-width="4"/>
        <circle cx="29" cy="29" r="${R}" fill="none" stroke="url(#avg)" stroke-width="4" stroke-linecap="round"
          stroke-dasharray="${C.toFixed(1)}" stroke-dashoffset="${off.toFixed(1)}"/>
        <defs><linearGradient id="avg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#a78bfa"/><stop offset="1" stop-color="#7c3aed"/></linearGradient></defs>
      </svg>
      <div class="face">${a.avatar||'🧑‍🚀'}</div>
      <div class="lvbadge">Nv ${a.nivel}</div>
    </div>
    <div class="hstats">
      <div class="nome">Olá, ${esc(a.nome)}! 👋</div>
      <div class="sub">faltam <b style="color:var(--rox2)">${faltam} XP</b> para o Nível ${a.nivel+1}</div>
      <div class="xpbar"><i style="width:${(pct*100).toFixed(0)}%"></i></div>
    </div>
  </div>
  <div class="chipsrow">
    <div class="chip fire"><div class="v">🔥 ${a.streak}</div><div class="k">dias</div></div>
    <div class="chip coin"><div class="v">🪙 ${a.moedas}</div><div class="k">moedas</div></div>
    <div class="chip star"><div class="v">⭐ ${a.xp}</div><div class="k">XP total</div></div>
  </div>`;
}

function navHTML(){
  const items=[['materias','📘','Matérias'],['medalhas','🏅','Medalhas'],['loja','🛒','Loja']];
  return `<div class="bottomnav">${items.map(([id,ic,lb])=>
    `<button class="bnav${tab===id?' on':''}" onclick="setTab('${id}')"><span class="ic">${ic}</span><span class="lb">${lb}</span></button>`).join('')}</div>`;
}

function materiasHTML(){
  let h = `<div class="pad fade-in"><div class="sec first">Suas matérias</div><div class="grid">`;
  CONT.forEach(s=>{
    const st=subjStats(s); const pc=Math.round(st.pct*100);
    h += `<button class="mat" style="--mc:${s.cor}" onclick="abrirMateria('${s.id}')">
      <div class="ic">${s.icone}</div><div class="nm">${esc(s.nome)}</div>
      <div class="pb"><i style="width:${pc}%"></i></div>
      <div class="stat"><span>${st.conc}/${st.tot} missões</span>${st.conc===st.tot&&st.tot?'<span class="done">✔ 100%</span>':`<span>${pc}%</span>`}</div>
    </button>`;
  });
  h += `</div><div class="foot">VSA EduAI • <a href="/pais">painel dos pais</a></div></div>`;
  return h;
}

function missoesHTML(s){
  const st=subjStats(s); let prevDone=true;
  let h=`<div class="pad fade-in"><div class="subhead"><span class="big">${s.icone}</span>
    <div><h2>${esc(s.nome)}</h2><div class="meta">${st.conc} de ${st.tot} missões concluídas</div></div></div>`;
  s.missoes.forEach((mi,i)=>{
    if (mi.link){
      h += `<div class="missao"><div class="num" style="background:rgba(124,58,237,.15);border-color:rgba(124,58,237,.5);color:var(--rox2)">▶</div>
        <div class="info"><div class="tt">${esc(mi.titulo)} <span class="linktag">EXTRA</span></div><div class="ds">${esc(mi.descricao)}</div></div>
        <button class="btn" style="width:auto;padding:10px 14px;font-size:14px" onclick="abrirTerminal()">Abrir</button></div>`;
      return;
    }
    const p=progOf(s.id,mi.id); const done=!!(p&&p.concluida); const locked=!prevDone&&!done; const est=p?p.melhor_estrela:0;
    h += `<button class="missao${done?' ok':''}${locked?' locked':''}" ${locked?'disabled':`onclick="abrirMissao('${s.id}','${mi.id}')"`}>
      <div class="num">${done?'✔':locked?'🔒':(i+1)}</div>
      <div class="info"><div class="tt">${esc(mi.titulo)}</div><div class="ds">${esc(mi.descricao)}</div></div>
      ${done?`<div class="est">${stars(est)}</div>`:locked?'':'<div class="go">›</div>'}</button>`;
    prevDone=done;
  });
  h += `</div>`; return h;
}

// ── Exercício (um por vez) ────────────────────────────
function exercicioHTML(){
  const mi=flow.missao, exs=mi.exercicios, ex=exs[exIdx], last=exIdx===exs.length-1;
  let dots=''; exs.forEach((_,i)=>{ dots+=`<i class="${i<exIdx?'on':i===exIdx?'cur':''}"></i>`; });
  let opts='';
  if (ex.tipo==='multipla'){
    ex.opcoes.forEach((o,i)=>{ opts+=`<button class="${optClass(i)}" ${exReveal?'disabled':''} onclick="selResp(${i})"><span class="mk">${mkText(i)}</span><span>${esc(o)}</span></button>`; });
  } else if (ex.tipo==='vf'){
    [['Verdadeiro',true],['Falso',false]].forEach(([lb,v])=>{ opts+=`<button class="${vfClass(v)}" ${exReveal?'disabled':''} onclick="selResp(${v})"><span class="mk">${vfMk(v)}</span><span>${lb}</span></button>`; });
  } else {
    const cls = exReveal ? (exCorrect()?' cert':' err') : '';
    const tp = ex.tipo==='numerica'?'number':'text';
    opts = `<input id="ex-in" class="field${cls}" type="${tp}" ${ex.tipo==='numerica'?'inputmode="decimal"':''} placeholder="${ex.tipo==='numerica'?'Digite o número':'Complete...'}" value="${exResp!=null?esc(exResp):''}" ${exReveal?'disabled':''} oninput="exResp=this.value;syncCta()">`;
  }
  let fb='';
  if (exReveal){ const ok=exCorrect(); fb=`<div class="fb ${ok?'cert':'err'}"><span class="fi">${ok?'✅':'💡'}</span><span><b>${ok?'Isso! ':'Quase! '}</b>${esc(ex._exp||'')}</span></div>`; }
  const cta = !exReveal
    ? `<button class="btn" id="cta" ${respondeu()?'':'disabled'} onclick="verificar()">Verificar</button>`
    : `<button class="btn" onclick="proxima()">${last?'Ver resultado 🎯':'Próxima →'}</button>`;
  return `<div class="pad fade-in" style="display:flex;flex-direction:column;min-height:70vh">
    <div class="progdots">${dots}</div>
    ${(mi.texto&&exIdx===0)?`<div class="texto-base"><b>📄 Texto base</b>${esc(mi.texto)}</div>`:''}
    <div class="ex${exShake?' shake':''}"><div class="qn">Questão ${exIdx+1} de ${exs.length}</div>
      <div class="q">${esc(ex.enunciado)}</div>${opts}${fb}</div>
    <div style="flex:1"></div><div class="ctabar">${cta}</div></div>`;
}
let exShake=false;
function mkText(i){ const ex=flow.missao.exercicios[exIdx]; if(!exReveal) return exResp===i?String.fromCharCode(65+i):String.fromCharCode(65+i); if(i===ex._cor) return '✓'; if(i===exResp) return '✕'; return String.fromCharCode(65+i); }
function vfMk(v){ const ex=flow.missao.exercicios[exIdx]; if(exReveal){ if(v===ex._cor) return '✓'; if(v===exResp) return '✕'; } return v?'V':'F'; }
function optClass(i){ const ex=flow.missao.exercicios[exIdx]; if(!exReveal) return 'opc'+(exResp===i?' sel':''); if(i===ex._cor) return 'opc cert'; if(i===exResp) return 'opc err'; return 'opc dim'; }
function vfClass(v){ const ex=flow.missao.exercicios[exIdx]; if(!exReveal) return 'opc'+(exResp===v?' sel':''); if(v===ex._cor) return 'opc cert'; if(v===exResp) return 'opc err'; return 'opc dim'; }
function respondeu(){ return exResp!==undefined && exResp!=='' && exResp!==null; }
function exCorrect(){ return flow.missao.exercicios[exIdx]._ok===true; }
function selResp(v){ if(exReveal) return; exResp=v; render(); }
function syncCta(){ const c=$('cta'); if(c) c.disabled=!respondeu(); }

async function verificar(){
  const ex=flow.missao.exercicios[exIdx];
  const r=await api('/api/corrigir',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({materia:flow.subject.id,missao:flow.missao.id,exercicio:ex.id,resposta:exResp})});
  if(r.status!==200) return;
  ex._ok=r.data.correto; ex._exp=r.data.explicacao; ex._cor=r.data.resposta;
  exRespostas[ex.id]=exResp;
  if(r.data.correto) exAcertos++;
  else { exShake=true; setTimeout(()=>{exShake=false;render();},420); }
  exReveal=true; render();
}
async function proxima(){
  const exs=flow.missao.exercicios;
  if(exIdx===exs.length-1){
    const r=await api('/api/tentativa',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({materia:flow.subject.id,missao:flow.missao.id,respostas:exRespostas})});
    await recarregar();
    flow={view:'resultado',subject:flow.subject,missao:flow.missao,result:r.data}; render();
  } else { exIdx++; exResp=undefined; exReveal=false; render(); }
}

// ── Resultado ─────────────────────────────────────────
function resultadoHTML(){
  const d=flow.result, win=d.estrelas>=1;
  const emoji=d.estrelas>=3?'🏆':d.estrelas>=2?'🎉':win?'👍':'💪';
  let h=`<div class="pad fade-in" style="padding-top:18px"><div class="box">
    <div class="emoji pop">${emoji}</div>
    <div class="estrelas">${stars(d.estrelas)}</div>
    <h2>${win?(d.estrelas>=2?'Mandou muito bem!':'Boa!'):'Quase lá!'}</h2>
    <p>Você acertou <b>${d.acertos} de ${d.total}</b> questões.</p>
    <div class="reward-row"><div class="reward" style="color:var(--rox2)"><span class="k">XP</span>+${d.xp_ganho}</div>
    ${win?'<div class="reward" style="color:var(--amar)"><span class="k">ao concluir</span>🪙 +10</div>':''}</div>`;
  if(win){
    h+=`<div class="gate lema" style="margin-top:18px">🔑 Falta o mais importante: <b>a LEITURA</b>. Nenhuma missão se conclui sem ler — esse é o lema! 📖</div>
      <button class="btn" onclick="irLeitura()">Ir para a leitura 📖</button>`;
  } else {
    h+=`<p style="color:#fca5a5;margin-top:14px">Você precisa de pelo menos <b>1 estrela</b> (40%) para avançar.</p>
      <button class="btn" onclick="abrirMissao('${flow.subject.id}','${flow.missao.id}')">Tentar de novo 🔄</button>`;
  }
  h+=`</div></div>`; return h;
}

// ── Leitura (gate) ────────────────────────────────────
function leituraHTML(){
  return `<div class="pad fade-in" style="padding-top:18px"><div class="box gate leitura">
    <div style="text-align:center"><div class="emoji">📖</div><h2>Hora de ler!</h2>
      <p style="text-align:center">Leia um livro ou capítulo e registre. Só assim a missão conclui de verdade. 💜</p></div>
    <label>📕 Título do que você leu</label><input id="lt-titulo" type="text" placeholder="Ex.: O Pequeno Príncipe">
    <label>✍️ Seu resumo (com suas palavras)</label>
    <textarea id="lt-resumo" placeholder="O que você aprendeu na leitura de hoje..."></textarea>
    <div class="charcount" id="lt-cc">0/50 letras</div>
    <button class="btn" style="margin-top:12px" onclick="enviarLeitura()">Enviar resumo ✅</button>
    <div class="divider">ou</div>
    <div class="photo-drop" id="lt-drop" onclick="document.getElementById('lt-foto').click()">
      <div class="ic">🖼️</div><div class="dl" style="margin-top:6px;font-weight:700">Enviar FOTO do resumo no papel</div></div>
    <input id="lt-foto" type="file" accept="image/*" capture="environment" style="display:none">
    <button class="btn-sec" style="margin-top:10px" onclick="enviarLeituraFoto()">Enviar foto 📸</button>
    <div class="msg" id="lt-msg"></div></div></div>`;
}
async function enviarLeitura(){
  const msg=$('lt-msg'), resumo=$('lt-resumo').value, titulo=$('lt-titulo').value;
  if(resumo.trim().length<50){ msg.className='msg err'; msg.textContent='Escreva um resumo maior (mín. 50 letras) ou envie a foto.'; return; }
  const r=await api('/api/leitura',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({materia:flow.subject.id,missao:flow.missao.id,titulo,resumo})});
  if(r.status===200&&r.data.ok) await concluir(r.data); else { msg.className='msg err'; msg.textContent=(r.data&&r.data.erro)||'Erro.'; }
}
async function enviarLeituraFoto(){
  const msg=$('lt-msg'), f=$('lt-foto').files[0];
  if(!f){ msg.className='msg err'; msg.textContent='Escolha ou tire a foto do resumo.'; return; }
  const fd=new FormData(); fd.append('materia',flow.subject.id); fd.append('missao',flow.missao.id); fd.append('titulo',$('lt-titulo').value); fd.append('foto',f);
  const r=await api('/api/leitura-foto',{method:'POST',body:fd});
  if(r.status===200&&r.data.ok) await concluir(r.data); else { msg.className='msg err'; msg.textContent=(r.data&&r.data.erro)||'Erro.'; }
}
async function concluir(d){ await recarregar(); flow={view:'concluido',subject:flow.subject,novasMedalhas:d.novas_medalhas||[]}; render(); burstConfetti(); }

function concluidoHTML(){
  const nm=flow.novasMedalhas||[];
  return `<div class="pad fade-in" style="padding-top:18px"><div class="box">
    <div class="emoji pop">🏆</div><h2>Missão concluída!</h2>
    <p>Leitura registrada. Você ganhou <b style="color:var(--rox2)">+20 XP</b> e <b style="color:var(--amar)">🪙 +10</b> moedas!</p>
    ${nm.length?`<div class="medal-toast">🏅 Nova medalha: ${nm.map(m=>m.emoji+' '+esc(m.nome)).join(', ')}</div>`:''}
    <button class="btn" style="margin-top:18px" onclick="voltar('missoes')">Continuar 🚀</button></div></div>`;
}

// ── Medalhas ──────────────────────────────────────────
function medalhasHTML(){
  const cat=EST.medalhas_catalogo||[]; const got=cat.filter(m=>m.tem).length;
  let h=`<div class="pad fade-in"><div class="med-banner"><span class="big">🏅</span>
    <div><div class="t">${got} de ${cat.length} medalhas</div><div class="s">Conquiste todas estudando e lendo todo dia!</div></div></div>
    <div class="sec">Coleção</div><div class="medgrid">`;
  cat.forEach(m=>{ h+=`<div class="med ${m.tem?'got':'lock'}"><div class="e">${m.emoji}</div><div class="n">${esc(m.nome)}</div><div class="d">${m.tem?'Conquistada!':esc(m.dica||'')}</div></div>`; });
  h+=`</div></div>`; return h;
}

// ── Loja ──────────────────────────────────────────────
function lojaHTML(){
  const a=EST.aluno, loja=EST.loja||[], comp=EST.comprados||[], pend=EST.pendentes||[];
  const row=it=>{
    const owned=comp.includes(it.codigo), pe=pend.includes(it.codigo), pode=a.moedas>=it.custo;
    let btn = owned?'<button class="buy owned" disabled>✓ Tem</button>'
      : pe?'<button class="buy pend" disabled>⏳ Pai</button>'
      : `<button class="btn buy" ${pode?'':'disabled'} onclick="comprar('${it.codigo}')">🪙 ${it.custo}</button>`;
    return `<div class="item"><div class="ic">${it.emoji||'🎁'}</div>
      <div class="nm"><b>${esc(it.nome)}</b><span class="tag">${it.tipo==='avatar'?'Item de avatar':'Recompensa real • aprovação do pai'}</span></div>${btn}</div>`;
  };
  let h=`<div class="pad fade-in"><div class="coinbar"><div><div class="l">Seu saldo</div><div class="b">🪙 ${a.moedas}</div></div><div style="font-size:30px">🛒</div></div>`;
  h+=`<div class="sec">Avatar</div>${loja.filter(i=>i.tipo==='avatar').map(row).join('')}`;
  h+=`<div class="sec">Recompensas reais</div>${loja.filter(i=>i.tipo==='recompensa').map(row).join('')}</div>`;
  return h;
}
async function comprar(cod){
  const r=await api('/api/loja/comprar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({item:cod})});
  await recarregar();
  if(!(r.data&&r.data.ok)) alert((r.data&&r.data.erro)||'Não foi possível.');
  else if(r.data.status==='pendente') alert('Pedido enviado ao seu pai! 🎁');
  render();
}

// ── Confetti ──────────────────────────────────────────
function burstConfetti(){
  const cores=['#7c3aed','#a78bfa','#f5b301','#22c55e','#3b82f6','#ef4444'];
  const wrap=document.createElement('div'); wrap.className='confetti';
  for(let i=0;i<46;i++){ const p=document.createElement('i');
    p.style.left=(Math.random()*100)+'%'; p.style.background=cores[i%cores.length];
    p.style.animationDuration=(1.6+Math.random()*1.4)+'s'; p.style.animationDelay=(Math.random()*0.5)+'s';
    p.style.transform='rotate('+(Math.random()*360)+'deg)'; wrap.appendChild(p); }
  const root=document.querySelector('.eduai'); if(root){ root.appendChild(wrap); setTimeout(()=>wrap.remove(),2800); }
}

// ── navegação ─────────────────────────────────────────
function setTab(t){ tab=t; flow=null; render(); }
function abrirMateria(id){ flow={view:'missoes',subject:subj(id)}; render(); }
function abrirMissao(matId,misId){ const s=subj(matId); const mi=s.missoes.find(m=>m.id===misId);
  exIdx=0; exResp=undefined; exReveal=false; exAcertos=0; exRespostas={}; mi.exercicios.forEach(e=>{delete e._ok;delete e._exp;delete e._cor;});
  flow={view:'exercicio',subject:s,missao:mi}; render(); }
function irLeitura(){ flow={view:'leitura',subject:flow.subject,missao:flow.missao}; render(); }
function abrirTerminal(){ window.open(CFG.terminal_url||'#','_blank'); }
function voltar(target){
  if(target==='hub'){ flow=null; }
  else if(target==='missoes'){ flow={view:'missoes',subject:flow.subject}; }
  render();
}

// ── auto-login ────────────────────────────────────────
window.addEventListener('load', async ()=>{
  if(senha && await carregar()){ logged=true; render(); if('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{}); }
  else render();
});
