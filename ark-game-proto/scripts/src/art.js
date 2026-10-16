/* art — 雛型美術：全部程式產生的 SVG（之後美術出圖只換這一層；名稱 = 規格書符號代碼）
 * SlotArt.svg(name) → SVG 字串；SlotArt.load(PIXI, size) → { name: Texture }
 */
(function (root) {
  'use strict';
  const FONT = "'Noto Serif CJK TC','Noto Serif TC','PMingLiU','Songti TC',serif";
  const wrap = (body, defs) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200"><defs>${defs || ''}</defs>${body}</svg>`;
  const goldGrad = (id) => `<linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff3b0"/><stop offset=".45" stop-color="#f5c542"/><stop offset="1" stop-color="#b9770e"/></linearGradient>`;
  const frame = (c1, c2, id) => `<radialGradient id="${id}" cx=".5" cy=".38" r=".7"><stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></radialGradient>`;
  const plate = (id, gid) => `<rect x="8" y="8" width="184" height="184" rx="30" fill="url(#${id})" stroke="url(#${gid})" stroke-width="7"/>`;

  const S = {};
  // M1 彌勒佛（笑臉）
  S.M1 = wrap(`${plate('bgM1', 'gM1')}
    <circle cx="100" cy="104" r="62" fill="url(#skin)" stroke="#a0522d" stroke-width="3"/>
    <path d="M52 78 Q100 20 148 78" fill="none" stroke="#7a3b10" stroke-width="5" stroke-linecap="round" opacity=".35"/>
    <path d="M70 92 Q80 82 90 92" fill="none" stroke="#5a2a0a" stroke-width="5" stroke-linecap="round"/>
    <path d="M110 92 Q120 82 130 92" fill="none" stroke="#5a2a0a" stroke-width="5" stroke-linecap="round"/>
    <ellipse cx="66" cy="112" rx="10" ry="6" fill="#ff8a7a" opacity=".55"/><ellipse cx="134" cy="112" rx="10" ry="6" fill="#ff8a7a" opacity=".55"/>
    <path d="M70 118 Q100 156 130 118 Q100 132 70 118Z" fill="#8b1a1a" stroke="#5a2a0a" stroke-width="3" stroke-linejoin="round"/>
    <path d="M80 124 Q100 132 120 124 L118 128 Q100 136 82 128Z" fill="#fff"/>
    <ellipse cx="100" cy="106" rx="6" ry="4" fill="#d9894a"/>
    <circle cx="40" cy="104" r="12" fill="url(#skin)" stroke="#a0522d" stroke-width="3"/><circle cx="160" cy="104" r="12" fill="url(#skin)" stroke="#a0522d" stroke-width="3"/>`,
    frame('#d0302a', '#5c0b0b', 'bgM1') + goldGrad('gM1') + `<radialGradient id="skin" cx=".45" cy=".35" r=".75"><stop offset="0" stop-color="#ffe2b8"/><stop offset="1" stop-color="#e8a25e"/></radialGradient>`);
  // M2 金元寶
  S.M2 = wrap(`${plate('bgM2', 'gM2')}
    <path d="M30 104 Q34 150 100 156 Q166 150 170 104 Q140 124 100 124 Q60 124 30 104Z" fill="url(#gM2b)" stroke="#8a5a06" stroke-width="4"/>
    <ellipse cx="100" cy="102" rx="44" ry="34" fill="url(#gM2b)" stroke="#8a5a06" stroke-width="4"/>
    <path d="M26 100 Q60 86 72 104 M174 100 Q140 86 128 104" stroke="#8a5a06" stroke-width="4" fill="url(#gM2b)"/>
    <ellipse cx="88" cy="88" rx="14" ry="8" fill="#fff8d0" opacity=".8"/>
    <text x="100" y="186" font-family="${FONT}" font-size="22" text-anchor="middle" fill="#ffe9a0" font-weight="700">元寶</text>`,
    frame('#2f6b4f', '#0b2a1d', 'bgM2') + goldGrad('gM2') + goldGrad('gM2b'));
  // M3 福袋
  S.M3 = wrap(`${plate('bgM3', 'gM3')}
    <path d="M62 66 Q100 52 138 66 L126 78 Q100 70 74 78Z" fill="#c0392b" stroke="#6e1a12" stroke-width="3"/>
    <path d="M74 78 Q34 110 50 150 Q100 176 150 150 Q166 110 126 78Z" fill="url(#bag)" stroke="#6e1a12" stroke-width="4"/>
    <path d="M70 80 Q100 92 130 80" stroke="url(#gM3)" stroke-width="8" fill="none" stroke-linecap="round"/>
    <circle cx="100" cy="124" r="26" fill="url(#gM3)" stroke="#8a5a06" stroke-width="3"/>
    <text x="100" y="134" font-family="${FONT}" font-size="30" text-anchor="middle" fill="#8b1a1a" font-weight="900">福</text>`,
    frame('#384a8f', '#0d1438', 'bgM3') + goldGrad('gM3') + `<radialGradient id="bag" cx=".4" cy=".35" r=".8"><stop offset="0" stop-color="#ff6b5b"/><stop offset="1" stop-color="#9b1b12"/></radialGradient>`);
  // M4 仙桃
  S.M4 = wrap(`${plate('bgM4', 'gM4')}
    <path d="M100 60 C60 50 36 96 52 128 C66 158 96 166 100 168 C104 166 134 158 148 128 C164 96 140 50 100 60Z" fill="url(#peach)" stroke="#9e3b4a" stroke-width="4"/>
    <path d="M100 64 Q92 110 100 166" stroke="#c44d63" stroke-width="3" fill="none" opacity=".6"/>
    <path d="M100 62 Q76 36 50 50 Q72 70 100 62Z" fill="#3e8e41" stroke="#1d4d20" stroke-width="3"/>
    <path d="M100 62 Q126 32 152 46 Q128 70 100 62Z" fill="#4caf50" stroke="#1d4d20" stroke-width="3"/>
    <ellipse cx="78" cy="96" rx="12" ry="18" fill="#fff" opacity=".35"/>`,
    frame('#6b3f8f', '#1f0b33', 'bgM4') + goldGrad('gM4') + `<radialGradient id="peach" cx=".4" cy=".3" r=".8"><stop offset="0" stop-color="#ffe0e6"/><stop offset=".5" stop-color="#ff8fa3"/><stop offset="1" stop-color="#d9435f"/></radialGradient>`);
  // M5 葫蘆
  S.M5 = wrap(`${plate('bgM5', 'gM5')}
    <circle cx="100" cy="132" r="38" fill="url(#gourd)" stroke="#7a4b0a" stroke-width="4"/>
    <circle cx="100" cy="82" r="26" fill="url(#gourd)" stroke="#7a4b0a" stroke-width="4"/>
    <rect x="88" y="98" width="24" height="10" rx="4" fill="#c0392b"/>
    <rect x="94" y="46" width="12" height="14" rx="3" fill="#6d4c2a"/>
    <path d="M112 100 Q134 112 128 140" stroke="#c0392b" stroke-width="4" fill="none"/>
    <ellipse cx="86" cy="120" rx="9" ry="14" fill="#fff" opacity=".35"/>`,
    frame('#1f6f8b', '#06232e', 'bgM5') + goldGrad('gM5') + `<radialGradient id="gourd" cx=".4" cy=".3" r=".8"><stop offset="0" stop-color="#ffe9a8"/><stop offset="1" stop-color="#d08a1a"/></radialGradient>`);
  // FA / FK / FQ：牌面字
  const card = (ch, c1, c2) => wrap(`<rect x="22" y="22" width="156" height="156" rx="26" fill="url(#c${ch})" stroke="#f5d27a" stroke-width="4" opacity=".95"/>
    <text x="100" y="140" font-family="Georgia,'Times New Roman',serif" font-size="112" font-weight="700" text-anchor="middle" fill="url(#t${ch})" stroke="#2a1a05" stroke-width="3">${ch}</text>`,
    `<linearGradient id="c${ch}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></linearGradient>` +
    `<linearGradient id="t${ch}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#f5c542"/></linearGradient>`);
  S.FA = card('A', '#2e7d5b', '#0e3326');
  S.FK = card('K', '#2b5aa8', '#0c1f45');
  S.FQ = card('Q', '#8e3b8e', '#2e0f33');
  // WW：百搭玉牌
  S.WW = wrap(`<rect x="10" y="10" width="180" height="180" rx="28" fill="url(#jade)" stroke="url(#gW)" stroke-width="8"/>
    <text x="100" y="104" font-family="${FONT}" font-size="64" font-weight="900" text-anchor="middle" fill="url(#gW)" stroke="#20402a" stroke-width="2">百搭</text>
    <text x="100" y="156" font-family="Georgia,serif" font-size="38" font-weight="700" text-anchor="middle" fill="#fff6c8" letter-spacing="4">WILD</text>`,
    goldGrad('gW') + `<radialGradient id="jade" cx=".5" cy=".35" r=".8"><stop offset="0" stop-color="#9ff0c4"/><stop offset=".55" stop-color="#2fa36b"/><stop offset="1" stop-color="#0d4a2c"/></radialGradient>`);
  // SC：金幣（分數由 Pixi 疊字）
  S.SC = wrap(`<circle cx="100" cy="100" r="86" fill="url(#gSC)" stroke="#8a5a06" stroke-width="6"/>
    <circle cx="100" cy="100" r="66" fill="none" stroke="#fff3b0" stroke-width="4" opacity=".7"/>
    <rect x="82" y="82" width="36" height="36" rx="3" fill="#7a4a04" stroke="#fff3b0" stroke-width="3" opacity=".9"/>
    <ellipse cx="72" cy="66" rx="20" ry="10" fill="#fff" opacity=".45" transform="rotate(-30 72 66)"/>`,
    goldGrad('gSC'));
  // SS：彩珠
  S.SS = wrap(`<circle cx="100" cy="100" r="84" fill="url(#rb)" stroke="#fff" stroke-width="5"/>
    <circle cx="100" cy="100" r="84" fill="url(#shine)"/>
    <ellipse cx="74" cy="64" rx="26" ry="14" fill="#fff" opacity=".7" transform="rotate(-30 74 64)"/>`,
    `<linearGradient id="rb" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff5f6d"/><stop offset=".25" stop-color="#ffc371"/><stop offset=".5" stop-color="#47e891"/><stop offset=".75" stop-color="#4facfe"/><stop offset="1" stop-color="#b06ab3"/></linearGradient>` +
    `<radialGradient id="shine" cx=".35" cy=".3" r=".7"><stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>`);
  // FG 物件
  S.coin = S.SC;
  S.carp = wrap(`<path d="M30 100 Q70 50 130 80 L170 56 L162 100 L170 144 L130 120 Q70 150 30 100Z" fill="url(#fish)" stroke="#7a2a05" stroke-width="4"/>
    <circle cx="58" cy="94" r="7" fill="#1a0a00"/><circle cx="56" cy="92" r="2" fill="#fff"/>
    <path d="M80 82 Q90 100 80 118 M100 80 Q110 100 100 120 M120 84 Q128 100 120 116" stroke="#ffd29a" stroke-width="3" fill="none" opacity=".8"/>`,
    `<linearGradient id="fish" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffb347"/><stop offset="1" stop-color="#e2461b"/></linearGradient>`);
  const dragon = (id, g) => wrap(`<path d="M40 150 C20 110 60 90 90 110 C120 130 150 110 140 80 C132 56 104 56 100 74" fill="none" stroke="url(#${id})" stroke-width="24" stroke-linecap="round"/>
    <path d="M40 150 C20 110 60 90 90 110 C120 130 150 110 140 80 C132 56 104 56 100 74" fill="none" stroke="#3a2205" stroke-width="2" stroke-dasharray="6 8" opacity=".6"/>
    <circle cx="104" cy="66" r="24" fill="url(#${id})" stroke="#3a2205" stroke-width="4"/>
    <path d="M92 46 L84 24 L100 40 M116 46 L124 24 L110 40" stroke="url(#${id})" stroke-width="6" fill="none" stroke-linecap="round"/>
    <circle cx="96" cy="62" r="5" fill="#c00"/><circle cx="114" cy="62" r="5" fill="#c00"/>
    <path d="M90 80 Q104 90 120 78" stroke="#3a2205" stroke-width="4" fill="none"/>
    <path d="M86 78 Q60 74 54 60 M122 78 Q150 76 158 62" stroke="#3a2205" stroke-width="3" fill="none"/>`, g);
  S.gold = dragon('dg', goldGrad('dg'));
  S.color = dragon('dc', `<linearGradient id="dc" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff5f6d"/><stop offset=".33" stop-color="#ffc371"/><stop offset=".66" stop-color="#47e891"/><stop offset="1" stop-color="#4facfe"/></linearGradient>`);


  // ───── Tiger and Dragon 套（通用造型，不仿原廠美術）─────
  const TD = {};
  const tile = (id, c1, c2, body, defs) => wrap(`<rect x="10" y="10" width="180" height="180" rx="28" fill="url(#${id})" stroke="url(#g${id})" stroke-width="7"/>${body}`,
    `<radialGradient id="${id}" cx=".5" cy=".38" r=".75"><stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></radialGradient>` + goldGrad('g' + id) + (defs || ''));
  TD.M1 = tile('t1', '#3f8f6b', '#0d2a1f', `<ellipse cx="100" cy="110" rx="64" ry="48" fill="#6fbf73" stroke="#1d4d20" stroke-width="4"/>
    <path d="M70 92 L100 76 L130 92 L130 124 L100 140 L70 124Z" fill="#a5d6a7" stroke="#1d4d20" stroke-width="3"/>
    <circle cx="160" cy="100" r="16" fill="#8bc34a" stroke="#1d4d20" stroke-width="3"/><circle cx="165" cy="96" r="3" fill="#000"/>
    <ellipse cx="60" cy="150" rx="12" ry="8" fill="#8bc34a"/><ellipse cx="140" cy="150" rx="12" ry="8" fill="#8bc34a"/>`);
  TD.M2 = tile('t2', '#2a5aa8', '#0c1f45', `<path d="M30 100 Q70 50 130 80 L170 56 L162 100 L170 144 L130 120 Q70 150 30 100Z" fill="#ff7043" stroke="#7a2a05" stroke-width="4"/>
    <circle cx="58" cy="94" r="7" fill="#1a0a00"/><path d="M84 86 Q96 100 84 114 M104 84 Q116 100 104 118" stroke="#fff" stroke-width="3" fill="none" opacity=".7"/>`);
  TD.M3 = tile('t3', '#7a4b1e', '#2a1505', `<circle cx="100" cy="100" r="62" fill="#c98b3a" stroke="#5a3209" stroke-width="5"/>
    <rect x="82" y="82" width="36" height="36" fill="#2a1505" stroke="#f2c47a" stroke-width="3"/>
    <text x="100" y="62" font-family="${FONT}" font-size="22" text-anchor="middle" fill="#5a3209" font-weight="900">通</text><text x="100" y="152" font-family="${FONT}" font-size="22" text-anchor="middle" fill="#5a3209" font-weight="900">寶</text>`);
  TD.M4 = tile('t4', '#8e2b2b', '#2e0909', `<path d="M40 104 Q100 96 160 104 L146 156 Q100 170 54 156Z" fill="#c0392b" stroke="#5a0f0f" stroke-width="4"/>
    <ellipse cx="100" cy="104" rx="60" ry="12" fill="#e74c3c" stroke="#5a0f0f" stroke-width="3"/>
    <circle cx="80" cy="92" r="14" fill="url(#gt4)"/><circle cx="104" cy="84" r="16" fill="url(#gt4)"/><circle cx="126" cy="94" r="12" fill="url(#gt4)"/>`);
  TD.M5 = tile('t5', '#4c3f8f', '#140d38', `<circle cx="100" cy="104" r="56" fill="#7fe0c0" stroke="#1d6b55" stroke-width="5"/><circle cx="100" cy="104" r="20" fill="#140d38"/>
    <path d="M100 30 L100 48" stroke="#c0392b" stroke-width="6"/><ellipse cx="80" cy="84" rx="14" ry="8" fill="#fff" opacity=".5"/>`);
  TD.M6 = tile('t6', '#8f6b1f', '#2e1f05', `<path d="M100 160 L30 80 A100 100 0 0 1 170 80Z" fill="#f5e6c4" stroke="#7a4b0a" stroke-width="4"/>
    <path d="M100 160 L52 66 M100 160 L76 56 M100 160 L100 52 M100 160 L124 56 M100 160 L148 66" stroke="#b07a2a" stroke-width="3"/>
    <circle cx="100" cy="160" r="8" fill="#7a4b0a"/>`);
  TD.A = card('A', '#2e7d5b', '#0e3326'); TD.K = card('K', '#2b5aa8', '#0c1f45'); TD.Q = card('Q', '#8e3b8e', '#2e0f33'); TD.J = card('J', '#9a5a12', '#331c03');
  const gong = (id, label, sub) => wrap(`<circle cx="100" cy="100" r="84" fill="url(#${id})" stroke="#5a3209" stroke-width="6"/>
    <circle cx="100" cy="100" r="66" fill="none" stroke="#fff3b0" stroke-width="4" opacity=".6"/>
    <text x="100" y="${sub ? 92 : 112}" font-family="Georgia,serif" font-size="${sub ? 40 : 34}" font-weight="900" text-anchor="middle" fill="#fff" stroke="#3a1a00" stroke-width="2">${label}</text>
    ${sub ? `<text x="100" y="140" font-family="${FONT}" font-size="22" font-weight="900" text-anchor="middle" fill="#fff6c8">${sub}</text>` : ''}`,
    `<radialGradient id="${id}" cx=".4" cy=".35" r=".8"><stop offset="0" stop-color="#ffe9a0"/><stop offset=".6" stop-color="#e0a030"/><stop offset="1" stop-color="#8a5a06"/></radialGradient>`);
  TD.WILD = gong('gw', 'WILD', '');
  TD.MY = gong('gm', '?', '銅鑼');
  TD.SC_T = tile('tt', '#ff9800', '#7a2e00', `<text x="100" y="134" font-family="${FONT}" font-size="104" font-weight="900" text-anchor="middle" fill="#fff3e0" stroke="#3a1400" stroke-width="5">虎</text>`);
  TD.SC_D = tile('td', '#26a69a', '#00332c', `<text x="100" y="134" font-family="${FONT}" font-size="104" font-weight="900" text-anchor="middle" fill="#e0f2f1" stroke="#00221d" stroke-width="5">龍</text>`);
  TD.COIN = S.SC;
  TD.ARROW = wrap(`<circle cx="100" cy="100" r="84" fill="#1e63c8" stroke="#bfe0ff" stroke-width="6"/><path d="M60 100 L130 100 M110 74 L140 100 L110 126" stroke="#fff" stroke-width="16" stroke-linecap="round" stroke-linejoin="round" fill="none"/>`);
  // ───── 吉屋出豬 three-pigs 套（房子收集主題；程式產生 SVG 佔位，不仿原廠美術）─────
  const TP = {};
  const tpTile = (id, c1, c2, body, defs) => wrap(`<rect x="10" y="10" width="180" height="180" rx="28" fill="url(#${id})" stroke="url(#g${id})" stroke-width="7"/>${body}`,
    `<radialGradient id="${id}" cx=".5" cy=".38" r=".75"><stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></radialGradient>` + goldGrad('g' + id) + (defs || ''));
  // 三隻小豬（H1 粉 / H2 金 / H3 紅）：圓臉 + 豬鼻 + 耳朵
  const pig = (id, c1, c2) => tpTile(id, c1, c2, `<ellipse cx="64" cy="70" rx="20" ry="24" fill="#ffc0cb" stroke="#9b5b63" stroke-width="3"/><ellipse cx="136" cy="70" rx="20" ry="24" fill="#ffc0cb" stroke="#9b5b63" stroke-width="3"/>
    <circle cx="100" cy="108" r="56" fill="#ffd1dc" stroke="#9b5b63" stroke-width="4"/>
    <ellipse cx="100" cy="118" rx="30" ry="22" fill="#ffb0c4" stroke="#9b5b63" stroke-width="3"/>
    <ellipse cx="90" cy="118" rx="6" ry="9" fill="#6b2a35"/><ellipse cx="110" cy="118" rx="6" ry="9" fill="#6b2a35"/>
    <circle cx="80" cy="94" r="6" fill="#2a1015"/><circle cx="120" cy="94" r="6" fill="#2a1015"/>`);
  TP.H1 = pig('p1', '#d0507a', '#5c0b2b');
  TP.H2 = pig('p2', '#e0a030', '#5a3a06');
  TP.H3 = pig('p3', '#d0302a', '#5c0b0b');
  // M1 磚屋 / M2 木屋（中獎圖騰）
  TP.M1 = tpTile('m1', '#b85c3a', '#4a1e0e', `<path d="M100 50 L160 96 L140 96 L140 156 L60 156 L60 96 L40 96Z" fill="#c8745a" stroke="#4a1e0e" stroke-width="4"/>
    <rect x="60" y="96" width="80" height="60" fill="none" stroke="#4a1e0e" stroke-width="2"/>
    <path d="M60 110 H140 M60 124 H140 M60 138 H140 M86 96 V156 M114 96 V156" stroke="#8a4a30" stroke-width="2"/>
    <rect x="88" y="128" width="24" height="28" fill="#5a2a16"/>`);
  TP.M2 = tpTile('m2', '#8a6a3a', '#3a2a10', `<path d="M100 52 L158 98 L138 98 L138 156 L62 156 L62 98 L42 98Z" fill="#c9a05a" stroke="#3a2a10" stroke-width="4"/>
    <path d="M62 98 H138 M62 118 H138 M62 138 H138" stroke="#6a4a1a" stroke-width="3"/>
    <rect x="86" y="126" width="28" height="30" fill="#4a3012"/>`);
  // L1-L6 低賠（撲克字牌，草屋色系）
  TP.L1 = card('A', '#2e7d5b', '#0e3326'); TP.L2 = card('K', '#2b5aa8', '#0c1f45');
  TP.L3 = card('Q', '#8e3b8e', '#2e0f33'); TP.L4 = card('J', '#9a5a12', '#331c03');
  TP.L5 = card('10', '#3a7d7d', '#0e3030'); TP.L6 = card('9', '#7d3a5a', '#300e1f');
  // WILD 百搭
  TP.WILD = wrap(`<rect x="10" y="10" width="180" height="180" rx="28" fill="url(#tpjade)" stroke="url(#gtw)" stroke-width="8"/>
    <text x="100" y="104" font-family="${FONT}" font-size="60" font-weight="900" text-anchor="middle" fill="url(#gtw)" stroke="#20402a" stroke-width="2">百搭</text>
    <text x="100" y="154" font-family="Georgia,serif" font-size="34" font-weight="700" text-anchor="middle" fill="#fff6c8" letter-spacing="4">WILD</text>`,
    goldGrad('gtw') + `<radialGradient id="tpjade" cx=".5" cy=".35" r=".8"><stop offset="0" stop-color="#9ff0c4"/><stop offset=".55" stop-color="#2fa36b"/><stop offset="1" stop-color="#0d4a2c"/></radialGradient>`);
  // SC 房框 scatter（收集符號 = 房子地基 / 加分星）
  TP.SC = wrap(`<circle cx="100" cy="100" r="84" fill="url(#gtsc)" stroke="#8a5a06" stroke-width="6"/>
    <path d="M100 54 L116 90 L156 94 L126 120 L134 160 L100 138 L66 160 L74 120 L44 94 L84 90Z" fill="#fff3b0" stroke="#8a5a06" stroke-width="3"/>
    <text x="100" y="112" font-family="${FONT}" font-size="30" font-weight="900" text-anchor="middle" fill="#8a5a06">框</text>`,
    `<radialGradient id="gtsc" cx=".4" cy=".35" r=".8"><stop offset="0" stop-color="#ffe9a0"/><stop offset="1" stop-color="#d08a1a"/></radialGradient>`);
  // BS 大轉盤 bonus
  TP.BS = wrap(`<circle cx="100" cy="100" r="84" fill="url(#gtbs)" stroke="#5a0b0b" stroke-width="6"/>
    <g stroke="#fff" stroke-width="3" opacity=".8"><path d="M100 20 V100 M100 100 L156 44 M100 100 H180 M100 100 L156 156 M100 100 V180 M100 100 L44 156 M100 100 H20 M100 100 L44 44"/></g>
    <circle cx="100" cy="100" r="20" fill="#ffd36b" stroke="#5a0b0b" stroke-width="3"/>
    <text x="100" y="192" font-family="${FONT}" font-size="20" font-weight="900" text-anchor="middle" fill="#ffd36b">轉盤</text>`,
    `<radialGradient id="gtbs" cx=".4" cy=".35" r=".8"><stop offset="0" stop-color="#ff6b5b"/><stop offset="1" stop-color="#8a1010"/></radialGradient>`);
  // MY1 / MY2 神秘圖騰
  const myTile = (id, label, c1, c2) => wrap(`<rect x="10" y="10" width="180" height="180" rx="28" fill="url(#${id})" stroke="#f5d27a" stroke-width="7"/>
    <text x="100" y="128" font-family="${FONT}" font-size="92" font-weight="900" text-anchor="middle" fill="#fff" stroke="#2a1a05" stroke-width="3">${label}</text>`,
    `<radialGradient id="${id}" cx=".4" cy=".35" r=".8"><stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></radialGradient>`);
  TP.MY1 = myTile('my1', '?', '#6b3f8f', '#1f0b33');
  TP.MY2 = myTile('my2', '?', '#1f6f8b', '#06232e');

  const SETS = { milefo: S, tiger_dragon: TD, three_pigs: TP };

  // 背景（廟宇紅金 + 雲紋）
  function background(w, h) {
    let clouds = '';
    for (let i = 0; i < 14; i++) {
      const x = (i * 197) % w, y = 40 + ((i * 131) % (h - 80)), s = 0.6 + (i % 4) * 0.25;
      clouds += `<g transform="translate(${x} ${y}) scale(${s})" opacity=".08" fill="none" stroke="#ffd36b" stroke-width="5"><path d="M0 0 q20 -30 40 0 q20 -30 40 0 q-10 20 -40 14 q-30 6 -40 -14z"/><path d="M14 -2 q10 -12 20 0"/></g>`;
    }
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}"><defs>
      <radialGradient id="bg" cx=".5" cy=".35" r=".9"><stop offset="0" stop-color="#7a1414"/><stop offset=".6" stop-color="#3d0808"/><stop offset="1" stop-color="#160202"/></radialGradient></defs>
      <rect width="${w}" height="${h}" fill="url(#bg)"/>${clouds}</svg>`;
  }

  function toTexture(PIXI, svg, size) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        const c = document.createElement('canvas');
        c.width = size; c.height = size * (img.height / img.width);
        c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
        resolve(PIXI.Texture.from(c));
      };
      img.onerror = reject;
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    });
  }
  async function load(PIXI, size, bg, set) {
    const out = {}, src = SETS[set] || S;
    await Promise.all(Object.keys(src).map(async (k) => { out[k] = await toTexture(PIXI, src[k], size); }));
    if (bg) out.__bg = await toTexture(PIXI, background(bg[0], bg[1]), bg[0]);
    return out;
  }
  root.SlotArt = { svg: (n, set) => (SETS[set] || S)[n], names: (set) => Object.keys(SETS[set] || S), sets: Object.keys(SETS), load, background };
})(typeof self !== 'undefined' ? self : globalThis);
