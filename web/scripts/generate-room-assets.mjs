#!/usr/bin/env node
/**
 * Generate room scene assets using OpenAI gpt-image-1.
 *
 * Usage:
 *   node scripts/generate-room-assets.mjs [room|pieces|all]
 *
 * Outputs PNGs to public/room-assets/
 */

import OpenAI from "openai";
import fs from "fs";
import path from "path";
import { execSync } from "child_process";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.resolve(__dirname, "../public/room-assets");

const envPath = path.resolve(__dirname, "../../.env");
if (fs.existsSync(envPath)) {
  const envContent = fs.readFileSync(envPath, "utf-8");
  for (const line of envContent.split("\n")) {
    const match = line.match(/^([^#=]+)=(.*)$/);
    if (match) process.env[match[1].trim()] = match[2].trim();
  }
}

const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

// ─── LOCKED STYLE D — "LUSH LUXURY" CANONICAL SPEC ─────────────────
const STYLE_D_LOCKED = `
STYLE SPECIFICATION — "Lush Luxury Illustrated" (follow EXACTLY):
- Medium: rich digital illustration with soft painterly texture — slightly more
  realistic than gouache but NOT photorealistic. Think high-end editorial illustration
  or concept art for a luxury hotel brochure. Soft brush texture visible but refined.
- Perspective: FLAT SIDE VIEW (elevation view) — camera is straight-on at eye level,
  looking at the room from one wall. NO 3/4 angle, NO isometric, NO top-down.
  Like a cross-section or dollhouse side view. Simple 2D composition.
- Lighting: warm golden tropical morning light flooding in from large windows,
  lush and rich, soft volumetric warmth, gentle highlights on surfaces
- Color palette: rich and lush —
  deep cream walls (#F5EDE3), warm honey wood floors (#D4A574, #C49A6C),
  rich emerald and tropical greens (#2D5A3D, #4A7C59, #8DB98F) for plants/jungle,
  deep dusty blue (#6B8FA3, #8BAAB8) for bedding accents,
  warm brass/gold (#C5A55A, #D4B96A) for fixtures and hardware,
  crisp white linens (#FFF8F0, #F5EDE0),
  warm terracotta (#C4A882, #B8956A) for pots and accents,
  soft dusty rose (#D4A5A0, #E8C8B8) for textiles,
  rich dark wood (#6B4E3D, #8B6F5C) for furniture accents
- Line style: soft, refined edges — NOT cartoony, NOT vector-sharp.
  Shapes defined by value and color, minimal outlines.
- Texture: refined painterly — smooth but with subtle brush quality,
  NOT slick CG, NOT flat vector, NOT photographic
- Mood: lush, luxurious, tropical, serene — like waking up in a beautiful
  resort villa with jungle and mountains outside
- CRITICAL: This is a BEAUTIFUL ILLUSTRATION — elevated, editorial quality.
  NOT a photograph, NOT a 3D render, NOT cartoonish. Lush, warm, inviting.
- Canvas: 1536×1024 pixels, landscape orientation
`.trim();

// ─── STRICT TRANSPARENCY — NO SHADOWS, NO GLOW ─────────────────────
const TRANSPARENCY = `
TRANSPARENCY & CUTOUT (critical — read carefully):
- The background MUST be 100% transparent. ONLY the object itself is visible.
- Absolutely NO shadow of any kind baked into the image — no contact shadow,
  no drop shadow, no ambient occlusion shadow, no soft glow beneath the object.
  The area under and around the object must be COMPLETELY TRANSPARENT.
- Absolutely NO glow effects, NO light halos, NO white or cream fog, NO bloom.
  If this is a lamp, render only the physical lamp object (shade, stem, base) —
  do NOT paint any light rays, glow clouds, or luminous halos around the shade.
- Edges must be pixel-clean against transparency — no white fringe, no light halo,
  no semi-opaque border, no feathered white edge.
- The ONLY visible pixels should be the furniture/object itself. Everything else
  is fully transparent (alpha = 0).
`.trim();

// ─── ROOM BASE PROMPT ───────────────────────────────────────────────
const ROOM_BASE = `
Illustrate a WIDE-SHOT SIDE VIEW of a luxurious tropical bedroom — EMPTY of furniture.

This is the BACKGROUND ONLY — no bed, no nightstand, no dresser, no lamps, no rugs,
no furniture of any kind. Just the room shell and architectural elements.

The room includes:
- BACK WALL: warm cream/off-white wall, smooth and elegant
- FLOOR: beautiful warm honey-toned hardwood floor with subtle grain, stretching
  the full width. Floor line at roughly 60% down from top of canvas.
- LARGE WINDOWS on the back wall (center-left area): tall elegant windows with
  thin dark frames, showing a LUSH TROPICAL LANDSCAPE outside —
  dense jungle canopy in rich greens, misty blue-green mountains in the distance,
  golden morning light filtering through. The view should feel like a luxury
  resort in Bali or Costa Rica.
- CEILING: visible at top, warm white, with subtle crown molding or clean edge
- Subtle architectural details: clean baseboards, maybe a subtle wall panel or
  wainscoting in the lower third
- Warm golden morning light flooding through the windows, casting soft light
  across the floor and walls

Perspective: FLAT SIDE VIEW — straight-on elevation, like looking at the room
from the missing fourth wall. Simple 2D composition. The floor is a horizontal
plane at the bottom, the back wall is flat behind it.

The room should feel SPACIOUS and LUXURIOUS — high ceilings, generous proportions.
Leave plenty of empty floor and wall space where furniture will be layered on top.

${STYLE_D_LOCKED}
`;

// ─── PIECE PROMPTS ──────────────────────────────────────────────────

const PIECES = {
  bed: `
Illustrate a FULL DRESSED BED on a completely transparent background.

The bed includes (all as one combined illustration):
- A rich dark wood headboard, elegant and substantial, with refined carved or
  paneled detail — luxurious but not ornate
- A matching bed frame with sturdy legs
- Plush white/cream linens — crisp sheets, fluffy duvet
- A deep dusty blue (#6B8FA3) accent throw or duvet folded at the foot
- Multiple plump white pillows (3-4) layered against the headboard
- The bedding looks PLUSH and INVITING — luxury hotel quality

Orientation: SIDE VIEW — headboard on the LEFT, foot of bed on the RIGHT.
Straight-on, flat perspective. No 3/4 angle.
The bed should fill roughly 50-55% of the canvas width, centered.

${TRANSPARENCY}
${STYLE_D_LOCKED}
`,

  nightstand: `
Illustrate a SMALL BEDSIDE NIGHTSTAND on a completely transparent background.

- Rich warm wood (dark honey or walnut tone), matching luxury bedroom furniture
- One or two small drawers with brass/gold knobs or pulls
- Four tapered or turned legs
- A flat top surface (empty — no objects on it)
- Refined, elegant proportions

Orientation: SIDE VIEW — straight-on, flat perspective. Front face visible.
Fill roughly 15-18% of canvas width, centered.

${TRANSPARENCY}
${STYLE_D_LOCKED}
`,

  dresser: `
Illustrate a WIDE BEDROOM DRESSER on a completely transparent background.

- Rich warm wood (dark honey or walnut tone), matching luxury bedroom furniture
- Wide and low proportioned, elegant lines
- 3-4 drawers with brass/gold hardware (knobs or bar pulls)
- Tapered or turned legs
- Flat top surface (empty)

Orientation: SIDE VIEW — straight-on, flat perspective. Front face visible.
Fill roughly 28-32% of canvas width, centered.

${TRANSPARENCY}
${STYLE_D_LOCKED}
`,

  ceiling_light: `
Illustrate a PENDANT CEILING LIGHT on a completely transparent background.

- A thin brass/gold cord or chain hanging from the very top of the canvas
- An elegant shade — woven rattan/wicker dome or warm linen drum shade,
  giving a tropical luxury feel
- Refined, natural materials look
- Render ONLY the physical fixture (cord + shade). Do NOT paint any glow,
  light rays, or luminous effects. Just the object itself.

The fixture hangs from the top-center of the canvas.
The cord should start at the very top edge.
Fill roughly 15-18% of canvas width.

${TRANSPARENCY}
${STYLE_D_LOCKED}
`,

  table_lamp: `
Illustrate a SMALL TABLE LAMP on a completely transparent background.

- A warm linen or cream fabric shade, slightly tapered (wider at bottom)
- A ceramic or turned-wood base in warm earthy tones, elegant shape
- Brass/gold accent ring where shade meets base
- Render ONLY the physical lamp (shade + stem + base). Do NOT paint any glow,
  light halo, bloom, or luminous cloud around the shade. Just the solid object.

Orientation: SIDE VIEW — straight-on, flat perspective.
Fill roughly 10-12% of canvas width, centered.

${TRANSPARENCY}
${STYLE_D_LOCKED}
`,

  floor_lamp: `
Illustrate a TALL STANDING FLOOR LAMP on a completely transparent background.

- A tall slim stem/pole in warm brass or dark wood tone
- An elegant shade — warm linen fabric or woven rattan
- A round weighted base in matching brass or wood
- Render ONLY the physical lamp (shade + stem + base). Do NOT paint any glow,
  light halo, bloom, or luminous cloud around the shade. Just the solid object.

Orientation: SIDE VIEW — straight-on, flat perspective.
Fill roughly 12-15% of canvas width and about 55-60% of canvas height, centered.

${TRANSPARENCY}
${STYLE_D_LOCKED}
`,

  wall_art: `
Illustrate a SINGLE FRAMED ARTWORK for a wall, on a completely transparent background.

- An elegant frame in dark wood or thin brass/gold
- Inside: a lush landscape or abstract artwork — rich greens, deep blues,
  warm golds — complementing the tropical luxury theme
- The artwork should feel curated and sophisticated
- Rectangular, landscape orientation

Orientation: FRONT-FACING — flat, straight-on, no perspective distortion.
Fill roughly 18-20% of canvas width, centered.

${TRANSPARENCY}
${STYLE_D_LOCKED}
`,

  plant: `
Illustrate a SINGLE POTTED PLANT on a completely transparent background.

- A stylish pot — warm terracotta, matte black ceramic, or woven basket planter
- LUSH tropical foliage — large dramatic leaves (monstera, bird of paradise,
  fiddle leaf fig, or similar tropical plant). Rich deep greens (#2D5A3D, #4A7C59).
- Tall and dramatic — a statement floor plant
- Feels like it belongs in a luxury tropical villa

Orientation: SIDE VIEW — straight-on, flat perspective.
Fill roughly 18-22% of canvas width, centered.

${TRANSPARENCY}
${STYLE_D_LOCKED}
`,

  mirror: `
Illustrate a WALL MIRROR on a completely transparent background.

- An elegant frame — thin brass/gold or dark wood, refined
- Oval or rounded-rectangle shape, tall proportions
- The mirror surface shows a very soft, blurred warm reflection (just warm light
  and vague soft colors — not a detailed room reflection)

Orientation: FRONT-FACING — flat, straight-on, no perspective.
Fill roughly 12-15% of canvas width, centered.

${TRANSPARENCY}
${STYLE_D_LOCKED}
`,

  rug: `
Illustrate a RECTANGULAR AREA RUG on a completely transparent background.

- Rich woven texture — warm neutral tones with a sophisticated pattern
  (subtle geometric, moroccan-inspired, or tone-on-tone texture)
- Warm cream, soft gold, and muted terracotta tones
- Plush, luxurious appearance with clean edges or subtle fringe
- Rectangular, sized to go under a bed

Orientation: seen from STRAIGHT ABOVE but slightly foreshortened to suggest
floor plane — the rug appears as a slightly compressed rectangle
(wider than tall). It lies FLAT.
Fill roughly 50-55% of canvas width, centered.

${TRANSPARENCY}
${STYLE_D_LOCKED}
`,

  curtains: `
Illustrate a PAIR OF CURTAINS / WINDOW DRAPES on a completely transparent background.

- Two panels of luxurious sheer or light linen fabric in warm cream/white
- Floor-length, gently gathered, hung from a thin brass rod visible at top
- Soft flowing drape with natural folds — elegant and airy
- Between the curtain panels: leave an open gap (transparent) where the window is
- The panels should feel light, tropical, breezy

Orientation: FRONT-FACING — flat, straight-on perspective.
Fill roughly 35-40% of canvas width, centered. Height: roughly 55-60% of canvas.

${TRANSPARENCY}
${STYLE_D_LOCKED}
`,

  throw_blanket: `
Illustrate ONLY a folded/draped THROW BLANKET by itself, on a completely transparent background.

CRITICAL — THIS IS JUST THE BLANKET. DO NOT DRAW A BED OR ANY FURNITURE.
ONLY THE THROW BLANKET FABRIC ITSELF — NOTHING ELSE.

- A luxurious knit or woven throw in warm dusty rose (#D4A5A0) or soft terracotta
- Casually folded as if tossed — rumpled, relaxed, organic shape
- Rich, tactile texture — chunky knit or herringbone weave
- Fringed or tasseled edges visible
- Oriented roughly horizontally, as if draped across the foot of a bed

Fill roughly 25-28% of canvas width, centered.

${TRANSPARENCY}
${STYLE_D_LOCKED}
`,
};

// ─── GENERATION ──────────────────────────────────────────────────────

async function generate(name, prompt, transparent) {
  console.log(`\n🎨 Generating ${name}...`);
  const startTime = Date.now();

  const params = {
    model: "gpt-image-1",
    prompt,
    n: 1,
    size: "1536x1024",
    quality: "medium",
  };
  if (transparent) {
    params.background = "transparent";
  }

  const response = await client.images.generate(params);
  const imageData = response.data[0];
  const b64 = imageData.b64_json;

  let buffer;
  if (!b64) {
    const imgResponse = await fetch(imageData.url);
    buffer = Buffer.from(await imgResponse.arrayBuffer());
  } else {
    buffer = Buffer.from(b64, "base64");
  }

  const outPath = path.join(OUT_DIR, `${name}.png`);
  fs.writeFileSync(outPath, buffer);
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  const sizeKB = (buffer.length / 1024).toFixed(0);
  console.log(`  ✅ ${name}.png (${sizeKB} KB, ${elapsed}s)`);
}

function optimizePngs(names) {
  console.log(`\n📦 Optimizing ${names.length} PNGs (resize to 1024 wide)...`);
  for (const name of names) {
    const filePath = path.join(OUT_DIR, `${name}.png`);
    if (!fs.existsSync(filePath)) continue;
    const beforeKB = (fs.statSync(filePath).size / 1024).toFixed(0);
    try {
      execSync(`sips --resampleWidth 1024 "${filePath}" 2>/dev/null`, { stdio: "pipe" });
      const afterKB = (fs.statSync(filePath).size / 1024).toFixed(0);
      console.log(`  ${name}: ${beforeKB} KB → ${afterKB} KB`);
    } catch {
      console.log(`  ${name}: skipped (sips error)`);
    }
  }
}

// ─── MAIN ────────────────────────────────────────────────────────────

const target = process.argv[2] || "all";
fs.mkdirSync(OUT_DIR, { recursive: true });

try {
  if (target === "room" || target === "all") {
    console.log("\n══ Generating room base ══");
    await generate("room-base", ROOM_BASE, false);
    optimizePngs(["room-base"]);
  }

  if (target === "pieces" || target === "all") {
    const pieceNames = Object.keys(PIECES);
    // Generate in batches of 2 (rate limit: 5/min)
    for (let i = 0; i < pieceNames.length; i += 2) {
      const batch = pieceNames.slice(i, i + 2);
      console.log(`\n── Batch ${Math.floor(i / 2) + 1}: ${batch.join(", ")} ──`);
      await Promise.all(
        batch.map((name) => generate(name, PIECES[name], true))
      );
      if (i + 2 < pieceNames.length) {
        console.log("\n⏳ Waiting 15s (rate limit)...");
        await new Promise((r) => setTimeout(r, 15000));
      }
    }
    optimizePngs(pieceNames);
  }

  console.log("\n✅ Done! Assets in public/room-assets/");
} catch (err) {
  console.error("\n❌ Generation failed:", err.message);
  if (err.response) {
    console.error("  API response:", JSON.stringify(err.response, null, 2));
  }
  process.exit(1);
}
