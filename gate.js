// Процедурная отрисовка ворот+калитки из досок металлического сайдинга (SVG).
// scene(STATE) -> строка <svg>. Доски, блик, фактура рисуются программно и
// перекрашиваются в выбранный цвет; кирпичные столбы — в тон дома.

// профили досок: стоп-точки градиента (позиция, цвет, прозрачность) поперёк доски
const PROFILE = {
  brus: [[0,'#fff',.22],[.10,'#fff',.05],[.5,'#000',0],[.84,'#000',.05],[1,'#000',.28]],
  log:  [[0,'#000',.22],[.07,'#000',.05],[.24,'#fff',.36],[.5,'#fff',.06],[.8,'#000',.08],[1,'#000',.34]],
  ship: [[0,'#fff',.20],[.07,'#fff',.03],[.46,'#000',0],[.5,'#000',.22],[.56,'#fff',.12],[.9,'#000',.05],[1,'#000',.26]],
  vert: [[0,'#fff',.22],[.10,'#fff',.05],[.5,'#000',0],[.84,'#000',.05],[1,'#000',.28]],
};
const PLANK_PX = {brus:36, log:30, ship:30, vert:42}; // целевая ширина доски

const BRICK_TONES = {
  beige:{brick:'#e8ddc6', mortar:'#cabda3', accent:'#b06a4f', edge:'#d8ccb0'},
  terra:{brick:'#b15f46', mortar:'#cdb49e', accent:'#8d4632', edge:'#9d5238'},
  sand: {brick:'#d8bf89', mortar:'#bfa479', accent:'#b8975a', edge:'#c8ad73'},
};

function lin(id, stops, vertical){
  const c = vertical ? 'x1="0" y1="0" x2="1" y2="0"' : 'x1="0" y1="0" x2="0" y2="1"';
  const s = stops.map(([o,col,a])=>`<stop offset="${o}" stop-color="${col}" stop-opacity="${a}"/>`).join('');
  return `<linearGradient id="${id}" ${c}>${s}</linearGradient>`;
}

// набор досок внутри прямоугольника (x,y,w,h)
function planks(x,y,w,h,type,orient,gradId){
  const vert = orient==='v';
  const span = vert ? w : h;
  const n = Math.max(3, Math.round(span / PLANK_PX[type]));
  const pt = span / n;
  let out = '';
  for(let i=0;i<n;i++){
    const px = vert ? x + i*pt : x;
    const py = vert ? y : y + i*pt;
    const pw = vert ? pt : w;
    const ph = vert ? h : pt;
    out += `<rect x="${px}" y="${py}" width="${pw}" height="${ph}" fill="url(#${gradId})"/>`;
    // шов между досками
    if(i>0){
      if(vert) out += `<rect x="${px-0.6}" y="${y}" width="1.2" height="${h}" fill="#000" opacity=".30"/>`;
      else     out += `<rect x="${x}" y="${py-0.6}" width="${w}" height="1.2" fill="#000" opacity=".30"/>`;
    }
  }
  return out;
}

// одна панель: рама + заполнение сайдингом
function panel(id, x, y, w, h, st){
  const fw = 13;                       // ширина рамы
  const ix=x+fw, iy=y+fw, iw=w-2*fw, ih=h-2*fw;
  const clip = `clip-${id}`;
  const gid = `grad-${id}`;
  let inner = `<rect x="${ix}" y="${iy}" width="${iw}" height="${ih}" fill="${st.hex}"/>`;
  inner += planks(ix,iy,iw,ih, st.type, st.orient, gid);
  if(st.finish==='глянец')
    inner += `<rect x="${ix}" y="${iy}" width="${iw}" height="${ih}" fill="url(#gloss)"/>`;
  if(st.finish==='дерево')
    inner += `<rect x="${ix}" y="${iy}" width="${iw}" height="${ih}" fill="#3a2a1d" opacity=".22" filter="url(#${st.orient==='v'?'woodV':'woodH'})"/>`;
  // лёгкое затемнение к краям панели (объём)
  inner += `<rect x="${ix}" y="${iy}" width="${iw}" height="${ih}" fill="url(#vign)"/>`;
  return `
    <defs>
      ${lin(gid, PROFILE[st.type], st.orient==='v')}
      <clipPath id="${clip}"><rect x="${ix}" y="${iy}" width="${iw}" height="${ih}"/></clipPath>
    </defs>
    <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="3" fill="#eceae3"/>
    <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="3" fill="url(#frame)"/>
    <g clip-path="url(#${clip})">${inner}</g>
    <rect x="${ix}" y="${iy}" width="${iw}" height="${ih}" fill="none" stroke="#000" stroke-opacity=".18"/>`;
}

// кирпичный столб с зубчатым верхом
function pier(x,y,w,h,br){
  const cap = sawtooth(x-3,y, w+6, 12, '#9c5b41');
  return `
    <rect x="${x}" y="${y+10}" width="${w}" height="${h-10}" fill="url(#brick-${br})"/>
    <rect x="${x}" y="${y+10}" width="${w}" height="${h-10}" fill="url(#pierShade)"/>
    <rect x="${x}" y="${y+10}" width="${w}" height="${h-10}" fill="none" stroke="#000" stroke-opacity=".12"/>
    ${cap}`;
}
function sawtooth(x,y,w,h,color){
  const teeth=Math.round(w/14); const tw=w/teeth; let d=`M${x} ${y+h}`;
  for(let i=0;i<teeth;i++){ d+=`L${x+i*tw+tw/2} ${y} L${x+(i+1)*tw} ${y+h}`; }
  return `<rect x="${x}" y="${y+h-2}" width="${w}" height="6" fill="${color}"/>
          <path d="${d}Z" fill="${color}"/>`;
}

function brickPattern(id, c){
  // плитка 64x36, два ряда со смещением
  const b=(bx,by,col)=>`<rect x="${bx}" y="${by}" width="28" height="13" rx="2" fill="${col}"/>`;
  return `<pattern id="brick-${id}" width="64" height="36" patternUnits="userSpaceOnUse">
    <rect width="64" height="36" fill="${c.mortar}"/>
    ${b(2,3,c.brick)}${b(34,3,c.accent)}
    ${b(-14,20,c.brick)}${b(18,20,c.brick)}${b(50,20,c.brick)}
    <rect width="64" height="36" fill="none" stroke="${c.edge}" stroke-opacity=".0"/>
  </pattern>`;
}

function defsGlobal(st){
  const b=BRICK_TONES[st.brick];
  return `<defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#dfe6ea"/><stop offset="1" stop-color="#eef1f0"/>
    </linearGradient>
    <linearGradient id="frame" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#fff" stop-opacity=".55"/>
      <stop offset=".5" stop-color="#fff" stop-opacity="0"/>
      <stop offset="1" stop-color="#000" stop-opacity=".18"/>
    </linearGradient>
    <linearGradient id="gloss" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#fff" stop-opacity="0"/>
      <stop offset=".4" stop-color="#fff" stop-opacity=".16"/>
      <stop offset=".5" stop-color="#fff" stop-opacity=".02"/>
      <stop offset="1" stop-color="#fff" stop-opacity="0"/>
    </linearGradient>
    <radialGradient id="vign" cx=".5" cy=".5" r=".75">
      <stop offset=".6" stop-color="#000" stop-opacity="0"/>
      <stop offset="1" stop-color="#000" stop-opacity=".16"/>
    </radialGradient>
    <linearGradient id="pierShade" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#fff" stop-opacity=".18"/>
      <stop offset=".5" stop-color="#000" stop-opacity="0"/>
      <stop offset="1" stop-color="#000" stop-opacity=".22"/>
    </linearGradient>
    <linearGradient id="ground" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#c8c5bd"/><stop offset="1" stop-color="#b4b1a8"/>
    </linearGradient>
    <filter id="woodH"><feTurbulence type="fractalNoise" baseFrequency="0.015 0.55" numOctaves="2" seed="7" result="n"/>
      <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1.3 -0.35"/></filter>
    <filter id="woodV"><feTurbulence type="fractalNoise" baseFrequency="0.55 0.015" numOctaves="2" seed="7" result="n"/>
      <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1.3 -0.35"/></filter>
    <filter id="soft"><feDropShadow dx="0" dy="6" stdDeviation="8" flood-opacity=".25"/></filter>
    ${brickPattern(st.brick, b)}
  </defs>`;
}

function scene(st){
  const W=1000,H=600, gy=545;
  // раскладка
  const top=150, bot=gy, ph=bot-top;
  const pierTop=78, pierH=bot-pierTop;
  let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" role="img">`;
  s += defsGlobal(st);
  // фон и земля
  s += `<rect width="${W}" height="${H}" fill="url(#sky)"/>`;
  s += `<rect y="${gy}" width="${W}" height="${H-gy}" fill="url(#ground)"/>`;
  s += `<rect y="${gy}" width="${W}" height="3" fill="#000" opacity=".10"/>`;
  // тени на земле
  s += `<ellipse cx="500" cy="${gy+8}" rx="430" ry="14" fill="#000" opacity=".12"/>`;
  // столбы
  s += pier(20, pierTop, 50, pierH, st.brick);     // левый
  s += pier(300, pierTop, 52, pierH, st.brick);    // средний
  s += pier(952, pierTop, 50, pierH, st.brick);    // правый
  // калитка (левая): петли на левом краю, ручка справа
  s += `<g filter="url(#soft)">` + panel('wk', 78, top, 214, ph, st) + `</g>`;
  s += hinges(84, top, ph) + handle(292-20, top+ph/2);
  // ворота — две створки
  s += `<g filter="url(#soft)">` + panel('gA', 360, top, 300, ph, st) + `</g>`;
  s += `<g filter="url(#soft)">` + panel('gB', 660, top, 300, ph, st) + `</g>`;
  // петли по краям, центральный стык, ручки створок
  s += hinges(366, top, ph) + hinges(954, top, ph);
  s += `<rect x="658" y="${top}" width="4" height="${ph}" fill="#000" opacity=".18"/>`;
  s += handle(648, top+ph/2) + handle(672, top+ph/2);
  s += `</svg>`;
  return s;
}
// две петли на вертикальном крае панели с центром по x
function hinges(x, top, h){
  const y1=top+h*0.16, y2=top+h*0.80;
  return `<rect x="${x-10}" y="${y1}" width="20" height="15" rx="2" fill="#2b2b2b"/>
          <rect x="${x-10}" y="${y2}" width="20" height="15" rx="2" fill="#2b2b2b"/>`;
}
function handle(x,y){
  return `<rect x="${x}" y="${y-15}" width="7" height="30" rx="3" fill="#1f1f1f"/>`;
}
