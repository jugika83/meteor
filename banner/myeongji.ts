// 부산 명지동의 밤 — 라인아트 배너.
// 명지국제신도시 아파트, 낙동강 하구와 다리, 강변 갈대, 대파밭, 산책하는 사람,
// 김해공항으로 내려가는 비행기, 그리고 별똥별.
//
// 사용법: mountMyeongji(document.querySelector('#mj')!, { every: 7 })
//   every: 별똥별이 평균 몇 초마다 하나씩 떨어지는지 (작을수록 자주)
import { el, pen, shape, blot, paint, limb, shoe, place, inkDefs, run, f, pt, PEN, type Vec } from './lib/ink.ts';
import { gait } from './lib/gait.ts';
import { spring, pendulum, pointerWind, ease, clamp, seeded, rnd, smooth } from './lib/motion.ts';

const W = 960, H = 240, S = 0.5, SP = PEN * S;
const BASE = 178;        // 건너편 강둑(아파트 밑동)
const BANK = 207;        // 이쪽 강둑 윗선
const GROUND = 222;      // 산책로(사람 발)
const INK = '#ebe4cd', INK_FAR = '#8d8ca3', PAPER_N = '#1b2140', WATER = '#121731';
const WARM = '#f1c46e', LEEK = '#6f9a58', LEEK_DARK = '#4d7340';

export interface Options { every?: number }

export function mountMyeongji(host: HTMLElement, opts: Options = {}): void {
  const every = opts.every ?? 7;
  const R = seeded(23);
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'xMidYMax slice', role: 'img', 'aria-label': '부산 명지동의 밤 풍경과 별똥별을 그린 선화 애니메이션' });
  svg.classList.add('mj');
  svg.style.color = INK;
  svg.style.setProperty('--paper', PAPER_N);
  el('style', {}, svg).textContent = '.mj .pp{fill:var(--paper)} .mj text{font-family:inherit}';
  const { defs, filter } = inkDefs(svg, 'mj');
  host.appendChild(svg);

  // ---- defs: 하늘, 빛 번짐
  const sky = el('linearGradient', { id: 'mj-sky', x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
  el('stop', { offset: 0, 'stop-color': '#090e1f' }, sky);
  el('stop', { offset: 0.72, 'stop-color': '#1d2347' }, sky);
  el('stop', { offset: 1, 'stop-color': '#3a3560' }, sky);
  const radial = (id: string, c: string, o: number) => { const g = el('radialGradient', { id }, defs); el('stop', { offset: 0, 'stop-color': c, 'stop-opacity': o }, g); el('stop', { offset: 1, 'stop-color': c, 'stop-opacity': 0 }, g); };
  radial('mj-warm', WARM, 0.8); radial('mj-moon', '#e9e4ff', 0.32); radial('mj-red', '#ff4a3a', 0.9); radial('mj-white', '#ffffff', 0.9); radial('mj-met', '#fff4d6', 0.9);
  const blur = el('filter', { id: 'mj-blur', x: '-20%', y: '-20%', width: '140%', height: '140%' }, defs);
  el('feGaussianBlur', { stdDeviation: 2.2 }, blur);

  // ---- layers
  const skyG = el('g', {}, svg);
  const scene = el('g', { filter }, svg);
  const glow = el('g', { style: 'mix-blend-mode:screen;pointer-events:none' }, svg);
  const top = el('g', { style: 'pointer-events:none' }, svg);

  // ---- 하늘
  const skyHit = el('rect', { x: -10, y: -10, width: W + 20, height: H + 10, fill: 'url(#mj-sky)', style: 'cursor:crosshair' }, skyG);
  el('title', {}, skyHit).textContent = '하늘을 누르면 별똥별이 떨어져요';
  const stars = Array.from({ length: 130 }, () => {
    const r = R(0.3, 1.05);
    return { n: el('circle', { cx: f(R(0, W)), cy: f(R(4, 165)), r: f(r), fill: '#f5efda' }, skyG), ph: R(0, 6.3), sp: R(0.5, 2.2), base: r > 0.85 ? 0.95 : R(0.35, 0.8) };
  });
  // 달 (초승달)
  const MOON: Vec = [872, 42];
  el('circle', { cx: MOON[0], cy: MOON[1], r: 46, fill: 'url(#mj-moon)' }, skyG);
  const mr = 11;
  el('path', { d: `M0 ${-mr} A${mr} ${mr} 0 1 1 0 ${mr} A${mr * 0.6} ${mr} 0 1 0 0 ${-mr}Z`, fill: '#f3ecd6', transform: `translate(${MOON[0]} ${MOON[1]}) rotate(-28)` }, skyG);
  const meteorG = el('g', { style: 'pointer-events:none' }, skyG);

  // ---- 먼 풍경 (옅은 먹): 가덕도 능선, 사장교
  const far = el('g', { opacity: 0.5 }, scene);
  shape(far, SP * 0.8).setAttribute('d', `M600 ${BASE} Q630 160 668 156 Q700 150 724 140 Q752 130 784 142 Q812 152 840 146 Q880 132 914 140 Q940 146 ${W + 5} 150 L${W + 5} ${BASE} Z`);
  pen(far, SP * 0.5).setAttribute('d', 'M690 152 q12 -4 24 -2 M792 146 q14 -3 26 1 M900 140 q10 -2 20 2');
  const deckY = 168, pylons = [472, 584];
  pen(far, SP).setAttribute('d', `M405 ${deckY} Q528 ${deckY - 3} 650 ${deckY} M405 ${deckY + 3} Q528 ${deckY} 650 ${deckY + 3}`);
  const piers: string[] = [];
  for (let x = 420; x < 650; x += 26) piers.push(`M${x} ${deckY + 3} L${x} ${BASE}`);
  pen(far, SP * 0.6).setAttribute('d', piers.join(' '));
  const cables: string[] = [];
  pylons.forEach((px) => {
    cables.push(`M${px - 3} ${BASE} L${px} 112 L${px + 3} ${BASE} M${px - 2} 130 L${px + 2} 130`);
    for (let k = 1; k <= 6; k++) cables.push(`M${px} ${118 + k * 1.6} L${px - k * 8.6} ${deckY - 1} M${px} ${118 + k * 1.6} L${px + k * 8.6} ${deckY - 1}`);
  });
  pen(far, SP * 0.45).setAttribute('d', cables.join(' '));
  // 다리 가로등
  const bridgeLights = el('g', { opacity: 0.8 }, glow);
  for (let x = 414; x < 648; x += 15) el('circle', { cx: x, cy: deckY - 1.5, r: 2.4, fill: 'url(#mj-warm)' }, bridgeLights);

  // ---- 비행기 (김해공항 접근)
  const planeG = el('g', {}, scene);
  shape(planeG, SP * 0.9).setAttribute('d', 'M-11 0 Q-9 -1.6 6 -1.4 Q11 -1 12 0 Q11 1 6 1.3 L-9 1.2 Q-11 1 -11 0Z');
  pen(planeG, SP * 0.9).setAttribute('d', 'M-1 -1 L-5 -7 L-2 -7 L4 -1 M-1 1 L-4 5 L-1.5 5 L4 1 M-9 -1 L-12 -5 L-10 -5 L-6 -1');
  const planeRed = el('circle', { r: 4, fill: 'url(#mj-red)' }, glow);
  const planeWhite = el('circle', { r: 5, fill: 'url(#mj-white)' }, glow);
  const planeLand = el('circle', { r: 7, fill: 'url(#mj-warm)' }, glow);

  // ---- 명지국제신도시 아파트
  const winGlow = el('g', { filter: 'url(#mj-blur)', opacity: 0.55 }, glow);
  const reflG = el('g', { opacity: 0.6 }, glow);
  type Pane = { r: SVGRectElement; g: SVGRectElement; on: boolean; x: number; tower: number };
  const panes: Pane[] = [];
  const towerRefl: { n: SVGPathElement; x: number; w: number; idx: number[] }[] = [];
  const beacons: { n: SVGCircleElement; ph: number }[] = [];
  const back: Array<[number, number, number]> = [[56, 34, 128], [150, 36, 146], [262, 34, 120], [372, 30, 102]];
  const front: Array<[number, number, number]> = [[16, 44, 112], [96, 40, 96], [186, 50, 140], [292, 44, 108], [338, 40, 124]];
  back.forEach(([x, w, h]) => tower(x, w, h, true));
  front.forEach(([x, w, h]) => tower(x, w, h, false));

  function tower(x: number, w: number, h: number, isFar: boolean) {
    const g = el('g', {}, scene);
    if (isFar) g.style.color = INK_FAR;
    const lw = isFar ? SP * 0.8 : SP, top = BASE - h, mid = (BASE + top) / 2;
    shape(g, lw).setAttribute('d', `M${x} ${BASE} Q${x - 0.5} ${f(mid)} ${x + 0.2} ${top} L${x + w - 0.2} ${top} Q${x + w + 0.5} ${f(mid)} ${x + w} ${BASE}Z`);
    // 옥상 구조물: 한국 아파트 특유의 왕관 프레임
    const cx = x + w / 2;
    if (R() < 0.6) {
      pen(g, lw).setAttribute('d', `M${f(cx - w * 0.3)} ${top} L${f(cx - w * 0.3)} ${top - 9} L${f(cx + w * 0.3)} ${top - 9} L${f(cx + w * 0.3)} ${top} M${f(cx - w * 0.3)} ${top - 5} L${f(cx + w * 0.3)} ${top - 5}`);
    } else {
      shape(g, lw).setAttribute('d', `M${f(cx - w * 0.22)} ${top} L${f(cx - w * 0.2)} ${top - 7} L${f(cx + w * 0.2)} ${top - 7} L${f(cx + w * 0.22)} ${top}Z`);
    }
    const fh = 4.4, floors = Math.floor((h - 8) / fh), bays = Math.max(3, Math.round((w - 4) / 8.5)), bw = (w - 4) / bays;
    const lines: string[] = [];
    for (let i = 0; i <= floors; i++) { const y = BASE - 5 - i * fh; lines.push(`M${f(x + 1.5)} ${f(y)} L${f(x + w - 1.5)} ${f(y)}`); }
    const core = Math.floor(bays / 2);
    lines.push(`M${f(x + 2 + core * bw)} ${f(BASE - 5)} L${f(x + 2 + core * bw)} ${f(BASE - 5 - floors * fh)} M${f(x + 2 + (core + 1) * bw)} ${f(BASE - 5)} L${f(x + 2 + (core + 1) * bw)} ${f(BASE - 5 - floors * fh)}`);
    pen(g, lw * 0.45).setAttribute('d', lines.join(' '));
    // 1층 필로티 기둥
    pen(g, lw * 0.6).setAttribute('d', Array.from({ length: bays + 1 }, (_, j) => `M${f(x + 2 + j * bw)} ${BASE} L${f(x + 2 + j * bw)} ${BASE - 5}`).join(' '));
    const ti = towerRefl.length, idx: number[] = [];
    for (let i = 0; i < floors; i++) for (let j = 0; j < bays; j++) {
      if (j === core) continue;
      const px = x + 2 + j * bw + 1, py = BASE - 5 - (i + 1) * fh + 1;
      const r = el('rect', { x: f(px), y: f(py), width: f(bw - 2), height: f(fh - 2), fill: WARM }, g);
      const gg = el('rect', { x: f(px - 0.6), y: f(py - 0.6), width: f(bw - 0.8), height: f(fh - 0.8), fill: WARM }, winGlow);
      const on = R() < (isFar ? 0.22 : 0.34);
      r.style.display = gg.style.display = on ? '' : 'none';
      r.setAttribute('opacity', isFar ? '0.55' : '0.9');
      idx.push(panes.length);
      panes.push({ r, g: gg, on, x: px + (bw - 2) / 2, tower: ti });
    }
    towerRefl.push({ n: el('path', { fill: 'none', stroke: WARM, 'stroke-width': 1.1, 'stroke-linecap': 'round', opacity: isFar ? 0.5 : 1 }, reflG), x, w, idx });
    if (h > 125) beacons.push({ n: el('circle', { cx: f(cx), cy: top - 10, r: 4, fill: 'url(#mj-red)' }, glow), ph: R(0, 2) });
  }

  // ---- 강물
  el('rect', { x: -5, y: BASE, width: W + 10, height: BANK - BASE + 3, fill: WATER }, scene);
  pen(scene, SP).setAttribute('d', `M-5 ${BASE} Q240 ${BASE + 0.8} 480 ${BASE} Q720 ${BASE - 0.8} ${W + 5} ${BASE}`);
  const ripples = Array.from({ length: 46 }, () => ({ x: R(0, W), y: R(BASE + 4, BANK - 3), l: R(5, 16), v: R(1.5, 4.5), n: pen(scene, SP * 0.55) }));
  ripples.forEach((r) => r.n.setAttribute('opacity', '0.45'));
  const moonRefl = el('path', { fill: 'none', stroke: '#f3ecd6', 'stroke-width': 0.9, 'stroke-linecap': 'round', opacity: 0.55 }, glow);

  // ---- 이쪽 강둑, 갈대, 난간, 산책로
  const bankG = el('g', {}, scene);
  const reedBack = el('g', {}, bankG);
  shape(bankG, SP).setAttribute('d', `M-5 ${BANK} Q120 ${BANK - 1.5} 260 ${BANK} Q420 ${BANK + 1.2} 600 ${BANK - 0.5} Q780 ${BANK - 1.5} ${W + 5} ${BANK} L${W + 5} ${H + 5} L-5 ${H + 5}Z`);
  // 강변 난간
  const rail: string[] = [`M-5 ${BANK - 6} Q480 ${BANK - 7} ${W + 5} ${BANK - 6}`];
  for (let x = 8; x < W; x += 28) rail.push(`M${x} ${BANK + 2} L${x + 0.3} ${BANK - 6.5}`);
  pen(bankG, SP * 0.8).setAttribute('d', rail.join(' '));
  pen(bankG, SP * 0.5).setAttribute('d', `M-5 ${BANK - 2.5} Q480 ${BANK - 3.5} ${W + 5} ${BANK - 2.5}`);
  pen(bankG, SP * 0.55).setAttribute('d', `M-5 ${GROUND + 4} Q300 ${GROUND + 5} 600 ${GROUND + 4} Q800 ${GROUND + 3.4} ${W + 5} ${GROUND + 4.4}`);
  const tufts: string[] = [];
  for (let i = 0; i < 40; i++) { const x = R(0, 590), y = R(GROUND + 8, H - 2); tufts.push(`M${f(x)} ${f(y)} q-1 -2 -1.6 -3.4 M${f(x + 1.4)} ${f(y)} q0.4 -2.4 1.2 -3.8`); }
  pen(bankG, SP * 0.5).setAttribute('d', tufts.join(' '));
  // 갈대: 난간 뒤 물가
  const reeds = Array.from({ length: 34 }, (_, i) => {
    const x = i < 20 ? R(430, 590) : R(640, 760);
    return { x, h: R(13, 24), lean: R(-0.15, 0.25), ph: R(0, 6.3), stem: pen(reedBack, SP * 0.7), plume: el('path', { fill: 'currentColor', opacity: 0.85 }, reedBack) };
  });
  const reedSwing = pendulum(6, 1.4);

  // ---- 사람 (산책로)
  const walkerG = el('g', { style: 'cursor:pointer' }, scene);
  el('title', {}, walkerG).textContent = '산책하는 사람 — 눌러 보세요';
  const farArm = limb(walkerG, 3.6);
  const legs = [limb(walkerG, 4.2), limb(walkerG, 4.2)];
  const shoes = [blot(walkerG), blot(walkerG)];
  const coat = shape(walkerG);
  const coatSeam = pen(walkerG, PEN * 0.6);
  const head = el('ellipse', { rx: 3.6, ry: 4.6, class: 'pp', fill: 'var(--paper)', stroke: 'currentColor', 'stroke-width': PEN }, walkerG);
  const cap = blot(walkerG);
  const scarf = paint(walkerG, '#9a3b2d', PEN * 0.8);
  const scarfTail = paint(walkerG, '#9a3b2d', PEN * 0.8);
  const nearArm = limb(walkerG, 3.6);

  // ---- 대파밭 (앞쪽)
  const field = el('g', {}, scene);
  const leeks: { g: SVGGElement; ph: number }[] = [];
  [[GROUND + 9, 0.8], [GROUND + 13.5, 0.92], [GROUND + 18.5, 1.05]].forEach(([y, s], row) => {
    for (let x = 606 + row * 4; x < W + 6; x += 10.5 * s) {
      const g = el('g', {}, field);
      const h = R(15, 20) * s;
      shape(g, SP * 0.7).setAttribute('d', `M-1 0 L-0.9 ${f(-h * 0.35)} L0.9 ${f(-h * 0.35)} L1 0Z`);
      const L = [[-5, 0.95], [-1.5, 1.08], [2.5, 1.0], [5.5, 0.82]].map(([dx, k]) => `M0 ${f(-h * 0.33)} Q${f(dx * 0.3)} ${f(-h * 0.7 * k)} ${f(dx)} ${f(-h * k)}`).join(' ');
      el('path', { d: L, fill: 'none', stroke: R() < 0.5 ? LEEK : LEEK_DARK, 'stroke-width': 1.6, 'stroke-linecap': 'round' }, g);
      pen(g, SP * 0.45).setAttribute('d', L);
      leeks.push({ g, ph: R(0, 6.3) });
      (g as any).__x = x + R(-1.5, 1.5); (g as any).__y = y;
    }
  });
  // 밭 팻말
  const sign = el('g', {}, scene);
  pen(sign, SP).setAttribute('d', `M596 ${H} L596 ${GROUND + 0.5}`);
  shape(sign, SP).setAttribute('d', `M578 ${GROUND - 13} L614 ${GROUND - 13.5} L614 ${GROUND - 1} L578 ${GROUND - 0.5}Z`);
  const st = el('text', { x: 596, y: GROUND - 4.4, 'text-anchor': 'middle', 'font-size': 7.2, fill: 'currentColor', 'font-weight': 700 }, sign);
  st.textContent = '명지 대파';

  // ---- 한 줄 안내
  const hint = el('text', { x: W / 2, y: 13, 'text-anchor': 'middle', 'font-size': 8, fill: INK, opacity: 0.55 }, top);
  hint.textContent = '부산 강서구 명지동 · 하늘을 누르면 별똥별이 떨어져요';

  // ---- 별똥별
  type Met = { x: number; y: number; dx: number; dy: number; len: number; life: number; t: number; segs: SVGPathElement[]; head: SVGCircleElement; col: string };
  const mets: Met[] = [];
  let lastMet: { x: number; y: number; until: number } | null = null;
  function shoot(x?: number, y?: number) {
    const a = rnd(22, 40) * Math.PI / 180, dir = Math.random() < 0.8 ? -1 : 1;
    const fire = Math.random() < 0.12;
    const col = fire ? '#d6ffe0' : '#fff6dc';
    const m: Met = { x: x ?? rnd(120, 900), y: y ?? rnd(8, 70), dx: dir * Math.cos(a), dy: Math.sin(a), len: fire ? rnd(120, 160) : rnd(60, 110), life: fire ? 1.6 : rnd(0.8, 1.25), t: 0, col,
      segs: [1.6, 1.0, 0.6].map((w, i) => el('path', { fill: 'none', stroke: col, 'stroke-width': fire ? w * 1.3 : w, 'stroke-linecap': 'round', opacity: [1, 0.5, 0.2][i] }, meteorG)),
      head: el('circle', { r: fire ? 9 : 5, fill: 'url(#mj-met)' }, glow) };
    mets.push(m);
    lastMet = { x: m.x + m.dx * 140, y: m.y + m.dy * 140, until: 0 };
    return m;
  }
  const toSvg = (e: PointerEvent): Vec => { const p = svg.createSVGPoint(); p.x = e.clientX; p.y = e.clientY; const q = p.matrixTransform(svg.getScreenCTM()!.inverse()); return [q.x, q.y]; };
  skyHit.addEventListener('pointerdown', (e) => { const [x, y] = toSvg(e); if (y < BASE) { shoot(x + 30, Math.max(4, y - 30)); look(); } });

  // ---- 사람 상태
  const walk = gait({ kind: 'walk' });
  const wind = pointerWind(svg, 0.3);
  const armSwing = [spring(60, 9), spring(60, 9)];
  const tail = spring(30, 4);
  const lookS = spring(14, 6);
  let phase = 0, wx = 300, dir: 1 | -1 = 1, lookT = -1;
  function look() { lookT = 0; }
  walkerG.addEventListener('pointerdown', (e) => {
    e.stopPropagation();
    const ahead = wx + dir * rnd(80, 200);
    shoot(clamp(ahead + 60, 60, W - 20), rnd(10, 50));
    look();
  });

  let nextMet = 2.5, nextFlick = 0, nextRefl = 0, nextPlane = 6, planeT = -1;

  run((t, dt) => {
    const wv = wind.step(t);
    // 별 반짝임
    for (let i = (Math.floor(t * 60) % 3); i < stars.length; i += 3) { const s = stars[i]; s.n.setAttribute('opacity', f(s.base * (0.6 + 0.4 * Math.sin(t * s.sp + s.ph)))); }

    // 별똥별
    if (t > nextMet) { shoot(); if (lookT < 0 && wx > 30 && wx < W - 30 && Math.random() < 0.7) look(); nextMet = t + every * rnd(0.4, 1.6); }
    for (let i = mets.length - 1; i >= 0; i--) {
      const m = mets[i]; m.t += dt;
      const u = m.t / m.life, d = m.len * 1.6 * ease(Math.min(1, u)), hx = m.x + m.dx * d, hy = m.y + m.dy * d;
      const tl = m.len * Math.min(1, u * 2.2) * (1 - smooth(0.75, 1, u));
      m.segs.forEach((s, k) => {
        const a0 = tl * k / 3, a1 = tl * (k + 1) / 3;
        s.setAttribute('d', `M${f(hx - m.dx * a0)} ${f(hy - m.dy * a0)} L${f(hx - m.dx * a1)} ${f(hy - m.dy * a1)}`);
      });
      const op = Math.sin(Math.PI * clamp(u, 0, 1));
      meteorGOpacity(m, op);
      m.head.setAttribute('cx', f(hx)); m.head.setAttribute('cy', f(hy)); m.head.setAttribute('opacity', f(op));
      if (u >= 1) { m.segs.forEach((s) => s.remove()); m.head.remove(); mets.splice(i, 1); }
    }

    // 창문: 가끔 하나씩 켜지고 꺼짐
    if (t > nextFlick) {
      const p = panes[Math.floor(Math.random() * panes.length)];
      p.on = !p.on; p.r.style.display = p.g.style.display = p.on ? '' : 'none';
      nextFlick = t + rnd(0.2, 0.9);
    }
    beacons.forEach((b) => b.n.setAttribute('opacity', ((t + b.ph) % 2) < 0.9 ? '1' : '0.08'));

    // 강물 반영
    ripples.forEach((r) => { r.x += r.v * dt * (1 + wv * 0.4); if (r.x > W + 20) r.x = -20; r.n.setAttribute('d', `M${f(r.x)} ${f(r.y)} q${f(r.l / 2)} -0.7 ${f(r.l)} 0`); });
    if (t > nextRefl) {
      nextRefl = t + 0.14;
      towerRefl.forEach((tr) => {
        const cols = new Map<number, number>();
        tr.idx.forEach((k) => { const p = panes[k]; if (p.on) cols.set(Math.round(p.x), (cols.get(Math.round(p.x)) ?? 0) + 1); });
        const d: string[] = [];
        cols.forEach((n, x) => { for (let y = BASE + 3; y < BANK - 2; y += 3.2) if (Math.random() < Math.min(0.85, n * 0.11) * (1 - (y - BASE) / 34)) { const l = rnd(1.5, 4.5); d.push(`M${f(x - l / 2 + rnd(-1, 1))} ${f(y)} l${f(l)} 0`); } });
        tr.n.setAttribute('d', d.join(' '));
      });
      const md: string[] = [];
      for (let y = BASE + 3; y < BANK - 2; y += 3) { const l = rnd(4, 12) * (1 - (y - BASE) / 40); md.push(`M${f(MOON[0] - l / 2 + rnd(-2, 2))} ${f(y)} l${f(l)} 0`); }
      moonRefl.setAttribute('d', md.join(' '));
    }

    // 갈대와 대파: 바람
    const sw = reedSwing.step(wv * 1.8, dt);
    reeds.forEach((r) => {
      const b = (r.lean + sw * 0.35 + 0.08 * Math.sin(t * 1.7 + r.ph)) * r.h;
      const tx = r.x + b, ty = BANK - 1 - r.h + Math.abs(b) * 0.2;
      r.stem.setAttribute('d', `M${f(r.x)} ${BANK - 1} Q${f(r.x + b * 0.2)} ${f(BANK - 1 - r.h * 0.6)} ${f(tx)} ${f(ty)}`);
      const ang = Math.atan2(ty - (BANK - 1 - r.h * 0.6), tx - (r.x + b * 0.2));
      const c = Math.cos(ang), s = Math.sin(ang), Lp = 6.5;
      r.plume.setAttribute('d', `M${f(tx)} ${f(ty)} Q${f(tx + c * Lp * 0.5 - s * 1.6)} ${f(ty + s * Lp * 0.5 + c * 1.6)} ${f(tx + c * Lp)} ${f(ty + s * Lp)} Q${f(tx + c * Lp * 0.5 + s * 1.1)} ${f(ty + s * Lp * 0.5 - c * 1.1)} ${f(tx)} ${f(ty)}Z`);
    });
    leeks.forEach((l) => { const a = (sw * 4 + Math.sin(t * 1.3 + l.ph) * 1.4); l.g.setAttribute('transform', `translate(${f((l.g as any).__x)} ${f((l.g as any).__y)}) skewX(${f(a)})`); });

    // 비행기: 왼쪽 위에서 오른쪽 아래(공항 쪽)로
    if (planeT < 0 && t > nextPlane) planeT = 0;
    if (planeT >= 0) {
      planeT += dt;
      const u = planeT / 42, px = -30 + (W + 70) * u, py = 26 + 70 * u * u;
      planeG.setAttribute('transform', `translate(${f(px)} ${f(py)}) rotate(${f(5 + 6 * u)}) scale(0.9)`);
      planeG.style.display = '';
      planeRed.setAttribute('cx', f(px - 2)); planeRed.setAttribute('cy', f(py + 4)); planeRed.setAttribute('opacity', (planeT % 1.2) < 0.5 ? '1' : '0.1');
      planeWhite.setAttribute('cx', f(px - 10)); planeWhite.setAttribute('cy', f(py - 1)); planeWhite.setAttribute('opacity', (planeT % 1.6) < 0.08 ? '1' : '0');
      planeLand.setAttribute('cx', f(px + 11)); planeLand.setAttribute('cy', f(py + 1)); planeLand.setAttribute('opacity', f(0.5 + 0.5 * u));
      if (u > 1) { planeT = -1; nextPlane = t + rnd(25, 45); }
    } else { planeG.style.display = 'none'; [planeRed, planeWhite, planeLand].forEach((n) => n.setAttribute('opacity', '0')); }

    // 사람: 걷다가 별똥별을 보면 멈춰서 가리킴
    let lk = 0;
    if (lookT >= 0) { lookT += dt; lk = lookT < 0.6 ? ease(lookT / 0.6) : lookT < 2.8 ? 1 : 1 - ease((lookT - 2.8) / 0.7); if (lookT > 3.5) lookT = -1; }
    const L = lookS.step(lk, dt), go = clamp(1 - L * 1.05, 0, 1);
    phase += (dt / walk.period) * go;
    wx += dir * walk.speed * S * dt * go;
    if (wx > W + 40) dir = -1; else if (wx < -40) dir = 1;
    place(walkerG, wx, GROUND, dir, S);
    const p = walk.pose(phase, go), b = p.bob;
    p.feet.forEach((fo, i) => { legs[i].draw([p.hip, fo.knee, fo.ankle], [0.3, 0.8]); shoe(shoes[i], fo.ankle, fo.pitch); });
    walkerG.insertBefore(legs[p.front].g, coat); walkerG.insertBefore(shoes[p.front], coat);
    const kF = p.feet[p.front].knee, aF = p.feet[p.front].ankle;
    const sh: Vec = [41, 41 + b], hemY = 80;
    const fx = Math.max(kF[0] + 2.4, 46.4);
    coat.setAttribute('d', `M${f(sh[0] - 6)} ${f(sh[1] + 1)} Q${f(sh[0] - 1)} ${f(sh[1] - 2.4)} ${f(sh[0] + 5)} ${f(sh[1] + 1)} L${f(Math.min(fx, 48) - 0.6)} ${f(70 + b)} Q${f(Math.min(fx, 48))} ${f(76 + b * 0.5)} ${f(Math.min(Math.max(fx, aF[0] - 4), 49))} ${hemY} L31.4 ${hemY + 1} L33.2 ${f(70 + b)}Z`);
    coatSeam.setAttribute('d', `M${f(sh[0] + 2.6)} ${f(sh[1] + 4)} L${f(sh[0] + 3.6)} ${f(hemY - 1 + b * 0.3)}`);
    // 고개를 들면 머리가 살짝 뒤로, 모자 챙이 위로
    const hc: Vec = [42.6 - 1.2 * L, 31.6 + b - 0.4 * L];
    head.setAttribute('cx', f(hc[0])); head.setAttribute('cy', f(hc[1]));
    cap.setAttribute('d', capPath(hc, -32 * L));
    scarf.setAttribute('d', `M${f(hc[0] - 4.6)} ${f(hc[1] + 4.6)} Q${f(hc[0])} ${f(hc[1] + 8.4)} ${f(hc[0] + 4)} ${f(hc[1] + 4.8)} L${f(hc[0] + 4.4)} ${f(hc[1] + 7.6)} Q${f(hc[0])} ${f(hc[1] + 11)} ${f(hc[0] - 4.8)} ${f(hc[1] + 7.4)}Z`);
    const flow = tail.step(-5 - walk.speed * 0.07 * go - wv * 4 * dir + Math.sin(t * 7) * 0.6, dt);
    scarfTail.setAttribute('d', `M${f(hc[0] - 3.6)} ${f(hc[1] + 6)} Q${f(hc[0] - 6 + flow * 0.4)} ${f(hc[1] + 9)} ${f(hc[0] - 4 + flow)} ${f(hc[1] + 15 + flow * 0.2)} L${f(hc[0] - 1 + flow * 0.9)} ${f(hc[1] + 15.6 + flow * 0.2)} Q${f(hc[0] - 3 + flow * 0.3)} ${f(hc[1] + 10)} ${f(hc[0] - 0.8)} ${f(hc[1] + 7.4)}Z`);
    const legSwing = (p.feet[0].ankle[0] - 40) / (walk.stride / 2);
    const farA = armSwing[0].step(-legSwing * 15 * go, dt) * Math.PI / 180;
    const nearA = armSwing[1].step(legSwing * 13 * go, dt) * Math.PI / 180;
    const shF: Vec = [sh[0] - 1, sh[1] + 2], shN: Vec = [sh[0] + 1.6, sh[1] + 2.4];
    const elbF: Vec = [shF[0] + 17 * Math.sin(farA), shF[1] + 17 * Math.cos(farA)];
    farArm.draw([shF, elbF, [elbF[0] + 16 * Math.sin(farA + 0.25), elbF[1] + 16 * Math.cos(farA + 0.25)]], [0.2, 0.5]);
    // 가까운 팔: 평소엔 흔들고, 올려다볼 땐 별똥별 쪽을 가리킴
    const elbW: Vec = [shN[0] + 17 * Math.sin(nearA), shN[1] + 17 * Math.cos(nearA)];
    const handW: Vec = [elbW[0] + 16 * Math.sin(nearA + 0.1), elbW[1] + 16 * Math.cos(nearA + 0.1)];
    let tx = 1, ty = -1.3;
    if (lastMet) { tx = 40 + dir * ((lastMet as any).x - wx) / S - shN[0]; ty = 120 + ((lastMet as any).y - GROUND) / S - shN[1]; }
    const tl = Math.hypot(tx, ty) || 1; tx /= tl; ty /= tl; if (ty > -0.35) { ty = -0.35; tx = Math.sign(tx || 1) * 0.94; }
    const handP: Vec = [shN[0] + tx * 31, shN[1] + ty * 31];
    const elbP: Vec = [shN[0] + tx * 15.5 + 2, shN[1] + ty * 15.5 + 2.5];
    const mix = (a: Vec, c: Vec): Vec => [a[0] + (c[0] - a[0]) * L, a[1] + (c[1] - a[1]) * L];
    nearArm.draw([shN, mix(elbW, elbP), mix(handW, handP)], [0.2, 0.4]);
  });

  function meteorGOpacity(m: Met, op: number) { m.segs[0].parentNode && m.segs.forEach((s, k) => s.setAttribute('opacity', f(op * [1, 0.5, 0.2][k]))); }
  function capPath(hc: Vec, deg: number): string {
    const r = deg * Math.PI / 180, c = Math.cos(r), s = Math.sin(r);
    const P = (x: number, y: number) => pt([hc[0] + x * c - y * s, hc[1] + x * s + y * c]);
    return `M${P(-4, -1.4)} Q${P(-4.2, -6.4)} ${P(0, -6.4)} Q${P(4, -6.2)} ${P(4, -1.6)} L${P(8, -1.2)} Q${P(8, 0)} ${P(6.5, 0)} L${P(-4, -0.4)}Z`;
  }
}
