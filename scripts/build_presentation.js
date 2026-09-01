#!/usr/bin/env node

"use strict";

const fs = require("node:fs");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const W = 1280;
const H = 720;

const C = {
  ink: "#0B0D14",
  ink2: "#151927",
  paper: "#F4F0E6",
  paper2: "#E9E3D5",
  white: "#FFFFFF",
  gray: "#9DA5B4",
  gray2: "#626B7A",
  blue: "#315BFF",
  blue2: "#7E9BFF",
  red: "#F04452",
  yellow: "#F4C842",
  mint: "#55D6A9",
  cyan: "#66D9EF",
  orange: "#FF9F43",
  board: "#2452D6",
  hole: "#111626",
};

const FONT_DISPLAY = "Bahnschrift";
const FONT_BODY = "Segoe UI";
const FONT_MONO = "Consolas";

const NONE_FILL = { type: "none" };
const NONE_LINE = { style: "solid", fill: NONE_FILL, width: 0 };

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const item = argv[i];
    if (!item.startsWith("--")) {
      throw new Error(`Argomento inatteso: ${item}`);
    }
    const key = item.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      args[key] = true;
    } else {
      args[key] = next;
      i += 1;
    }
  }
  return args;
}

function artifactToolEntry() {
  const candidates = [
    process.env.ARTIFACT_TOOL_ENTRY,
    path.join(
      process.env.CODEX_NODE_MODULES || "",
      "@oai",
      "artifact-tool",
      "dist",
      "artifact_tool.mjs",
    ),
    path.join(
      os.homedir(),
      ".cache",
      "codex-runtimes",
      "codex-primary-runtime",
      "dependencies",
      "node",
      "node_modules",
      "@oai",
      "artifact-tool",
      "dist",
      "artifact_tool.mjs",
    ),
  ].filter(Boolean);

  const found = candidates.find((candidate) => fs.existsSync(candidate));
  if (!found) {
    throw new Error(
      "Runtime @oai/artifact-tool non trovato. Impostare ARTIFACT_TOOL_ENTRY " +
        "o eseguire lo script nell'ambiente Codex desktop.",
    );
  }
  return found;
}

function rect(slide, x, y, w, h, fill, options = {}) {
  const shape = slide.shapes.add({
    geometry: options.geometry || "rect",
    position: { left: x, top: y, width: w, height: h },
    fill: fill ? { type: "solid", color: fill } : NONE_FILL,
    line:
      options.lineColor && options.lineWidth !== 0
        ? {
            style: options.dashed ? "dashed" : "solid",
            fill: options.lineColor,
            width: options.lineWidth || 1,
          }
        : NONE_LINE,
  });
  if (options.name) shape.name = options.name;
  if (options.rotation) shape.position.rotation = options.rotation;
  if (options.radius !== undefined) shape.borderRadius = options.radius;
  return shape;
}

function text(slide, value, x, y, w, h, options = {}) {
  const shape = rect(slide, x, y, w, h, null, {
    geometry: "rect",
    name: options.name,
  });
  shape.text = String(value);
  shape.text.typeface = options.font || FONT_BODY;
  shape.text.fontSize = options.size || 24;
  shape.text.color = options.color || C.ink;
  shape.text.bold = Boolean(options.bold);
  shape.text.italic = Boolean(options.italic);
  shape.text.alignment = options.align || "left";
  shape.text.verticalAlignment = options.valign || "top";
  shape.text.wrap = "square";
  shape.text.autoFit = options.autoFit || "shrinkText";
  shape.text.insets = {
    left: options.padX ?? 0,
    right: options.padX ?? 0,
    top: options.padY ?? 0,
    bottom: options.padY ?? 0,
  };
  if (options.rotation) shape.position.rotation = options.rotation;
  return shape;
}

function line(slide, x, y, w, h, color, options = {}) {
  return rect(slide, x, y, w, h, color, {
    geometry: options.geometry || "rect",
    rotation: options.rotation,
    name: options.name,
  });
}

function circle(slide, x, y, d, fill, options = {}) {
  return rect(slide, x, y, d, d, fill, {
    geometry: "ellipse",
    lineColor: options.lineColor,
    lineWidth: options.lineWidth,
    name: options.name,
  });
}

function connect(slide, from, to, options = {}) {
  return slide.shapes.connect(from, to, {
    kind: options.kind || "straight",
    fromSide: options.fromSide || "right",
    toSide: options.toSide || "left",
    line: {
      style: options.dashed ? "dashed" : "solid",
      fill: options.color || C.blue,
      width: options.width || 3,
    },
    tail: options.arrow === false ? undefined : { type: "arrow", width: "med", length: "med" },
  });
}

function labelPill(slide, label, x, y, w, fill, color = C.white) {
  const box = rect(slide, x, y, w, 30, fill, { geometry: "roundRect" });
  box.text = label;
  box.text.typeface = FONT_DISPLAY;
  box.text.fontSize = 14;
  box.text.bold = true;
  box.text.color = color;
  box.text.alignment = "center";
  box.text.verticalAlignment = "middle";
  box.text.insets = { left: 8, right: 8, top: 2, bottom: 2 };
  return box;
}

function kicker(slide, label, dark = false, index = "") {
  const marker = circle(slide, 58, 43, 10, C.yellow, {
    name: `kicker-${index || "main"}-marker`,
  });
  const kickerText = text(slide, label.toUpperCase(), 76, 34, 300, 28, {
    font: FONT_DISPLAY,
    size: 14,
    bold: true,
    color: dark ? C.paper : C.gray2,
    valign: "middle",
    name: `kicker-${index || "main"}-label`,
  });
  return { marker, kickerText };
}

function title(slide, claim, options = {}) {
  kicker(slide, options.kicker || "PEFFORZA 4", options.dark);
  return text(slide, claim, 56, 78, options.width || 1160, options.height || 92, {
    font: FONT_DISPLAY,
    size: options.size || 43,
    bold: true,
    color: options.dark ? C.white : C.ink,
    valign: "middle",
  });
}

function footer(slide, page, source, dark = false) {
  line(slide, 56, 681, 1168, 1, dark ? "#2B3142" : "#D3CCBE");
  text(slide, source, 58, 688, 1010, 18, {
    size: 10,
    color: dark ? C.gray : C.gray2,
    valign: "middle",
  });
  text(slide, String(page).padStart(2, "0"), 1166, 686, 56, 20, {
    font: FONT_DISPLAY,
    size: 12,
    bold: true,
    color: dark ? C.yellow : C.blue,
    align: "right",
    valign: "middle",
  });
}

function metric(slide, value, label, x, y, w, options = {}) {
  text(slide, value, x, y, w, 52, {
    font: FONT_DISPLAY,
    size: options.size || 40,
    bold: true,
    color: options.color || C.blue,
    align: options.align || "left",
    valign: "middle",
  });
  text(slide, label, x, y + 54, w, 26, {
    size: 15,
    color: options.labelColor || C.gray2,
    align: options.align || "left",
  });
}

function board(slide, x, y, width, grid, options = {}) {
  const height = (width * 6) / 7;
  const panel = rect(slide, x, y, width, height, options.panel || C.board, {
    geometry: "roundRect",
    lineColor: options.lineColor,
    lineWidth: options.lineWidth || 0,
    name: options.name || "connect4-board",
  });
  const gap = width * 0.025;
  const cellW = (width - gap * 8) / 7;
  const cellH = (height - gap * 7) / 6;
  const d = Math.min(cellW, cellH) * 0.78;
  for (let r = 0; r < 6; r += 1) {
    for (let c = 0; c < 7; c += 1) {
      const cx = x + gap + c * (cellW + gap) + (cellW - d) / 2;
      const cy = y + gap + r * (cellH + gap) + (cellH - d) / 2;
      const cell = grid?.[r]?.[c] || 0;
      const fill = cell === 1 ? C.red : cell === 2 ? C.yellow : options.hole || C.hole;
      circle(slide, cx, cy, d, fill);
    }
  }
  return panel;
}

function miniBoardGrid() {
  return [
    [0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 2, 0, 0, 0],
    [0, 0, 1, 1, 0, 0, 0],
    [0, 2, 2, 1, 0, 0, 0],
    [1, 2, 1, 2, 1, 0, 0],
  ];
}

function sourceBox(slide, label, x, y, w, h, fill, options = {}) {
  const box = rect(slide, x, y, w, h, fill, {
    geometry: "roundRect",
    lineColor: options.lineColor,
    lineWidth: options.lineWidth || 0,
    name: options.name,
  });
  box.text = label;
  box.text.typeface = options.font || FONT_DISPLAY;
  box.text.fontSize = options.size || 20;
  box.text.bold = options.bold !== false;
  box.text.color = options.color || C.white;
  box.text.alignment = options.align || "center";
  box.text.verticalAlignment = "middle";
  box.text.insets = { left: 16, right: 16, top: 12, bottom: 12 };
  return box;
}

function addNotes(slide, notes) {
  slide.speakerNotes.text = notes.trim();
}

function slide01(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = { type: "solid", color: C.ink };

  line(slide, 0, 0, W, 10, C.yellow);
  labelPill(slide, "AI + COMPUTER VISION + AR", 58, 54, 246, C.blue);
  text(slide, "PEFFORZA 4", 56, 126, 660, 92, {
    font: FONT_DISPLAY,
    size: 72,
    bold: true,
    color: C.white,
    valign: "middle",
  });
  text(slide, "Una scacchiera fisica diventa\nun sistema intelligente.", 58, 224, 620, 142, {
    font: FONT_DISPLAY,
    size: 42,
    bold: true,
    color: C.paper,
  });
  text(
    slide,
    "Reinforcement learning, minimax, OpenCV, realta aumentata e voce in un unico progetto.",
    60,
    382,
    560,
    72,
    { size: 21, color: C.gray },
  );

  const heroGrid = [
    [0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 2, 0, 0, 0],
    [0, 0, 2, 1, 0, 0, 0],
    [0, 2, 1, 1, 2, 0, 0],
    [1, 2, 1, 2, 1, 1, 0],
  ];
  board(slide, 782, 148, 410, heroGrid, { panel: C.board, hole: "#0A0E18" });
  const arrow = rect(slide, 932, 66, 88, 82, C.yellow, { geometry: "downArrow" });
  arrow.name = "ar-recommendation-arrow";
  labelPill(slide, "COLONNA 4", 920, 42, 112, C.red);

  metric(slide, "3", "modalita di gioco", 58, 532, 150, {
    color: C.yellow,
    labelColor: C.gray,
  });
  metric(slide, "5", "livelli di difficolta", 238, 532, 180, {
    color: C.mint,
    labelColor: C.gray,
  });
  metric(slide, "108", "test automatizzati", 448, 532, 180, {
    color: C.blue2,
    labelColor: C.gray,
  });

  text(slide, "Project presentation", 58, 654, 300, 24, {
    size: 12,
    color: C.gray2,
  });
  text(slide, "Versione 0.2.0", 1050, 654, 170, 24, {
    size: 12,
    color: C.gray2,
    align: "right",
  });

  addNotes(
    slide,
    `
Pefforza 4 e un progetto completo di intelligenza artificiale applicata al gioco del Forza 4.
La caratteristica distintiva e il collegamento tra una scacchiera fisica, una webcam, un motore decisionale e un feedback AR/vocale.
Durante la presentazione mostro sia il risultato finale sia l'evoluzione: dal primo PPO alla robustezza ottenuta con minimax, test e diagnostica.
`,
  );
  return slide;
}

function slide02(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = { type: "solid", color: C.paper };
  title(slide, "Il problema non e scegliere una colonna.\nE mantenere coerenti quattro mondi.", {
    kicker: "LA SFIDA",
    size: 42,
    height: 104,
  });

  const nodes = [
    { x: 62, label: "REALTA\nFISICA", fill: C.red, sub: "luce + prospettiva" },
    { x: 350, label: "PERCEZIONE\nVISIVA", fill: C.blue, sub: "pixel -> 42 celle" },
    { x: 638, label: "REGOLE\nE IA", fill: C.ink2, sub: "stato -> decisione" },
    { x: 926, label: "FEEDBACK\nUTENTE", fill: C.yellow, color: C.ink, sub: "AR + voce + GUI" },
  ];
  const shapes = nodes.map((node, index) => {
    circle(slide, node.x + 94, 214, 40, index === 3 ? C.ink : C.paper);
    text(slide, String(index + 1), node.x + 94, 214, 40, 40, {
      font: FONT_DISPLAY,
      size: 18,
      bold: true,
      color: index === 3 ? C.yellow : node.fill,
      align: "center",
      valign: "middle",
    });
    const shape = sourceBox(slide, node.label, node.x, 272, 230, 116, node.fill, {
      color: node.color || C.white,
      size: 23,
      name: `challenge-node-${index + 1}`,
    });
    text(slide, node.sub, node.x, 404, 230, 34, {
      size: 16,
      color: C.gray2,
      align: "center",
    });
    return shape;
  });
  for (let i = 0; i < shapes.length - 1; i += 1) {
    connect(slide, shapes[i], shapes[i + 1], {
      color: i === 2 ? C.orange : C.blue2,
      width: 3,
    });
  }

  const risks = [
    ["Rumore", "ombre, riflessi, camera spostata"],
    ["Latenza", "ricerca profonda senza bloccare l'interfaccia"],
    ["Credibilita", "mai ignorare una vittoria o un blocco immediato"],
  ];
  risks.forEach((risk, i) => {
    const x = 72 + i * 398;
    line(slide, x, 505, 54, 5, [C.red, C.blue, C.yellow][i]);
    text(slide, risk[0], x, 521, 140, 28, {
      font: FONT_DISPLAY,
      size: 19,
      bold: true,
      color: C.ink,
    });
    text(slide, risk[1], x, 553, 336, 55, {
      size: 16,
      color: C.gray2,
    });
  });

  footer(slide, 2, "Fonte: architettura e casi limite ricavati dal codice del repository.");
  addNotes(
    slide,
    `
In digitale il tabellone e gia una matrice; nel mondo reale bisogna prima ricostruirla da un'immagine rumorosa.
Ogni passaggio ha convenzioni diverse: colori fisici, ID dei giocatori, coordinate della camera e colonne dell'agente.
La scelta progettuale fondamentale e stata separare i quattro mondi, definendo contratti semplici e testabili tra un modulo e l'altro.
`,
  );
  return slide;
}

function slide03(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = { type: "solid", color: C.ink };
  title(slide, "In cinque mesi: da demo monolitica\na sistema installabile e verificato.", {
    kicker: "EVOLUZIONE",
    dark: true,
    size: 42,
    height: 104,
  });

  line(slide, 94, 342, 1092, 4, "#343B50");
  const points = [
    {
      x: 118,
      date: "10 DIC 2025",
      title: "Primo prototipo",
      body: "PPO + webcam + TTS\n577 righe iniziali",
      color: C.red,
    },
    {
      x: 356,
      date: "17 DIC 2025",
      title: "Board fisico",
      body: "Calibrazione, token HSV,\nnotebook e checkpoint",
      color: C.yellow,
    },
    {
      x: 594,
      date: "19 MAG 2026",
      title: "Engineering reset",
      body: "Package, rules pure,\nCI e 28 test",
      color: C.blue2,
    },
    {
      x: 832,
      date: "19 MAG 2026",
      title: "IA ibrida",
      body: "5 difficolta, minimax,\nsafety net e watchdog",
      color: C.mint,
    },
    {
      x: 1070,
      date: "25 MAG 2026",
      title: "Vision robusta",
      body: "Diagnostica live,\ncorner sorting e 108 test",
      color: C.orange,
    },
  ];

  points.forEach((point, i) => {
    const above = i % 2 === 0;
    circle(slide, point.x, 326, 34, point.color, { lineColor: C.ink, lineWidth: 4 });
    text(slide, point.date, point.x - 54, above ? 212 : 402, 142, 25, {
      font: FONT_DISPLAY,
      size: 13,
      bold: true,
      color: point.color,
      align: "center",
    });
    text(slide, point.title, point.x - 84, above ? 244 : 434, 202, 34, {
      font: FONT_DISPLAY,
      size: 21,
      bold: true,
      color: C.white,
      align: "center",
    });
    text(slide, point.body, point.x - 98, above ? 282 : 474, 230, 60, {
      size: 15,
      color: C.gray,
      align: "center",
    });
    line(slide, point.x + 15, above ? 310 : 362, 3, 18, point.color);
  });

  text(slide, "36 commit su main", 58, 594, 260, 36, {
    font: FONT_DISPLAY,
    size: 25,
    bold: true,
    color: C.yellow,
  });
  text(
    slide,
    "La cronologia racconta una progressione: prima farlo funzionare, poi renderlo forte, infine renderlo verificabile.",
    330,
    586,
    860,
    52,
    { size: 19, color: C.paper },
  );

  footer(slide, 3, "Fonte: git log e statistiche dei commit 4cd278b - 50fa04f.", true);
  addNotes(
    slide,
    `
Il primo commit conteneva gia l'idea completa, ma in forma di prototipo.
La seconda fase ha portato la partita sul board reale e ha aggiunto i notebook di training e debug.
La svolta di maggio e ingegneristica: package installabile, regole condivise, CI, minimax, watchdog, test headless della vision e tool di diagnosi.
`,
  );
  return slide;
}

function slide04(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = { type: "solid", color: C.paper };
  title(slide, "Un solo motore supporta tre esperienze\ne cinque livelli di sfida.", {
    kicker: "PRODOTTO",
    size: 40,
    height: 100,
  });

  const cardY = 212;
  const cardW = 344;
  const cardH = 294;
  const xs = [58, 468, 878];

  // CLI mockup.
  rect(slide, xs[0], cardY, cardW, cardH, C.ink, { geometry: "roundRect" });
  labelPill(slide, "CLI", xs[0] + 20, cardY + 18, 58, C.red);
  text(slide, "1 2 3 4 5 6 7", xs[0] + 30, cardY + 75, 280, 30, {
    font: FONT_MONO,
    size: 18,
    color: C.gray,
    align: "center",
  });
  text(
    slide,
    "| . . . . . . . |\n| . . . O . . . |\n| . . X X . . . |\n| O O X O X . . |",
    xs[0] + 42,
    cardY + 112,
    260,
    112,
    { font: FONT_MONO, size: 18, color: C.paper, align: "center" },
  );
  text(slide, "AI chose column 4  (0.32s)", xs[0] + 24, cardY + 246, 296, 28, {
    font: FONT_MONO,
    size: 13,
    color: C.mint,
    align: "center",
  });

  // GUI mockup.
  rect(slide, xs[1], cardY, cardW, cardH, C.ink2, { geometry: "roundRect" });
  labelPill(slide, "PYGAME", xs[1] + 20, cardY + 18, 84, C.blue);
  text(slide, "Difficulty: hard  -  AI thinking...", xs[1] + 18, cardY + 62, 308, 26, {
    size: 13,
    color: C.gray,
    align: "center",
  });
  board(slide, xs[1] + 68, cardY + 98, 208, miniBoardGrid(), {
    panel: C.board,
    hole: C.ink,
  });
  circle(slide, xs[1] + 150, cardY + 90, 24, C.yellow);

  // AR mockup.
  rect(slide, xs[2], cardY, cardW, cardH, "#DCE5F3", { geometry: "roundRect" });
  labelPill(slide, "AR FISICA", xs[2] + 20, cardY + 18, 94, C.yellow, C.ink);
  rect(slide, xs[2] + 24, cardY + 62, 296, 188, "#AEBFD2", {
    lineColor: C.white,
    lineWidth: 4,
  });
  board(slide, xs[2] + 82, cardY + 88, 180, miniBoardGrid(), {
    panel: "#3F68D4",
    hole: "#C8D5E7",
  });
  rect(slide, xs[2] + 150, cardY + 45, 48, 52, C.red, { geometry: "downArrow" });
  text(slide, "AI recommends: 4", xs[2] + 60, cardY + 253, 226, 26, {
    font: FONT_DISPLAY,
    size: 16,
    bold: true,
    color: C.ink,
    align: "center",
  });

  const tiers = [
    ["easy", "random", C.gray2],
    ["medium", "1-ply", C.mint],
    ["hard", "minimax d5", C.blue],
    ["impossible", "iterative", C.red],
    ["neural", "PPO", C.yellow],
  ];
  tiers.forEach((tier, i) => {
    const x = 58 + i * 233;
    rect(slide, x, 552, 210, 70, i === 4 ? C.ink : C.paper2, {
      geometry: "roundRect",
      lineColor: tier[2],
      lineWidth: 2,
    });
    text(slide, tier[0], x + 14, 562, 182, 25, {
      font: FONT_DISPLAY,
      size: 17,
      bold: true,
      color: i === 4 ? C.yellow : C.ink,
      align: "center",
    });
    text(slide, tier[1], x + 14, 589, 182, 20, {
      size: 13,
      color: i === 4 ? C.gray : C.gray2,
      align: "center",
    });
  });

  footer(slide, 4, "Fonte: play_cli.py, play_gui.py, play_physical.py e difficulty.py.");
  addNotes(
    slide,
    `
Le tre interfacce servono scopi diversi: la CLI e rapida e trasparente, la GUI rende il gioco piacevole, la modalita AR dimostra l'integrazione fisica.
Il registro delle difficolta espone lo stesso tipo di funzione a tutte le interfacce.
Neural non e sinonimo di piu forte: e la modalita sperimentale che usa il checkpoint PPO; hard e impossible usano ricerca classica.
`,
  );
  return slide;
}

function slide05(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = { type: "solid", color: C.ink };
  title(slide, "Training e runtime restano separati,\nma parlano la stessa lingua.", {
    kicker: "ARCHITETTURA",
    dark: true,
    size: 41,
    height: 102,
  });

  text(slide, "RUNTIME FISICO", 60, 197, 220, 26, {
    font: FONT_DISPLAY,
    size: 15,
    bold: true,
    color: C.yellow,
  });
  line(slide, 60, 228, 1160, 1, "#30364A");

  const runtimeNodes = [
    sourceBox(slide, "WEBCAM\nBGR frame", 62, 263, 166, 86, C.ink2, {
      lineColor: C.red,
      lineWidth: 2,
      size: 18,
      name: "arch-webcam",
    }),
    sourceBox(slide, "BoardDetector\nwarp + HSV", 278, 263, 190, 86, C.blue, {
      size: 18,
      name: "arch-detector",
    }),
    sourceBox(slide, "GRID 6x7\n0 / 1 / 2", 518, 263, 166, 86, C.paper, {
      color: C.ink,
      size: 18,
      name: "arch-grid",
    }),
    sourceBox(slide, "Agent registry\nminimax / PPO", 734, 263, 196, 86, C.ink2, {
      lineColor: C.mint,
      lineWidth: 2,
      size: 18,
      name: "arch-agent",
    }),
    sourceBox(slide, "AR + VOCE\nmossa utente", 980, 263, 190, 86, C.yellow, {
      color: C.ink,
      size: 18,
      name: "arch-output",
    }),
  ];
  for (let i = 0; i < runtimeNodes.length - 1; i += 1) {
    connect(slide, runtimeNodes[i], runtimeNodes[i + 1], {
      color: i === 1 ? C.yellow : C.blue2,
      width: 3,
    });
  }

  text(slide, "TRAINING", 60, 410, 220, 26, {
    font: FONT_DISPLAY,
    size: 15,
    bold: true,
    color: C.mint,
  });
  line(slide, 60, 441, 1160, 1, "#30364A");
  const trainNodes = [
    sourceBox(slide, "Connect4Env\nregole + reward", 132, 480, 206, 90, C.ink2, {
      lineColor: C.blue,
      lineWidth: 2,
      size: 18,
      name: "arch-env",
    }),
    sourceBox(slide, "SinglePlayerWrapper\navversario casuale", 410, 480, 230, 90, C.ink2, {
      lineColor: C.yellow,
      lineWidth: 2,
      size: 18,
      name: "arch-wrapper",
    }),
    sourceBox(slide, "PPO\naggiorna la policy", 712, 480, 196, 90, C.blue, {
      size: 18,
      name: "arch-ppo",
    }),
    sourceBox(slide, "CHECKPOINT\nnotebook_model.zip", 980, 480, 202, 90, C.paper, {
      color: C.ink,
      size: 18,
      name: "arch-checkpoint",
    }),
  ];
  for (let i = 0; i < trainNodes.length - 1; i += 1) {
    connect(slide, trainNodes[i], trainNodes[i + 1], {
      color: C.mint,
      width: 3,
    });
  }
  connect(slide, trainNodes[3], runtimeNodes[3], {
    kind: "elbow",
    fromSide: "top",
    toSide: "bottom",
    color: C.yellow,
    width: 3,
  });
  labelPill(slide, "NEURAL TIER", 944, 407, 116, C.red);

  footer(slide, 5, "Fonte: moduli pefforza/vision, envs, agent e interaction.", true);
  addNotes(
    slide,
    `
Il runtime non passa immagini al PPO: BoardDetector traduce prima il frame in una griglia 6x7.
Il training avviene interamente in Connect4Env, dove gli episodi possono essere eseguiti molto piu velocemente e senza hardware.
Il punto di contatto e il checkpoint: difficulty.py lo carica come uno dei motori disponibili, accanto a random, euristica e minimax.
`,
  );
  return slide;
}

function slide06(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = { type: "solid", color: C.paper };
  title(slide, "La matrice 6x7 e il contratto comune\ndi tutto il sistema.", {
    kicker: "CORE DI GIOCO",
    size: 41,
    height: 100,
  });

  const sample = [
    [0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0],
    [0, 0, 2, 1, 0, 0, 0],
    [0, 2, 2, 1, 0, 0, 0],
    [1, 2, 1, 1, 2, 0, 0],
  ];
  board(slide, 72, 216, 420, sample, { panel: C.board, hole: "#E5E0D7" });
  text(slide, "np.ndarray  |  shape=(6,7)  |  dtype=int8", 72, 594, 420, 30, {
    font: FONT_MONO,
    size: 14,
    color: C.gray2,
    align: "center",
  });

  const rails = [
    {
      y: 218,
      tag: "STATO",
      headline: "42 celle",
      detail: "0 vuota  |  1 player 1  |  2 player 2",
      color: C.blue,
    },
    {
      y: 332,
      tag: "AZIONE",
      headline: "1 colonna",
      detail: "intero da 0 a 6; la gravita sceglie la riga",
      color: C.red,
    },
    {
      y: 446,
      tag: "REWARD",
      headline: "+1 / 0 / -1",
      detail: "vittoria, transizione/pareggio, sconfitta nel wrapper",
      color: C.mint,
    },
    {
      y: 560,
      tag: "GUARDIA",
      headline: "-10",
      detail: "mossa illegale: episodio terminato",
      color: C.yellow,
    },
  ];
  rails.forEach((item) => {
    line(slide, 554, item.y, 8, 76, item.color);
    labelPill(slide, item.tag, 580, item.y, 96, item.color, item.color === C.yellow ? C.ink : C.white);
    text(slide, item.headline, 704, item.y - 4, 224, 38, {
      font: FONT_DISPLAY,
      size: 28,
      bold: true,
      color: C.ink,
    });
    text(slide, item.detail, 704, item.y + 40, 470, 38, {
      size: 16,
      color: C.gray2,
    });
  });

  footer(slide, 6, "Fonte: constants.py, rules.py e envs/connect4_env.py.");
  addNotes(
    slide,
    `
La rappresentazione e volutamente minima: 42 interi bastano per descrivere completamente la posizione.
rules.py applica la gravita, trova le colonne disponibili e verifica allineamenti orizzontali, verticali e diagonali.
Connect4Env aggiunge l'interfaccia Gymnasium: reset, step, observation space, action space e ricompense.
La penalita -10 per le mosse illegali e conservata per mantenere compatibili i checkpoint gia addestrati.
`,
  );
  return slide;
}

function slide07(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = { type: "solid", color: "#12265A" };
  title(slide, "Il PPO ha imparato giocando,\nnon guardando immagini.", {
    kicker: "COME HA IMPARATO",
    dark: true,
    size: 44,
    height: 102,
  });

  const centerX = 652;
  const centerY = 404;
  circle(slide, centerX - 88, centerY - 88, 176, C.yellow);
  text(slide, "PPO", centerX - 88, centerY - 63, 176, 58, {
    font: FONT_DISPLAY,
    size: 40,
    bold: true,
    color: C.ink,
    align: "center",
    valign: "middle",
  });
  text(slide, "aggiorna policy\n+ value function", centerX - 76, centerY, 152, 58, {
    size: 15,
    color: C.ink,
    align: "center",
  });

  const loop = [
    {
      x: 134,
      y: 250,
      w: 210,
      h: 84,
      label: "OSSERVAZIONE\n42 valori",
      fill: C.blue,
      name: "ppo-observation",
    },
    {
      x: 936,
      y: 250,
      w: 210,
      h: 84,
      label: "AZIONE\ncolonna 0..6",
      fill: C.red,
      name: "ppo-action",
    },
    {
      x: 936,
      y: 500,
      w: 210,
      h: 84,
      label: "REWARD\n+1 / 0 / -1",
      fill: C.mint,
      color: C.ink,
      name: "ppo-reward",
    },
    {
      x: 134,
      y: 500,
      w: 210,
      h: 84,
      label: "NUOVO STATO\nmossa avversaria",
      fill: C.ink2,
      name: "ppo-next",
    },
  ].map((node) =>
    sourceBox(slide, node.label, node.x, node.y, node.w, node.h, node.fill, {
      color: node.color || C.white,
      size: 18,
      name: node.name,
    }),
  );

  connect(slide, loop[0], loop[1], { color: C.yellow, width: 4 });
  connect(slide, loop[1], loop[2], {
    kind: "elbow",
    fromSide: "bottom",
    toSide: "top",
    color: C.yellow,
    width: 4,
  });
  connect(slide, loop[2], loop[3], {
    fromSide: "left",
    toSide: "right",
    color: C.yellow,
    width: 4,
  });
  connect(slide, loop[3], loop[0], {
    kind: "elbow",
    fromSide: "top",
    toSide: "bottom",
    color: C.yellow,
    width: 4,
  });

  labelPill(slide, "SinglePlayerWrapper", 498, 234, 306, C.ink2);
  text(
    slide,
    "L'ambiente esegue automaticamente\nuna mossa casuale dell'avversario.",
    468,
    274,
    366,
    56,
    { size: 16, color: C.gray, align: "center" },
  );

  metric(slide, "501.760", "timestep nel checkpoint", 80, 598, 240, {
    color: C.yellow,
    labelColor: C.gray,
    size: 34,
  });
  metric(slide, "2.048", "step per rollout", 390, 598, 190, {
    color: C.mint,
    labelColor: C.gray,
    size: 34,
  });
  metric(slide, "64", "batch size", 650, 598, 150, {
    color: C.red,
    labelColor: C.gray,
    size: 34,
  });
  metric(slide, "0,99", "gamma", 870, 598, 140, {
    color: C.blue2,
    labelColor: C.gray,
    size: 34,
  });

  footer(slide, 7, "Fonte: train.py e metadata del checkpoint Stable-Baselines3.", true);
  addNotes(
    slide,
    `
PPO e un algoritmo actor-critic: la policy propone azioni e una value function stima quanto e promettente lo stato.
SinglePlayerWrapper trasforma il gioco a due turni in un problema single-agent compatibile con Stable-Baselines3.
Il modello incluso registra 501.760 timestep; il training e avvenuto su CPU con i parametri PPO standard riportati nel checkpoint.
La computer vision non partecipa al training: serve soltanto a ricreare, nel mondo reale, la stessa osservazione numerica.
`,
  );
  return slide;
}

function slide08(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = { type: "solid", color: C.paper };
  title(slide, "Il neurale ha appreso le basi.\nLa ricerca classica ha vinto il confronto.", {
    kicker: "VALUTAZIONE",
    size: 41,
    height: 100,
  });

  text(slide, "PPO vs minimax depth 4  |  40 partite", 66, 213, 540, 30, {
    font: FONT_DISPLAY,
    size: 17,
    bold: true,
    color: C.gray2,
  });
  const barX = 68;
  const barY = 272;
  const barW = 690;
  const winW = barW * 0.275;
  rect(slide, barX, barY, barW, 96, C.paper2, { geometry: "roundRect" });
  rect(slide, barX, barY, winW, 96, C.mint, { geometry: "roundRect" });
  rect(slide, barX + winW, barY, barW - winW, 96, C.red, { geometry: "roundRect" });
  text(slide, "27,5%", barX + 18, barY + 11, winW - 36, 42, {
    font: FONT_DISPLAY,
    size: 30,
    bold: true,
    color: C.ink,
    align: "center",
  });
  text(slide, "vittorie PPO", barX + 18, barY + 56, winW - 36, 22, {
    size: 14,
    color: C.ink,
    align: "center",
  });
  text(slide, "72,5%", barX + winW + 18, barY + 11, barW - winW - 36, 42, {
    font: FONT_DISPLAY,
    size: 30,
    bold: true,
    color: C.white,
    align: "center",
  });
  text(slide, "sconfitte PPO", barX + winW + 18, barY + 56, barW - winW - 36, 22, {
    size: 14,
    color: C.white,
    align: "center",
  });

  text(
    slide,
    "Il risultato non invalida il reinforcement learning:\nmostra esattamente cosa ha imparato e cosa non ha visto.",
    68,
    402,
    690,
    72,
    { font: FONT_DISPLAY, size: 24, bold: true, color: C.ink },
  );

  const insights = [
    {
      y: 218,
      no: "01",
      title: "Training opponent",
      body: "Avversario casuale: utile per regole e pattern di base, debole sulle tattiche profonde.",
      color: C.yellow,
    },
    {
      y: 356,
      no: "02",
      title: "Forza del dominio",
      body: "Connect 4 ha branching factor <= 7: alpha-beta sfrutta molto bene la struttura del gioco.",
      color: C.blue,
    },
    {
      y: 494,
      no: "03",
      title: "Decisione progettuale",
      body: "Mantenere il PPO come laboratorio neurale e usare minimax per la sfida competitiva.",
      color: C.mint,
    },
  ];
  insights.forEach((item) => {
    circle(slide, 842, item.y, 46, item.color);
    text(slide, item.no, 842, item.y, 46, 46, {
      font: FONT_DISPLAY,
      size: 15,
      bold: true,
      color: item.color === C.yellow ? C.ink : C.white,
      align: "center",
      valign: "middle",
    });
    text(slide, item.title, 910, item.y - 4, 280, 30, {
      font: FONT_DISPLAY,
      size: 20,
      bold: true,
      color: C.ink,
    });
    text(slide, item.body, 910, item.y + 32, 292, 64, {
      size: 15,
      color: C.gray2,
    });
  });

  labelPill(slide, "LEZIONE: MISURARE PRIMA DI DICHIARARE", 68, 545, 410, C.ink);
  footer(slide, 8, "Fonte: benchmark documentato nel commit 729dddb (40 partite).");
  addNotes(
    slide,
    `
Il repository contiene una valutazione esplicita: contro minimax depth 4 il PPO ha vinto il 27,5% delle 40 partite.
La causa principale e coerente con il training: il modello ha affrontato soprattutto un avversario casuale.
Il risultato ha guidato il prodotto verso un'architettura ibrida, invece di nascondere la debolezza dietro l'etichetta AI.
`,
  );
  return slide;
}

function slide09(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = { type: "solid", color: C.ink };
  title(slide, "La forza finale combina strategia\ne garanzie deterministiche.", {
    kicker: "INTELLIGENZA IBRIDA",
    dark: true,
    size: 42,
    height: 102,
  });

  text(slide, "LIVELLI DI DIFFICOLTA", 62, 207, 290, 26, {
    font: FONT_DISPLAY,
    size: 14,
    bold: true,
    color: C.gray,
  });
  const tierData = [
    ["easy", "random", 128, C.gray2],
    ["medium", "win / block / center", 196, C.mint],
    ["hard", "minimax depth 5", 270, C.blue2],
    ["impossible", "iterative deepening 3s", 346, C.red],
  ];
  tierData.forEach((tier, i) => {
    const y = 252 + i * 88;
    rect(slide, 62, y, tier[2], 58, tier[3], { geometry: "roundRect" });
    text(slide, tier[0], 80, y + 5, 140, 20, {
      font: FONT_DISPLAY,
      size: 19,
      bold: true,
      color: i === 1 ? C.ink : C.white,
    });
    text(slide, tier[1], 80, y + 30, 240, 16, {
      size: 13,
      color: i === 1 ? C.ink : C.white,
    });
  });
  line(slide, 62, 613, 350, 1, "#343B50");
  labelPill(slide, "neural", 62, 631, 86, C.yellow, C.ink);
  text(slide, "PPO: ramo sperimentale, non cima della scala", 164, 631, 300, 30, {
    size: 14,
    color: C.gray,
    valign: "middle",
  });

  text(slide, "TACTICAL SAFETY NET", 572, 207, 300, 26, {
    font: FONT_DISPLAY,
    size: 14,
    bold: true,
    color: C.yellow,
  });
  const n1 = sourceBox(slide, "POSSO VINCERE\nORA?", 570, 262, 190, 78, C.red, {
    size: 18,
    name: "safety-win",
  });
  const n2 = sourceBox(slide, "L'AVVERSARIO\nVINCE ORA?", 570, 404, 190, 78, C.blue, {
    size: 18,
    name: "safety-block",
  });
  const n3 = sourceBox(slide, "DELEGA\nALL'AGENTE", 570, 546, 190, 78, C.ink2, {
    lineColor: C.mint,
    lineWidth: 2,
    size: 18,
    name: "safety-delegate",
  });
  const yes1 = sourceBox(slide, "GIOCA\nLA VITTORIA", 922, 262, 208, 78, C.yellow, {
    color: C.ink,
    size: 18,
    name: "safety-take-win",
  });
  const yes2 = sourceBox(slide, "BLOCCA\nLA MINACCIA", 922, 404, 208, 78, C.mint, {
    color: C.ink,
    size: 18,
    name: "safety-block-threat",
  });
  const chosen = sourceBox(slide, "random / heuristic /\nminimax / PPO", 922, 546, 208, 78, C.paper, {
    color: C.ink,
    size: 17,
    name: "safety-chosen-agent",
  });

  connect(slide, n1, yes1, { color: C.yellow, width: 3 });
  connect(slide, n1, n2, {
    kind: "elbow",
    fromSide: "bottom",
    toSide: "top",
    color: C.gray2,
    width: 2,
  });
  connect(slide, n2, yes2, { color: C.mint, width: 3 });
  connect(slide, n2, n3, {
    kind: "elbow",
    fromSide: "bottom",
    toSide: "top",
    color: C.gray2,
    width: 2,
  });
  connect(slide, n3, chosen, { color: C.blue2, width: 3 });
  labelPill(slide, "SI", 800, 278, 48, C.yellow, C.ink);
  labelPill(slide, "SI", 800, 420, 48, C.mint, C.ink);
  text(slide, "NO", 776, 354, 54, 24, {
    font: FONT_DISPLAY,
    size: 13,
    bold: true,
    color: C.gray,
    align: "center",
  });
  text(slide, "NO", 776, 496, 54, 24, {
    font: FONT_DISPLAY,
    size: 13,
    bold: true,
    color: C.gray,
    align: "center",
  });

  footer(slide, 9, "Fonte: difficulty.py e agent/minimax.py.", true);
  addNotes(
    slide,
    `
Hard usa Negamax con alpha-beta pruning, valutazione euristica e ordinamento delle mosse dal centro verso i bordi.
Impossible ripete la ricerca a profondita crescente e restituisce l'ultima risposta completata entro il budget di circa tre secondi.
Prima di qualunque strategia, tactical_safety_net verifica una vittoria immediata e poi una minaccia avversaria immediata.
Questo pattern e defense in depth: anche un agente debole o difettoso non puo ignorare un quattro-in-fila visibile.
`,
  );
  return slide;
}

function slide10(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = { type: "solid", color: C.paper };
  title(slide, "Quattro click trasformano una camera\ninclinata in una griglia misurabile.", {
    kicker: "COMPUTER VISION / 1",
    size: 40,
    height: 100,
  });

  text(slide, "PRIMA", 76, 202, 100, 24, {
    font: FONT_DISPLAY,
    size: 14,
    bold: true,
    color: C.gray2,
  });
  rect(slide, 72, 235, 470, 332, "#CBD4DF", {
    geometry: "roundRect",
    lineColor: C.white,
    lineWidth: 4,
  });
  text(slide, "FRAME WEBCAM", 94, 252, 180, 24, {
    font: FONT_MONO,
    size: 13,
    color: C.gray2,
  });

  const corners = [
    circle(slide, 146, 326, 18, C.red, { name: "corner-tl" }),
    circle(slide, 426, 294, 18, C.red, { name: "corner-tr" }),
    circle(slide, 464, 500, 18, C.red, { name: "corner-br" }),
    circle(slide, 110, 530, 18, C.red, { name: "corner-bl" }),
  ];
  connect(slide, corners[0], corners[1], { color: C.blue, width: 4, arrow: false });
  connect(slide, corners[1], corners[2], { color: C.blue, width: 4, arrow: false });
  connect(slide, corners[2], corners[3], { color: C.blue, width: 4, arrow: false });
  connect(slide, corners[3], corners[0], { color: C.blue, width: 4, arrow: false });
  const tokenPoints = [
    [174, 410, C.yellow],
    [238, 400, C.red],
    [300, 392, C.yellow],
    [356, 382, C.red],
    [206, 458, C.red],
    [286, 450, C.yellow],
    [372, 442, C.red],
  ];
  tokenPoints.forEach(([x, y, color]) => circle(slide, x, y, 32, color));
  text(slide, "click in qualsiasi ordine", 160, 579, 288, 28, {
    size: 15,
    color: C.gray2,
    align: "center",
  });

  const transform = sourceBox(slide, "H\n3x3", 588, 337, 96, 96, C.ink, {
    color: C.yellow,
    size: 24,
    name: "homography",
  });
  text(slide, "omografia", 570, 448, 132, 24, {
    font: FONT_DISPLAY,
    size: 14,
    bold: true,
    color: C.gray2,
    align: "center",
  });
  connect(slide, corners[1], transform, {
    fromSide: "right",
    toSide: "left",
    color: C.red,
    width: 4,
  });

  text(slide, "DOPO", 746, 202, 100, 24, {
    font: FONT_DISPLAY,
    size: 14,
    bold: true,
    color: C.gray2,
  });
  board(slide, 744, 235, 448, miniBoardGrid(), {
    panel: C.board,
    hole: "#E5E0D7",
  });
  text(slide, "700 x 600 px  |  celle regolari  |  TL / TR / BR / BL", 744, 632, 448, 28, {
    font: FONT_MONO,
    size: 13,
    color: C.gray2,
    align: "center",
  });
  connect(slide, transform, slide.shapes.getItem("connect4-board"), {
    color: C.blue,
    width: 4,
  });

  footer(slide, 10, "Fonte: vision/board_detector.py, calibrate() e _order_points().");
  addNotes(
    slide,
    `
La calibrazione raccoglie quattro punti e li ordina automaticamente usando somma e differenza delle coordinate.
Questo corregge un bug reale: se i punti venivano cliccati in un ordine diverso, numeri e frecce potevano apparire sul lato del board.
OpenCV calcola una matrice di trasformazione prospettica 3x3 e produce un'immagine rettificata nominalmente 700 per 600 pixel.
Le dimensioni vengono adattate a multipli esatti di 7 e 6, cosi ogni cella ha confini interi.
`,
  );
  return slide;
}

function slide11(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = { type: "solid", color: C.ink };
  title(slide, "Ogni cella diventa una misura esplicita\ndi colore e confidenza.", {
    kicker: "COMPUTER VISION / 2",
    dark: true,
    size: 41,
    height: 100,
  });

  const grid = [
    [0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 2, 0, 0, 0],
    [0, 0, 1, 2, 0, 0, 0],
    [0, 2, 1, 1, 0, 0, 0],
    [1, 2, 2, 1, 1, 0, 0],
  ];
  board(slide, 64, 220, 450, grid, { panel: C.board, hole: "#101521" });
  rect(slide, 249, 458, 54, 54, null, {
    geometry: "rect",
    lineColor: C.yellow,
    lineWidth: 5,
    name: "selected-cell",
  });
  text(slide, "42 ROI analizzate separatamente", 86, 622, 404, 30, {
    font: FONT_DISPLAY,
    size: 17,
    bold: true,
    color: C.gray,
    align: "center",
  });

  connect(slide, slide.shapes.getItem("selected-cell"), sourceBox(slide, "ROI\ninterna", 602, 244, 150, 94, C.yellow, {
    color: C.ink,
    size: 20,
    name: "roi-zoom",
  }), {
    color: C.yellow,
    width: 3,
  });
  text(slide, "20% di margine", 602, 348, 150, 26, {
    size: 14,
    color: C.gray,
    align: "center",
  });

  text(slide, "HSV", 818, 216, 110, 40, {
    font: FONT_DISPLAY,
    size: 30,
    bold: true,
    color: C.white,
  });
  text(slide, "separa tonalita, saturazione e luminosita", 818, 260, 360, 30, {
    size: 15,
    color: C.gray,
  });

  const bands = [
    { y: 308, label: "ROSSO A", range: "H 0-12", color: C.red, width: 120 },
    { y: 368, label: "ROSSO B", range: "H 165-180", color: "#B22558", width: 150 },
    { y: 428, label: "GIALLO", range: "H 18-45", color: C.yellow, width: 210 },
  ];
  bands.forEach((band) => {
    text(slide, band.label, 818, band.y, 100, 24, {
      font: FONT_DISPLAY,
      size: 14,
      bold: true,
      color: C.gray,
    });
    rect(slide, 930, band.y + 2, band.width, 20, band.color, { geometry: "roundRect" });
    text(slide, band.range, 1070, band.y - 2, 118, 28, {
      font: FONT_MONO,
      size: 13,
      color: C.paper,
      align: "right",
    });
  });

  text(slide, "FILL RATIO", 602, 442, 150, 26, {
    font: FONT_DISPLAY,
    size: 14,
    bold: true,
    color: C.gray,
    align: "center",
  });
  rect(slide, 602, 482, 150, 28, "#30364A", { geometry: "roundRect" });
  rect(slide, 602, 482, 96, 28, C.red, { geometry: "roundRect" });
  line(slide, 647, 476, 3, 40, C.white);
  text(slide, "30%", 624, 519, 50, 22, {
    font: FONT_MONO,
    size: 12,
    color: C.gray,
    align: "center",
  });
  text(slide, "64%", 674, 519, 54, 22, {
    font: FONT_MONO,
    size: 12,
    color: C.red,
    bold: true,
    align: "center",
  });
  labelPill(slide, "CLASSIFICATA: ROSSA", 584, 570, 190, C.red);

  sourceBox(slide, "confidence = max(pixel rossi, pixel gialli) / pixel ROI", 818, 522, 372, 84, C.ink2, {
    lineColor: C.blue2,
    lineWidth: 2,
    size: 16,
    font: FONT_MONO,
    name: "confidence-formula",
  });

  footer(slide, 11, "Fonte: _DEFAULT_*_RANGE, _CELL_MARGIN_FRAC e _FILL_THRESHOLD.", true);
  addNotes(
    slide,
    `
HSV e piu adatto del BGR per isolare un colore in presenza di variazioni moderate di luminosita.
Il rosso usa due bande perche la tonalita circonda il punto zero dell'asse hue; il giallo ne usa una.
Per ogni cella il detector ignora il 20% del bordo, conta i pixel compatibili e confronta il fill ratio con la soglia del 30%.
cell_confidences espone il rapporto massimo per aiutare a capire se il problema e luce, riflesso o soglia.
`,
  );
  return slide;
}

function slide12(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = { type: "solid", color: C.paper };
  title(slide, "Dal frame alla freccia AR:\nsei trasformazioni controllate.", {
    kicker: "DEMO FISICA",
    size: 42,
    height: 100,
  });

  const steps = [
    { n: "01", title: "CATTURA", body: "frame webcam\nspecchiato", color: C.red },
    { n: "02", title: "VISION", body: "warp + HSV\n-> grid 6x7", color: C.blue },
    { n: "03", title: "PROSPETTIVA", body: "1=rosso / 2=giallo\n-> 1=self / 2=opp", color: C.yellow },
    { n: "04", title: "DECISIONE", body: "safety net\n+ agente", color: C.mint },
    { n: "05", title: "MIRROR", body: "col = 6 - col\nper il feed", color: C.orange },
    { n: "06", title: "OUTPUT", body: "freccia AR\n+ voce", color: C.ink2 },
  ];

  const boxes = steps.map((step, i) => {
    const x = 58 + i * 202;
    circle(slide, x + 72, 220, 44, step.color);
    text(slide, step.n, x + 72, 220, 44, 44, {
      font: FONT_DISPLAY,
      size: 14,
      bold: true,
      color: step.color === C.yellow ? C.ink : C.white,
      align: "center",
      valign: "middle",
    });
    const box = sourceBox(slide, `${step.title}\n${step.body}`, x, 286, 174, 126, C.white, {
      color: C.ink,
      lineColor: step.color,
      lineWidth: 3,
      size: 17,
      name: `demo-step-${i + 1}`,
    });
    if (i < steps.length - 1) {
      line(slide, x + 174, 346, 28, 3, C.gray2);
      rect(slide, x + 192, 336, 18, 22, C.gray2, { geometry: "rightArrow" });
    }
    return box;
  });

  const beforeGrid = [
    [0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 2, 0, 0, 0],
    [0, 0, 1, 1, 0, 0, 0],
    [0, 2, 1, 2, 1, 0, 0],
  ];
  board(slide, 82, 456, 252, beforeGrid, { panel: C.board, hole: "#E5E0D7" });
  text(slide, "VISION VIEW", 82, 424, 252, 22, {
    font: FONT_DISPLAY,
    size: 13,
    bold: true,
    color: C.gray2,
    align: "center",
  });

  sourceBox(slide, "swap_perspective()", 416, 510, 206, 64, C.ink, {
    color: C.yellow,
    font: FONT_MONO,
    size: 17,
    name: "swap-perspective",
  });
  rect(slide, 634, 521, 46, 42, C.blue, { geometry: "rightArrow" });

  board(slide, 714, 456, 252, beforeGrid.map((row) => row.map((v) => (v === 1 ? 2 : v === 2 ? 1 : 0))), {
    panel: C.board,
    hole: "#E5E0D7",
  });
  text(slide, "AGENT VIEW", 714, 424, 252, 22, {
    font: FONT_DISPLAY,
    size: 13,
    bold: true,
    color: C.gray2,
    align: "center",
  });
  rect(slide, 1015, 474, 70, 68, C.red, { geometry: "downArrow" });
  labelPill(slide, "COLONNA 4", 994, 452, 112, C.yellow, C.ink);
  text(slide, "\"Putting in column 4.\"", 972, 560, 236, 52, {
    font: FONT_DISPLAY,
    size: 20,
    bold: true,
    color: C.ink,
    align: "center",
    valign: "middle",
  });

  footer(slide, 12, "Fonte: play_physical.py, rules.swap_perspective() e BoardDetector overlays.");
  addNotes(
    slide,
    `
La visione assegna 1 al rosso e 2 al giallo, mentre il modello e stato addestrato assumendo sempre 1 uguale self.
Se l'AI gioca giallo, swap_perspective scambia gli ID prima di chiamare l'agente.
La modalita fisica mostra il feed specchiato per essere intuitiva: la colonna scelta viene quindi invertita prima di disegnare la freccia.
VoiceEngine riceve la stessa colonna e accoda il commento senza bloccare il ciclo video.
`,
  );
  return slide;
}

function slide13(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = { type: "solid", color: C.ink };
  title(slide, "L'affidabilita non e arrivata alla fine.\nE diventata una feature.", {
    kicker: "QUALITA",
    dark: true,
    size: 42,
    height: 100,
  });

  metric(slide, "108", "test headless", 62, 204, 180, {
    color: C.yellow,
    labelColor: C.gray,
  });
  metric(slide, "4", "versioni Python in CI", 276, 204, 220, {
    color: C.mint,
    labelColor: C.gray,
  });
  metric(slide, "3", "quality gate principali", 530, 204, 220, {
    color: C.blue2,
    labelColor: C.gray,
  });
  metric(slide, "0", "hardware richiesto dai test", 784, 204, 260, {
    color: C.red,
    labelColor: C.gray,
  });

  line(slide, 62, 318, 1158, 1, "#30364A");
  const headers = [
    ["PROBLEMA OSSERVATO", 62, 310],
    ["CORREZIONE", 422, 312],
    ["PROVA AUTOMATICA", 826, 340],
  ];
  headers.forEach(([label, x, w]) =>
    text(slide, label, x, 342, w, 24, {
      font: FONT_DISPLAY,
      size: 13,
      bold: true,
      color: C.gray,
    }),
  );

  const rows = [
    {
      y: 386,
      problem: "AI ignora un blocco immediato",
      fix: "tactical safety net + watchdog GUI",
      proof: "threat tests + full-game simulation",
      color: C.red,
    },
    {
      y: 474,
      problem: "Numeri e freccia sul lato del board",
      fix: "corner sorting canonico TL/TR/BR/BL",
      proof: "permutazioni dei 4 click",
      color: C.yellow,
    },
    {
      y: 562,
      problem: "Animazione AI saltata dopo 3 secondi",
      fix: "clock locale + get_ticks()",
      proof: "regressione isolata nel flusso GUI",
      color: C.blue2,
    },
  ];
  rows.forEach((row) => {
    line(slide, 62, row.y, 8, 62, row.color);
    text(slide, row.problem, 86, row.y, 304, 62, {
      font: FONT_DISPLAY,
      size: 18,
      bold: true,
      color: C.white,
      valign: "middle",
    });
    text(slide, row.fix, 422, row.y, 350, 62, {
      size: 16,
      color: C.paper,
      valign: "middle",
    });
    text(slide, row.proof, 826, row.y, 360, 62, {
      font: FONT_MONO,
      size: 14,
      color: row.color,
      valign: "middle",
    });
  });

  labelPill(slide, "Ruff", 62, 646, 64, C.blue);
  labelPill(slide, "format", 138, 646, 76, C.ink2);
  labelPill(slide, "Mypy", 226, 646, 72, C.mint, C.ink);
  labelPill(slide, "Pytest + coverage", 310, 646, 146, C.yellow, C.ink);
  text(slide, "VoiceEngine: coda asincrona, backend null e fall-soft sugli errori audio.", 520, 646, 664, 30, {
    size: 15,
    color: C.gray,
    valign: "middle",
  });

  footer(slide, 13, "Fonte: tests/, CI workflow, voice.py e commit di regressione.", true);
  addNotes(
    slide,
    `
La suite corrente raccoglie 108 casi, inclusi test parametrizzati su regole, environment, minimax, difficolta, vision, voce e partite complete.
La CI esegue lint, format check, Mypy e Pytest con coverage su Python 3.10, 3.11, 3.12 e 3.13.
Tre bug reali sono diventati casi didattici: una mancata parata ha prodotto safety net e watchdog; un warp ruotato ha prodotto corner sorting; un clock condiviso ha spiegato perche l'animazione saltava.
La voce segue lo stesso principio: se driver o dispositivo audio falliscono, il gioco continua.
`,
  );
  return slide;
}

function slide14(presentation) {
  const slide = presentation.slides.add();
  slide.background.fill = { type: "solid", color: C.paper };
  rect(slide, 0, 0, 520, H, C.ink);
  labelPill(slide, "ROADMAP", 58, 54, 104, C.yellow, C.ink);
  text(slide, "Il prossimo passo\nparte dai limiti reali.", 56, 120, 408, 160, {
    font: FONT_DISPLAY,
    size: 46,
    bold: true,
    color: C.white,
  });
  text(
    slide,
    "Pefforza non e un singolo modello.\nE una pipeline completa, misurabile e migliorabile.",
    58,
    330,
    402,
    104,
    { size: 22, color: C.paper },
  );
  line(slide, 58, 470, 350, 2, C.yellow);
  text(slide, "TAKEAWAY", 58, 494, 170, 25, {
    font: FONT_DISPLAY,
    size: 14,
    bold: true,
    color: C.yellow,
  });
  text(
    slide,
    "L'intelligenza utile nasce quando percezione, algoritmi e affidabilita vengono progettati insieme.",
    58,
    530,
    402,
    110,
    { font: FONT_DISPLAY, size: 25, bold: true, color: C.white },
  );

  const roadmap = [
    {
      y: 112,
      tag: "P0",
      title: "HSV adattivo",
      body: "Campionare i colori reali e compensare l'illuminazione.",
      color: C.red,
    },
    {
      y: 246,
      tag: "P1",
      title: "Calibrazione automatica",
      body: "ArUco o contorni per eliminare i quattro click manuali.",
      color: C.blue,
    },
    {
      y: 380,
      tag: "P2",
      title: "Self-play competitivo",
      body: "Allenare PPO contro avversari piu forti e versioni storiche.",
      color: C.mint,
    },
    {
      y: 514,
      tag: "P3",
      title: "Web + smartphone",
      body: "ONNX e OpenCV.js per una demo senza installazione Python.",
      color: C.yellow,
    },
  ];
  roadmap.forEach((item, i) => {
    const x = 582;
    circle(slide, x, item.y, 54, item.color);
    text(slide, item.tag, x, item.y, 54, 54, {
      font: FONT_DISPLAY,
      size: 15,
      bold: true,
      color: item.color === C.yellow ? C.ink : C.white,
      align: "center",
      valign: "middle",
    });
    if (i < roadmap.length - 1) line(slide, x + 25, item.y + 54, 4, 80, C.paper2);
    text(slide, item.title, 660, item.y - 2, 470, 34, {
      font: FONT_DISPLAY,
      size: 25,
      bold: true,
      color: C.ink,
    });
    text(slide, item.body, 660, item.y + 40, 470, 48, {
      size: 17,
      color: C.gray2,
    });
  });

  text(slide, "Demo consigliata", 1014, 630, 180, 22, {
    font: FONT_DISPLAY,
    size: 13,
    bold: true,
    color: C.gray2,
    align: "right",
  });
  text(slide, "GUI -> diagnose -> AR", 970, 654, 224, 24, {
    font: FONT_MONO,
    size: 14,
    color: C.blue,
    align: "right",
  });
  text(slide, "14", 1180, 688, 42, 18, {
    font: FONT_DISPLAY,
    size: 12,
    bold: true,
    color: C.blue,
    align: "right",
  });

  addNotes(
    slide,
    `
La roadmap nasce dai limiti osservati nel codice, non da funzionalita decorative.
La priorita immediata e rendere la vision adattiva alla luce e ridurre la calibrazione manuale.
Sul lato AI, il miglioramento piu significativo sarebbe un curriculum di avversari o self-play competitivo.
Per la demo finale consiglio: una partita GUI, il tool diagnose con confidence e infine la raccomandazione AR sul board fisico.
La conclusione e che il valore del progetto sta nell'integrazione verificabile tra percezione, decisione e interazione.
`,
  );
  return slide;
}

const slideBuilders = [
  slide01,
  slide02,
  slide03,
  slide04,
  slide05,
  slide06,
  slide07,
  slide08,
  slide09,
  slide10,
  slide11,
  slide12,
  slide13,
  slide14,
];

async function saveBlob(blob, destination) {
  await fsp.mkdir(path.dirname(destination), { recursive: true });
  const buffer = Buffer.from(await blob.arrayBuffer());
  await fsp.writeFile(destination, buffer);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const repoRoot = path.resolve(__dirname, "..");
  const outPath = path.resolve(
    repoRoot,
    args.out || path.join("presentation", "Pefforza4_Project_Presentation.pptx"),
  );
  const previewDir = args["preview-dir"]
    ? path.resolve(repoRoot, args["preview-dir"])
    : null;
  const layoutDir = args["layout-dir"]
    ? path.resolve(repoRoot, args["layout-dir"])
    : null;

  const artifact = await import(pathToFileURL(artifactToolEntry()).href);
  const { Presentation, PresentationFile } = artifact;
  const presentation = Presentation.create({ slideSize: { width: W, height: H } });

  const slides = slideBuilders.map((build) => build(presentation));

  if (previewDir) {
    await fsp.mkdir(previewDir, { recursive: true });
    for (let i = 0; i < slides.length; i += 1) {
      const preview = await presentation.export({ slide: slides[i], format: "png", scale: 1 });
      await saveBlob(preview, path.join(previewDir, `slide-${String(i + 1).padStart(2, "0")}.png`));
    }
  }

  if (layoutDir) {
    await fsp.mkdir(layoutDir, { recursive: true });
    for (let i = 0; i < slides.length; i += 1) {
      const layout = await presentation.export({ slide: slides[i], format: "layout" });
      await fsp.writeFile(
        path.join(layoutDir, `slide-${String(i + 1).padStart(2, "0")}.layout.json`),
        await layout.text(),
        "utf8",
      );
    }
  }

  await fsp.mkdir(path.dirname(outPath), { recursive: true });
  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(outPath);

  const stat = await fsp.stat(outPath);
  if (stat.size === 0) throw new Error(`PPTX vuoto: ${outPath}`);

  console.log(
    JSON.stringify(
      {
        output: outPath,
        bytes: stat.size,
        slides: slides.length,
        previews: previewDir,
        layouts: layoutDir,
      },
      null,
      2,
    ),
  );
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
