/* Aba Trajetórias: cada projeto que passou pelas comissões desde out/2018 como uma linha que
   atravessa faixas (comissões, áreas fora delas e desfecho), com o mapa de transições ao lado.
   Dados em dados/trajetorias.json (painel/trajetorias.py).

   Três camadas de desenho: fundo (faixas, grade e rótulos, Canvas 2D), linhas (WebGL) e sobre
   (destaque, Canvas 2D). As 10 mil linhas vão em WebGL porque, no Canvas 2D, milhares de traços
   translúcidos fazem a GPU do PC levar segundos para rasterizar cada quadro. */
/* global d3 */
// eslint-disable-next-line no-unused-vars
const Trajetorias = (() => {
const SPLEGIS = "https://splegisconsulta.saopaulo.sp.leg.br/Pesquisa/DetailsMateriaTramitacaoLegislativa/";

function iniciar(D, ao) {
const P = D.projetos;
const N = P.rotulo.length;
const LANES = D.faixas;
const NC = D.n_comissoes, NF = D.n_fora;
const DIA0 = Date.UTC(2018, 9, 26);
const dataDe = d => new Date(DIA0 + d * 864e5);
const fmt = d3.utcFormat("%d/%m/%Y");
const num = n => n.toLocaleString("pt-BR");

// ---------- categorias ----------
const DESF = [...LANES.slice(NC + NF), "Em tramitação"];
const DESF_COR = { "Virou norma": "--s3", "Vetado": "--s2", "Retirado": "--s5", "Ilegalidade": "--s7",
  "Fim de legislatura": "--s4", "Outro encerramento": "--cinza-1", "Em tramitação": "--s1" };
// por legislatura; cores categóricas porque, com milhares de linhas sobrepostas, tons de um mesmo azul se confundem
const ANOS = [["Até 2016", 0, 2016, "--cinza-1"], ["2017–2020", 2017, 2020, "--s4"],
  ["2021–2024", 2021, 2024, "--s3"], ["2025–2026", 2025, 9999, "--s1"]];
const TIPO_COR = ["--s1", "--s2", "--s3", "--s7"];
// Fases dentro da comissão, pelo último passo interno (as etapas do painel). A última cor
// (neutra) é para os trechos fora das comissões e as trocas de faixa.
const FASE_NOME = { sem_relator: "Sem relator", estudo: "Estudo (relator ou assessoria)", diligencia: "Diligência", pauta: "Em pauta",
  votado: "Votado", outra: "Outro passo", desconhecida: "Desconhecida" };
const FASE_COR = { sem_relator: "--s2", estudo: "--s1", diligencia: "--s7", pauta: "--s4", votado: "--s3", outra: "--s5", desconhecida: "--cinza-1" };
const FASES = D.fases.map(f => FASE_NOME[f]), NEUTRO = D.fases.length;
const ROTULO_FAIXA = { ARQUIVO: "Arquivo", OUTRAS: "Outras áreas" };

const desfIdx = new Uint8Array(N), anoIdx = new Uint8Array(N);
for (let i = 0; i < N; i++) {
  desfIdx[i] = P.desfecho[i] >= 0 ? P.desfecho[i] - NC - NF : DESF.length - 1;
  anoIdx[i] = ANOS.findIndex(a => P.ano[i] >= a[1] && P.ano[i] <= a[2]);
}
const contar = (arr, k) => { const c = new Array(k).fill(0); for (const v of arr) c[v]++; return c; };
const contagem = { desfecho: contar(desfIdx, DESF.length), ano: contar(anoIdx, ANOS.length), tipo: contar(P.tipo, D.tipos.length) };
// Fase de cada trecho: mudanças [trecho, dia, fase] em P.fases. Dias em cada fase, para a legenda.
contagem.fase = (() => {
  const d = new Array(D.fases.length).fill(0);
  for (let i = 0; i < N; i++) { const ph = P.fases[i], s = P.trechos[i];
    for (let t = 0; t < ph.length; t += 3) { const fim = t + 3 < ph.length && ph[t + 3] === ph[t] ? ph[t + 4] : s[ph[t] * 3 + 2]; d[ph[t + 2]] += fim - ph[t + 1]; } }
  const tot = d.reduce((a, b) => a + b, 0) || 1;
  return d.map(v => `${Math.round(100 * v / tot)}%`);
})();
function faseEm(i, k, dia) { // fase do trecho k no dia (ou -1)
  const ph = P.fases[i]; let f = -1;
  for (let t = 0; t < ph.length; t += 3) if (ph[t] === k && ph[t + 1] <= dia) f = t; else if (ph[t] > k) break;
  return f < 0 ? -1 : f;
}

// ---------- estado ----------
const est = {
  cor: "desfecho", eixo: "data", slot: "entrada", passou: -1, intensidade: 0,
  on: { desfecho: DESF.map(() => true), ano: ANOS.map(() => true), tipo: D.tipos.map(() => true), fase: D.fases.map(() => true) },
  sel: -1, hover: -1,
  trans: null, // [de, para]: só os projetos que fizeram esse envio

};

// posição de cada projeto dentro das faixas: fixa, para a linha manter a "altura" ao trocar de faixa
const fracEntrada = new Float32Array(N), fracAcaso = new Float32Array(N);
for (let i = 0; i < N; i++) {
  fracEntrada[i] = i / (N - 1); // os dados já vêm ordenados pela chegada à primeira comissão
  let h = 2166136261; for (const ch of P.rotulo[i]) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); }
  fracAcaso[i] = (h >>> 0) / 4294967295;
}
const frac = () => est.slot === "entrada" ? fracEntrada : fracAcaso;

// ---------- geometria das faixas ----------
const GUT = 128, TOPO = 26, BASE = 26;
let faixas = [], W = 0, H = 0;
function montarFaixas() {
  const estreito = W < 640;
  const hc = estreito ? 30 : 42, hccj = estreito ? 44 : 64, hf = estreito ? 22 : 28, hd = estreito ? 18 : 22, gap = 22;
  faixas = []; let y = TOPO;
  const grupos = [["Nas comissões", 0, NC], ["Fora das comissões", NC, NC + NF], ["Desfecho", NC + NF, LANES.length]];
  for (const [nome, a, b] of grupos) {
    y += gap;
    faixas.grupos = faixas.grupos || [];
    faixas.grupos.push([nome, y - 6]);
    for (let l = a; l < b; l++) {
      const h = l === 0 ? hccj : l < NC ? hc : l < NC + NF ? hf : hd;
      faixas[l] = { top: y, h, nome: ROTULO_FAIXA[LANES[l]] || LANES[l], terminal: l >= NC + NF };
      y += h + 2;
    }
  }
  H = y + BASE;
}
const yDe = (i, l, fr) => { const f = faixas[l]; const pad = Math.min(4, f.h * 0.15); return f.top + pad + fr[i] * (f.h - 2 * pad); };

// ---------- escalas ----------
const maxIdade = (() => { let m = 0; for (let i = 0; i < N; i++) { const s = P.trechos[i]; m = Math.max(m, s[s.length - 1] - s[1], P.dia_desfecho[i] != null ? P.dia_desfecho[i] - s[1] : 0); } return m; })();
let x0 = d3.scaleLinear(), x = x0, zoomT = d3.zoomIdentity;
function domX() { x0 = d3.scaleLinear().domain(est.eixo === "data" ? [0, D.fim] : [0, maxIdade]).range([GUT + 8, W - 14]); x = zoomT.rescaleX(x0); }

// ---------- cores ----------
let cores = {};
function lerCores() {
  const cs = getComputedStyle(document.documentElement);
  const v = n => cs.getPropertyValue(n).trim();
  cores = {
    tinta: v("--tinta"), tinta2: v("--tinta-2"), tinta3: v("--tinta-3"), grade: v("--grade"), faixa: v("--realce"),
    superficie: v("--superficie"), plano: v("--plano"),
    desfecho: DESF.map(d => v(DESF_COR[d])), ano: ANOS.map(a => v(a[3])), tipo: TIPO_COR.map(v),
    fase: [...D.fases.map(f => v(FASE_COR[f])), v("--tinta-2")], // neutro: cinza frio, bem transparente
  };
  for (const [id, chave] of [["tj-f-desfecho", "desfecho"], ["tj-f-ano", "ano"], ["tj-f-tipo", "tipo"], ["tj-f-fase", "fase"]])
    document.querySelectorAll(`#${id} .tj-chip`).forEach((b, k) => b.style.setProperty("--c", cores[chave][k]));
}
const rgba = (hex, a) => { const h = hex.replace("#", ""); const n = parseInt(h.length === 3 ? h.replace(/./g, "$&$&") : h, 16);
  return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`; };
const catDe = i => est.cor === "desfecho" ? desfIdx[i] : est.cor === "ano" ? anoIdx[i] : est.cor === "tipo" ? P.tipo[i] : NEUTRO;

// ---------- filtro ----------
let visiveis = [];
// sequência de faixas de cada projeto, com o desfecho no fim (base do mapa de transições)
const SEQ = P.rotulo.map((_, i) => { const s = P.trechos[i], q = []; for (let j = 0; j < s.length; j += 3) q.push(s[j]); if (P.desfecho[i] >= 0) q.push(P.desfecho[i]); return q; });
const fez = (i, a, b) => { const q = SEQ[i]; for (let k = 1; k < q.length; k++) if (q[k - 1] === a && q[k] === b) return true; return false; };

// O mapa conta os envios dos projetos que passam pelos outros filtros, sem o filtro de transição,
// para que dê para trocar de arco sem antes desfazer o anterior.
let base = [], transicoes = new Map(), passagensNo = [], mapaSujo = true;
function filtrar() {
  base = []; visiveis = [];
  for (let i = 0; i < N; i++) {
    if (!est.on.desfecho[desfIdx[i]] || !est.on.ano[anoIdx[i]] || !est.on.tipo[P.tipo[i]]) continue;
    if (est.passou >= 0 && !SEQ[i].includes(est.passou)) continue;
    base.push(i);
    if (est.trans && !fez(i, est.trans[0], est.trans[1])) continue;
    visiveis.push(i);
  }
  transicoes = new Map(); passagensNo = new Array(LANES.length).fill(0);
  for (const i of base) {
    const q = SEQ[i], vistas = new Set();
    for (const l of new Set(q)) passagensNo[l]++;
    for (let k = 1; k < q.length; k++) { const c = q[k - 1] * 64 + q[k]; if (!vistas.has(c)) { vistas.add(c); transicoes.set(c, (transicoes.get(c) || 0) + 1); } }
  }
  document.getElementById("tj-n").textContent = num(visiveis.length);
  const ft = document.getElementById("tj-filtro-trans");
  ft.hidden = !est.trans;
  if (est.trans) ft.textContent = `só ${nomeFaixa(est.trans[0])} → ${nomeFaixa(est.trans[1])} ✕`;
  sujo = true; mapaSujo = true;
}
const nomeFaixa = l => ROTULO_FAIXA[LANES[l]] || LANES[l];

// ---------- desenho ----------
const cvF = document.getElementById("tj-fundo"), cvL = document.getElementById("tj-linhas"), cvS = document.getElementById("tj-sobre");
const ctxF = cvF.getContext("2d"), ctxS = cvS.getContext("2d");
const quadro = document.getElementById("tj-quadro");
const STUB = 8; // dias do tracinho final na faixa do desfecho
let dpr = 1;
function dimensionar() {
  W = quadro.clientWidth; montarFaixas(); dpr = window.devicePixelRatio || 1;
  for (const c of [cvF, cvL, cvS]) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); c.style.width = W + "px"; c.style.height = H + "px"; }
  quadro.style.height = H + "px";
  domX(); sujo = true; mapaSujo = true;
}

// Geometria da linha de um projeto, em segmentos (dia, y) → (dia, y); y em px CSS.
function segmentos(i, fr, emit) { // emit(dia0, y0, dia1, y1, fase ou -1)
  const s = P.trechos[i], ph = P.fases[i], o = est.eixo === "idade" ? s[1] : 0;
  let py = null, px = 0, t = 0;
  for (let j = 0; j < s.length; j += 3) {
    const k = j / 3, y = yDe(i, s[j], fr), xa = s[j + 1] - o, xb = s[j + 2] - o;
    if (py !== null) emit(xa, py, xa, y, -1);
    while (t < ph.length && ph[t] < k) t += 3;
    if (t < ph.length && ph[t] === k) { // trecho numa comissão: um pedaço por fase
      let ini = xa, f = ph[t + 2]; t += 3;
      while (t < ph.length && ph[t] === k) { const d = ph[t + 1] - o; emit(ini, y, d, y, f); ini = d; f = ph[t + 2]; t += 3; }
      emit(ini, y, xb, y, f);
    } else emit(xa, y, xb, y, -1);
    py = y; px = xb;
  }
  if (P.desfecho[i] >= 0) {
    const y = yDe(i, P.desfecho[i], fr), xf = P.dia_desfecho[i] - o;
    if (xf > px) emit(px, py, xf, py, -1);
    emit(xf, py, xf, y, -1); emit(xf, y, xf + STUB, y, -1);
  }
}
function tracar(ctx, i, fr) { segmentos(i, fr, (a, b, c, d) => { ctx.moveTo(x(a), b); ctx.lineTo(x(c), d); }); }

const alfa = () => Math.min(0.9, Math.max(0.012, 3.2 / Math.sqrt(Math.max(1, visiveis.length)) * Math.pow(2, est.intensidade) * Math.max(1, dpr * 0.8)));
const rgb = hex => { const h = hex.replace("#", ""); const n = parseInt(h.length === 3 ? h.replace(/./g, "$&$&") : h, 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; };

// WebGL: os vértices guardam (dia, y, categoria de cor); zoom e intensidade só mudam uniforms.
let GL = null, sujo = true;
function iniciarGL() {
  const gl = cvL.getContext("webgl", { antialias: true, premultipliedAlpha: true });
  if (!gl) return null;
  const sh = (tipo, src) => { const s = gl.createShader(tipo); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; };
  const prog = gl.createProgram();
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, `attribute vec3 p; uniform vec2 kx; uniform vec2 tam; uniform vec4 pal[8]; varying vec4 cor;
    void main() { float px = p.x * kx.x + kx.y; gl_Position = vec4(px / tam.x * 2.0 - 1.0, 1.0 - p.y / tam.y * 2.0, 0.0, 1.0); cor = pal[int(p.z + 0.5)]; }`));
  gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, `precision mediump float; varying vec4 cor; void main() { gl_FragColor = vec4(cor.rgb * cor.a, cor.a); }`));
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
  gl.useProgram(prog);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  const loc = gl.getAttribLocation(prog, "p"); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 3, gl.FLOAT, false, 0, 0);
  gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  return { gl, n: 0, u: { kx: gl.getUniformLocation(prog, "kx"), tam: gl.getUniformLocation(prog, "tam"), pal: gl.getUniformLocation(prog, "pal") } };
}
try { GL = iniciarGL(); } catch (e) { console.warn("WebGL indisponível; desenhando em Canvas 2D", e); GL = null; }
cvL.addEventListener("webglcontextlost", ev => ev.preventDefault());
cvL.addEventListener("webglcontextrestored", () => { try { GL = iniciarGL(); } catch { GL = null; } sujo = true; redesenhar(); });
const ctxL = GL ? null : cvL.getContext("2d"); // reserva, se o navegador não tiver WebGL

function montarLinhas() {
  sujo = false;
  if (!GL) return;
  const fr = frac(), arr = [];
  const porFase = est.cor === "fase";
  for (const i of visiveis) {
    const c = catDe(i);
    segmentos(i, fr, (a, b, cc, d, f) => {
      if (porFase && f >= 0 && !est.on.fase[f]) return;
      const k = porFase && f >= 0 ? f : c;
      arr.push(a, b, k, cc, d, k);
    });
  }
  GL.gl.bufferData(GL.gl.ARRAY_BUFFER, new Float32Array(arr), GL.gl.STATIC_DRAW);
  GL.n = arr.length / 3;
}

function desenharLinhas() {
  if (sujo) montarLinhas();
  const a = alfa();
  if (!GL) {
    const c = ctxL; c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, W, H);
    c.save(); c.beginPath(); c.rect(GUT, 0, W - GUT, H); c.clip();
    const pal = cores[est.cor].map(h => rgba(h, a)), fr = frac(); c.lineWidth = 1;
    for (const i of visiveis) { c.strokeStyle = pal[catDe(i)]; c.beginPath(); tracar(c, i, fr); c.stroke(); }
    c.restore(); return;
  }
  const gl = GL.gl;
  gl.viewport(0, 0, cvL.width, cvL.height);
  gl.disable(gl.SCISSOR_TEST); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
  gl.enable(gl.SCISSOR_TEST); const g = Math.round(GUT * dpr); gl.scissor(g, 0, cvL.width - g, cvL.height);
  gl.uniform2f(GL.u.kx, x(1) - x(0), x(0)); gl.uniform2f(GL.u.tam, W, H);
  const pal = new Float32Array(32);
  cores[est.cor].forEach((h, j) => { const [r, gg, b] = rgb(h); pal.set([r / 255, gg / 255, b / 255, est.cor === "fase" && j === NEUTRO ? a * 0.2 : a], j * 4); });
  gl.uniform4fv(GL.u.pal, pal);
  gl.drawArrays(gl.LINES, 0, GL.n);
}

function eixoTicks() {
  const [a, b] = x.domain();
  if (est.eixo === "data") {
    const t = d3.scaleUtc().domain([dataDe(a), dataDe(b)]).range(x.range());
    const ticks = t.ticks(Math.max(3, Math.floor((W - GUT) / 90)));
    const f = (b - a) > 900 ? d3.utcFormat("%Y") : d3.utcFormat("%b %Y");
    return ticks.map(d => [t(d), f(d)]);
  }
  const span = b - a, passo = span > 1500 ? 365 : span > 500 ? 182.5 : span > 120 ? 30.4 : 7;
  const out = []; for (let d = Math.ceil(a / passo) * passo; d <= b; d += passo) {
    const rot = passo >= 182 ? (d / 365 === Math.round(d / 365) ? `${Math.round(d / 365)} ano${Math.round(d / 365) === 1 ? "" : "s"}` : `${(d / 365).toFixed(1).replace(".", ",")} anos`)
      : passo > 7 ? `${Math.round(d / 30.4)} m` : `${Math.round(d)} d`;
    out.push([x(d), d === 0 ? "0" : rot]);
  }
  return out;
}

function desenharFundo() {
  const c = ctxF; c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, W, H);
  // faixas
  faixas.forEach((f, l) => { c.fillStyle = l % 2 ? cores.superficie : cores.faixa; c.fillRect(GUT, f.top, W - GUT, f.h); });
  // grade e eixo
  const ticks = eixoTicks();
  c.strokeStyle = cores.grade; c.lineWidth = 1; c.beginPath();
  for (const [px] of ticks) { c.moveTo(Math.round(px) + 0.5, TOPO); c.lineTo(Math.round(px) + 0.5, H - BASE + 4); }
  c.stroke();
  c.fillStyle = cores.tinta3; c.font = "11px " + getComputedStyle(document.body).fontFamily; c.textAlign = "center"; c.textBaseline = "alphabetic";
  for (const [px, t] of ticks) if (px > GUT + 10 && px < W - 10) { c.fillText(t, px, TOPO - 8); c.fillText(t, px, H - 8); }
  // início das legislaturas
  if (est.eixo === "data") {
    c.save(); c.setLineDash([3, 3]); c.strokeStyle = cores.tinta3; c.textAlign = "left";
    for (const [ano, rot] of [[2021, "19ª legislatura"], [2025, "20ª legislatura"]]) {
      const px = x((Date.UTC(ano, 0, 1) - DIA0) / 864e5); if (px < GUT || px > W) continue;
      c.beginPath(); c.moveTo(px, TOPO + 4); c.lineTo(px, H - BASE); c.stroke();
      c.fillStyle = cores.tinta2; c.fillText(rot, px + 4, TOPO + 12);
    }
    c.restore();
  }
  // rótulos das faixas (por cima, com fundo)
  c.fillStyle = cores.superficie; c.fillRect(0, 0, GUT, H);
  c.textAlign = "right"; c.textBaseline = "middle";
  faixas.forEach((f, l) => {
    c.fillStyle = f.terminal ? cores.tinta2 : cores.tinta;
    c.font = `${l < NC ? 600 : 400} ${f.h < 24 ? 11 : 12}px ` + getComputedStyle(document.body).fontFamily;
    c.fillText(f.nome, GUT - 10, f.top + f.h / 2);
  });
}

function desenharSobre() {
  const c = ctxS; c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, W, H);
  // nomes dos blocos de faixas, por cima das linhas
  c.textAlign = "left"; c.textBaseline = "alphabetic"; c.font = "600 10.5px " + getComputedStyle(document.body).fontFamily; c.fillStyle = cores.tinta3;
  for (const [nome, y] of faixas.grupos) {
    const t = nome.toUpperCase(), w = c.measureText(t).width;
    c.fillStyle = cores.superficie; c.fillRect(4, y - 11, w + 8, 15);
    c.fillStyle = cores.tinta3; c.fillText(t, 8, y);
  }
  c.save(); c.beginPath(); c.rect(GUT, 0, W - GUT, H); c.clip(); c.lineCap = "round";
  const fr = frac();
  for (const [i, larg] of [[est.sel, 2.4], [est.hover, 1.8]]) {
    if (i < 0) continue;
    c.lineJoin = "round"; c.beginPath(); tracar(c, i, fr);
    c.strokeStyle = cores.superficie; c.lineWidth = larg + 3; c.stroke();
    c.strokeStyle = i === est.sel ? cores.tinta : cores[est.cor][catDe(i)]; c.lineWidth = larg; c.stroke();
    if (est.cor === "fase") {
      c.lineWidth = larg + 0.6;
      segmentos(i, fr, (a, b, cc, d, f) => { if (f < 0) return; c.strokeStyle = cores.fase[f]; c.beginPath(); c.moveTo(x(a), b); c.lineTo(x(cc), d); c.stroke(); });
      c.strokeStyle = i === est.sel ? cores.tinta : cores.tinta2;
    }
    // pontos de envio
    const s = P.trechos[i], o = est.eixo === "idade" ? s[1] : 0;
    c.fillStyle = c.strokeStyle;
    for (let j = 0; j < s.length; j += 3) { c.beginPath(); c.arc(x(s[j + 1] - o), yDe(i, s[j], fr), larg + 0.8, 0, 7); c.fill(); }
    if (P.desfecho[i] >= 0) { c.beginPath(); c.arc(x(P.dia_desfecho[i] - o + STUB), yDe(i, P.desfecho[i], fr), larg + 1.6, 0, 7); c.fill(); }
  }
  c.restore();
  focoMapa(est.hover >= 0 ? est.hover : est.sel);
}

let pendente = 0;
function redesenhar(tudo = true) {
  if (pendente) return;
  pendente = requestAnimationFrame(() => { pendente = 0; if (mapaSujo) desenharMapa(); if (tudo) { desenharFundo(); desenharLinhas(); } desenharSobre(); });
}

// ---------- busca do projeto sob o mouse ----------
function acharPerto(mx, my) {
  let l = -1; faixas.forEach((f, k) => { if (my >= f.top - 1 && my <= f.top + f.h + 1) l = k; });
  if (l < 0 || mx < GUT) return -1;
  const fr = frac(), tol = 4 / Math.max(1e-9, (x(1) - x(0)));
  const dia = x.invert(mx); let melhor = -1, dist = 7;
  for (const i of visiveis) {
    const s = P.trechos[i], o = est.eixo === "idade" ? s[1] : 0, d = dia + o;
    let ok = false;
    for (let j = 0; j < s.length; j += 3) if (s[j] === l && d >= s[j + 1] - tol && d <= s[j + 2] + tol) { ok = true; break; }
    if (!ok && P.desfecho[i] === l && d >= P.dia_desfecho[i] - tol && d <= P.dia_desfecho[i] + 12 / (x(1) - x(0)) + tol) ok = true;
    if (!ok) continue;
    const dd = Math.abs(yDe(i, l, fr) - my); if (dd < dist) { dist = dd; melhor = i; }
  }
  return melhor;
}

const dica = document.getElementById("tj-dica");
function lugarEm(i, dia) {
  const s = P.trechos[i], o = est.eixo === "idade" ? s[1] : 0, d = dia + o;
  for (let j = 0; j < s.length; j += 3) if (d >= s[j + 1] - 1 && d <= s[j + 2] + 1) return [s[j], s[j + 1], s[j + 2], j / 3, d];
  return P.desfecho[i] >= 0 ? [P.desfecho[i], P.dia_desfecho[i], null] : null;
}
function mostrarDica(i, mx, my) {
  if (i < 0) { dica.hidden = true; return; }
  const lg = lugarEm(i, x.invert(mx));
  const onde = lg ? (lg[2] == null ? `${LANES[lg[0]]} em ${fmt(dataDe(lg[1]))}` : `${faixas[lg[0]].nome}: ${fmt(dataDe(lg[1]))} a ${fmt(dataDe(lg[2]))} (${num(lg[2] - lg[1])} dias)`) : "";
  dica.innerHTML = `<strong></strong> <span></span><p class="e"></p><p class="o"></p>`;
  dica.querySelector("strong").textContent = P.rotulo[i];
  dica.querySelector("span").textContent = "· " + DESF[desfIdx[i]];
  dica.querySelector(".e").textContent = P.ementa[i].length > 120 ? P.ementa[i].slice(0, 118) + "…" : P.ementa[i];
  let fase = "";
  if (lg && lg[2] != null && lg[0] < NC) {
    const t = faseEm(i, lg[3], lg[4]);
    if (t >= 0) fase = ` · ${FASES[P.fases[i][t + 2]].toLowerCase()} desde ${fmt(dataDe(P.fases[i][t + 1]))}`;
  }
  dica.querySelector(".o").textContent = onde + fase;
  dica.hidden = false;
  const bw = dica.offsetWidth, bh = dica.offsetHeight;
  dica.style.left = Math.min(W - bw - 6, mx + 14) + "px";
  dica.style.top = (my + bh + 20 > H ? my - bh - 12 : my + 14) + "px";
}

// ---------- detalhe ----------
const det = document.getElementById("tj-detalhe");
function mostrarDetalhe() {
  const i = est.sel;
  if (i < 0) { det.innerHTML = `<p class="tj-vazio">Clique numa linha ou busque um projeto para ver a trajetória dele aqui.</p>`; return; }
  const s = P.trechos[i];
  const linhas = [];
  for (let j = 0; j < s.length; j += 3) {
    const l = s[j], aberto = s[j + 2] >= D.fim && P.desfecho[i] < 0 && j === s.length - 3;
    linhas.push([l < NC ? LANES[l] : `${faixas[l].nome} (fora das comissões)`, fmt(dataDe(s[j + 1])) + (s[j + 1] === 0 && s[j] < NC ? " ou antes" : ""),
      aberto ? "hoje" : fmt(dataDe(s[j + 2])), num(s[j + 2] - s[j + 1]), l < NC ? resumoFases(i, j / 3) : "", D.nomes[LANES[l]] || ""]);
  }
  if (P.desfecho[i] >= 0) linhas.push([LANES[P.desfecho[i]], fmt(dataDe(P.dia_desfecho[i])), "", "", "", "Desfecho"]);
  const total = (P.desfecho[i] >= 0 ? P.dia_desfecho[i] : s[s.length - 1]) - s[1];
  det.innerHTML = `<h2><span class="r"></span><small class="d"></small></h2><p class="e"></p><p class="u"></p><p class="l" hidden><a target="_blank" rel="noopener">Abrir no SPLEGIS ↗</a></p>
    <div class="tj-tabela"><table><thead><tr><th>Onde</th><th>De</th><th>Até</th><th class="num">Dias</th><th>Dias em cada fase</th><th>Área</th></tr></thead><tbody></tbody></table></div>`;
  det.querySelector(".r").textContent = P.rotulo[i];
  det.querySelector(".d").textContent = `${DESF[desfIdx[i]]} · ${num(total)} dias desde a 1ª comissão`;
  det.querySelector(".e").textContent = P.ementa[i] || "(sem ementa)";
  det.querySelector(".u").textContent = P.autor[i] ? "Autoria: " + P.autor[i] : "";
  if (P.id[i]) { det.querySelector(".l").hidden = false; det.querySelector(".l a").href = SPLEGIS + P.id[i]; }
  const tb = det.querySelector("tbody");
  for (const ln of linhas) { const tr = tb.insertRow(); ln.forEach((v, k) => { const td = tr.insertCell(); td.textContent = v; if (k === 3) td.className = "num"; }); }
}
function resumoFases(i, k) {
  const ph = P.fases[i], s = P.trechos[i], dias = new Map();
  for (let t = 0; t < ph.length; t += 3) {
    if (ph[t] !== k) continue;
    const fim = t + 3 < ph.length && ph[t + 3] === k ? ph[t + 4] : s[k * 3 + 2];
    dias.set(ph[t + 2], (dias.get(ph[t + 2]) || 0) + fim - ph[t + 1]);
  }
  return [...dias].sort((a, b) => a[0] - b[0]).map(([f, d]) => `${FASES[f].toLowerCase()} ${num(d)}`).join(" · ");
}
function selecionar(i) { est.sel = i; mostrarDetalhe(); redesenhar(false); }

// ---------- mapa de transições ----------
// Diagrama de arcos alinhado às faixas do gráfico: cada ponto é uma faixa, na mesma altura dela.
const svgM = document.getElementById("tj-mapa-svg"), infoM = document.getElementById("tj-mapa-info"), listaM = document.getElementById("tj-mapa-lista");
const mapaEmbaixo = window.matchMedia("(max-width: 900px)"); // embaixo do gráfico, o mapa precisa dos próprios rótulos
const deCodigo = c => [Math.floor(c / 64), c % 64];
let arcos = [];
function desenharMapa() {
  mapaSujo = false;
  const w = svgM.clientWidth || 300, labW = mapaEmbaixo.matches ? 118 : 0;
  const ax = labW + (w - labW) / 2, maxB = (w - labW) / 2 - 10;
  svgM.setAttribute("viewBox", `0 0 ${w} ${H}`); svgM.setAttribute("height", H);
  const yc = l => faixas[l].top + faixas[l].h / 2;
  const minimo = Math.max(2, Math.round(base.length * 0.003));
  arcos = [...transicoes].filter(([, n]) => n >= minimo).sort((a, b) => b[1] - a[1]);
  const maxN = arcos.length ? arcos[0][1] : 1, maxP = Math.max(1, ...passagensNo);
  let h = "";
  faixas.forEach((f, l) => { h += `<rect class="${l % 2 ? "banda-b" : "banda-a"}" x="0" y="${f.top}" width="${w}" height="${f.h}"/>`; });
  h += `<text x="${w - 8}" y="${H - 8}" text-anchor="end">arcos com ${num(minimo)}+ projetos</text>`;
  h += `<line class="eixo" x1="${ax}" x2="${ax}" y1="${TOPO}" y2="${H - BASE}"/>`;
  h += `<text x="${ax - 8}" y="${TOPO - 8}" text-anchor="end">↑ voltas</text><text x="${ax + 8}" y="${TOPO - 8}">envios para baixo ↓</text>`;
  for (const [c, n] of arcos) { // os grossos primeiro: os finos ficam por cima e continuam clicáveis
    const [a, b] = deCodigo(c), ya = yc(a), yb = yc(b), dir = b > a ? 1 : -1;
    const bx = dir * Math.min(maxB, 10 + 0.45 * Math.abs(yb - ya)) * 1.33;
    const esc = est.trans && est.trans[0] === a && est.trans[1] === b;
    const cor = b >= NC + NF ? ` style="--cor: var(${DESF_COR[LANES[b]]})"` : ""; // envios para um desfecho levam a cor dele
    h += `<path class="arco${esc ? " escolhido" : ""}" data-c="${c}"${cor} d="M${ax},${ya}C${ax + bx},${ya} ${ax + bx},${yb} ${ax},${yb}" stroke-width="${(0.8 + 10 * Math.sqrt(n / maxN)).toFixed(2)}"></path>`;
  }
  faixas.forEach((f, l) => {
    const r = 2.5 + 6 * Math.sqrt(passagensNo[l] / maxP);
    const cor = l >= NC + NF ? `var(${DESF_COR[LANES[l]]})` : l < NC ? "var(--tinta)" : "var(--tinta-2)";
    const esc = est.passou === l || (l >= NC + NF && est.on.desfecho.filter(Boolean).length === 1 && est.on.desfecho[l - NC - NF]);
    h += `<circle class="no${esc ? " escolhido" : ""}" data-l="${l}" cx="${ax}" cy="${yc(l)}" r="${r.toFixed(1)}" fill="${cor}"></circle>`;
    if (labW) h += `<text class="rot" x="${labW - 8}" y="${yc(l) + 4}" text-anchor="end">${f.nome}</text>`;
  });
  svgM.innerHTML = h;
  svgM.classList.toggle("com-escolha", !!est.trans);
  listaM.innerHTML = "";
  for (const [c, n] of arcos.slice(0, 10)) {
    const [a, b] = deCodigo(c), li = document.createElement("li"), bt = document.createElement("button");
    bt.type = "button"; bt.setAttribute("aria-pressed", String(!!est.trans && est.trans[0] === a && est.trans[1] === b));
    bt.innerHTML = "<span></span><b></b>"; bt.querySelector("span").textContent = `${nomeFaixa(a)} → ${nomeFaixa(b)}`; bt.querySelector("b").textContent = num(n);
    bt.addEventListener("click", () => alternarTrans(a, b));
    li.appendChild(bt); listaM.appendChild(li);
  }
  infoM.textContent = infoPadrao();
}
function infoPadrao() {
  if (!est.trans) return "Passe o mouse num arco ou ponto para ver quantos projetos.";
  const [a, b] = est.trans;
  return `Mostrando só os ${num(visiveis.length)} projetos que foram de ${nomeFaixa(a)} para ${nomeFaixa(b)}. Clique de novo no arco para desfazer.`;
}
function descrever(el) {
  if (el.dataset.c) {
    const c = +el.dataset.c, [a, b] = deCodigo(c), n = transicoes.get(c) || 0;
    const pct = passagensNo[a] ? Math.round(100 * n / passagensNo[a]) : 0;
    return `${nomeFaixa(a)} → ${nomeFaixa(b)}: ${num(n)} projetos (${pct}% dos ${num(passagensNo[a])} que passaram por ${nomeFaixa(a)}).`;
  }
  const l = +el.dataset.l;
  return l >= NC + NF ? `${nomeFaixa(l)}: ${num(passagensNo[l])} projetos tiveram este desfecho.` : `${nomeFaixa(l)}: ${num(passagensNo[l])} projetos passaram por aqui.`;
}
function alternarTrans(a, b) {
  est.trans = est.trans && est.trans[0] === a && est.trans[1] === b ? null : [a, b];
  filtrar(); redesenhar();
}
function focoMapa(i) {
  const q = i >= 0 ? SEQ[i] : [], cs = new Set();
  for (let k = 1; k < q.length; k++) cs.add(q[k - 1] * 64 + q[k]);
  svgM.querySelectorAll(".arco").forEach(p => p.classList.toggle("foco", cs.has(+p.dataset.c)));
}
svgM.addEventListener("mouseover", ev => { const t = ev.target.closest("[data-c],[data-l]"); infoM.textContent = t ? descrever(t) : infoPadrao(); });
svgM.addEventListener("mouseleave", () => { infoM.textContent = infoPadrao(); });
svgM.addEventListener("click", ev => {
  const t = ev.target.closest("[data-c],[data-l]"); if (!t) return;
  if (t.dataset.c) { const [a, b] = deCodigo(+t.dataset.c); alternarTrans(a, b); return; }
  const l = +t.dataset.l;
  if (l >= NC + NF) { // desfecho: mostra só ele (ou volta a mostrar todos)
    const k = l - NC - NF, so = est.on.desfecho.filter(Boolean).length === 1 && est.on.desfecho[k];
    est.on.desfecho = est.on.desfecho.map((_, j) => so || j === k);
    document.querySelectorAll("#tj-f-desfecho .tj-chip").forEach((c, j) => c.setAttribute("aria-pressed", est.on.desfecho[j]));
  } else { escolherFaixa(est.passou === l ? -1 : l); return; }
  filtrar(); redesenhar();
});
document.getElementById("tj-filtro-trans").addEventListener("click", () => { est.trans = null; filtrar(); redesenhar(); });

// ---------- controles ----------
function segmento(id, chave) {
  const el = document.getElementById(id);
  el.addEventListener("click", ev => {
    const b = ev.target.closest("button"); if (!b) return;
    est[chave] = b.dataset.v;
    el.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", x === b));
    if (chave === "eixo") { zoomT = d3.zoomIdentity; d3.select(cvS).call(zoom.transform, zoomT); domX(); }
    if (chave === "cor") marcarCores();
    sujo = true; redesenhar();
  });
}
segmento("tj-cor", "cor"); segmento("tj-eixo", "eixo"); segmento("tj-slot", "slot");

function chips(id, chave, nomes) {
  const el = document.getElementById(id);
  nomes.forEach((nome, k) => {
    const b = document.createElement("button"); b.type = "button"; b.className = "tj-chip"; b.setAttribute("aria-pressed", "true");
    b.innerHTML = `<i></i><span></span> <b></b>`; b.querySelector("span").textContent = nome; b.querySelector("b").textContent = typeof contagem[chave][k] === "string" ? contagem[chave][k] : num(contagem[chave][k]);
    b.addEventListener("click", ev => {
      if (ev.altKey || ev.shiftKey) est.on[chave] = est.on[chave].map((_, j) => j === k); // só este
      else est.on[chave][k] = !est.on[chave][k];
      el.querySelectorAll(".tj-chip").forEach((c, j) => c.setAttribute("aria-pressed", est.on[chave][j]));
      filtrar(); redesenhar();
    });
    el.appendChild(b);
  });
}
chips("tj-f-desfecho", "desfecho", DESF); chips("tj-f-ano", "ano", ANOS.map(a => a[0])); chips("tj-f-tipo", "tipo", D.tipos); chips("tj-f-fase", "fase", FASES);
function marcarCores() {
  for (const [id, chave] of [["tj-f-desfecho", "desfecho"], ["tj-f-ano", "ano"], ["tj-f-tipo", "tipo"], ["tj-f-fase", "fase"]])
    document.querySelectorAll(`#${id} .tj-chip`).forEach(b => b.classList.toggle("colorido", est.cor === chave));
  document.getElementById("tj-g-fase").hidden = est.cor !== "fase";
}

const passou = document.getElementById("tj-passou");
passou.innerHTML = `<option value="-1">Qualquer faixa</option><optgroup label="Comissões">` + LANES.slice(0, NC).map((l, k) => `<option value="${k}">${l}</option>`).join("")
  + `</optgroup><optgroup label="Fora das comissões">` + LANES.slice(NC, NC + NF).map((l, k) => `<option value="${NC + k}">${nomeFaixa(NC + k)}</option>`).join("") + `</optgroup>`;
passou.addEventListener("change", () => escolherFaixa(+passou.value));
// Uma comissão escolhida aqui (ou no mapa) vira o filtro de comissão do painel, que volta por
// atualizar(); uma faixa de fora das comissões fica só aqui, com o filtro do painel em "Todas".
function escolherFaixa(l) {
  est.passou = l; passou.value = l;
  if (l >= 0 && l < NC) { ao.comissao(LANES[l]); return; }
  if (comissaoPainel !== "TODAS") { ao.comissao("TODAS"); return; }
  filtrar(); redesenhar();
}
document.getElementById("tj-intensidade").addEventListener("input", ev => { est.intensidade = +ev.target.value; redesenhar(); });

// busca: sugere até 8 rótulos (uma lista com os 10 mil travava o campo no Chrome do PC)
const indice = new Map(P.rotulo.map((r, i) => [r, i]));
const busca = document.getElementById("tj-busca"), sug = document.getElementById("tj-sugestoes");
const normal = v => v.trim().toUpperCase().replace(/\s+/g, " ").replace(/^(PL|PDL|PR|PLO) ?(\d)/, "$1 $2");
let opcoes = [], ativa = -1;
function sugerir() {
  const q = normal(busca.value); opcoes = []; ativa = -1;
  if (q.length >= 2) for (let i = 0; i < N && opcoes.length < 8; i++) if (P.rotulo[i].startsWith(q) || (/^\d/.test(q) && P.rotulo[i].includes(" " + q))) opcoes.push(i);
  sug.innerHTML = "";
  for (const i of opcoes) {
    const li = document.createElement("li"), b = document.createElement("button");
    b.type = "button"; b.textContent = P.rotulo[i]; b.addEventListener("mousedown", ev => { ev.preventDefault(); escolher(i); });
    li.appendChild(b); sug.appendChild(li);
  }
  sug.hidden = !opcoes.length; busca.setAttribute("aria-expanded", String(!sug.hidden));
}
function escolher(i) { busca.value = P.rotulo[i]; sug.hidden = true; busca.setCustomValidity(""); selecionar(i); }
busca.addEventListener("input", () => { busca.setCustomValidity(""); sugerir(); });
busca.addEventListener("blur", () => { sug.hidden = true; });
busca.addEventListener("keydown", ev => {
  if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
    if (!opcoes.length) return; ev.preventDefault();
    ativa = (ativa + (ev.key === "ArrowDown" ? 1 : -1) + opcoes.length) % opcoes.length;
    sug.querySelectorAll("button").forEach((b, k) => b.classList.toggle("ativo", k === ativa));
  } else if (ev.key === "Escape") { sug.hidden = true; }
  else if (ev.key === "Enter") {
    const q = normal(busca.value);
    const i = ativa >= 0 ? opcoes[ativa] : indice.has(q) ? indice.get(q) : opcoes[0];
    if (i == null) { busca.setCustomValidity("Projeto não encontrado entre os que passaram por comissões desde 2018."); busca.reportValidity(); return; }
    escolher(i);
  }
});

// zoom só no eixo horizontal; roda do mouse sem Ctrl continua rolando a página
const zoom = d3.zoom().scaleExtent([1, 60])
  .filter(ev => ev.type === "wheel" ? (ev.ctrlKey || ev.metaKey) : (!ev.button && ev.type !== "dblclick"))
  .on("zoom", ev => {
    const t = ev.transform; zoomT = d3.zoomIdentity.translate(t.x, 0).scale(t.k);
    x = zoomT.rescaleX(x0); dica.hidden = true; redesenhar();
  });
d3.select(cvS).call(zoom);
document.getElementById("tj-tudo").addEventListener("click", () => { d3.select(cvS).call(zoom.transform, d3.zoomIdentity); });

cvS.addEventListener("mousemove", ev => {
  const r = cvS.getBoundingClientRect(), mx = ev.clientX - r.left, my = ev.clientY - r.top;
  const i = acharPerto(mx, my);
  if (i !== est.hover) { est.hover = i; redesenhar(false); }
  mostrarDica(i, mx, my);
  cvS.style.cursor = i >= 0 ? "pointer" : "crosshair";
});
cvS.addEventListener("mouseleave", () => { est.hover = -1; dica.hidden = true; redesenhar(false); });
cvS.addEventListener("click", ev => {
  const r = cvS.getBoundingClientRect(); const i = acharPerto(ev.clientX - r.left, ev.clientY - r.top);
  selecionar(i);
});

// tamanho: com a aba escondida a largura é 0, e o desenho espera ela voltar
let ultimaW = 0;
new ResizeObserver(() => {
  if (!quadro.clientWidth || quadro.clientWidth === ultimaW) return;
  ultimaW = quadro.clientWidth; dimensionar(); redesenhar();
}).observe(quadro);

let comissaoPainel = "TODAS";
lerCores(); marcarCores();
return {
  // Chamado pelo painel a cada render, com o filtro de comissão.
  atualizar(comissao) {
    comissaoPainel = comissao;
    const l = LANES.indexOf(comissao);
    if (l >= 0 && l < NC) est.passou = l;
    else if (est.passou < NC) est.passou = -1;
    passou.value = est.passou;
    lerCores(); filtrar();
    if (quadro.clientWidth && quadro.clientWidth !== ultimaW) { ultimaW = quadro.clientWidth; dimensionar(); }
    redesenhar();
  },
};
}

let instancia = null, carregando = null;
return {
  // Baixa os dados na primeira vez que a aba é aberta. `ao.comissao(sigla)` muda o filtro de comissão do painel.
  async mostrar(comissao, ao) {
    if (!instancia) {
      carregando ??= fetch("dados/trajetorias.json").then((r) => {
        if (!r.ok) throw new Error(`dados/trajetorias.json: ${r.status}`);
        return r.json();
      });
      const D = await carregando;
      instancia ??= iniciar(D, ao);
    }
    instancia.atualizar(comissao);
  },
};
})();
