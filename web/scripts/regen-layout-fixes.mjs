#!/usr/bin/env node
/**
 * Regenerate room-base, rug, and bed with layout fixes:
 * - Room: wider shot, more space
 * - Rug: flat on floor, perpendicular to window
 * - Bed: headboard against back wall, foot facing us
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

const TRANSPARENCY = `
TRANSPARENCY & CUTOUT (critical — read carefully):
- The background MUST be 100% transparent. ONLY the object itself is visible.
- Absolutely NO shadow of any kind baked into the image — no contact shadow,
  no drop shadow, no ambient occlusion shadow, no soft glow beneath the object.
  The area under and around the object must be COMPLETELY TRANSPARENT.
- Absolutely NO glow effects, NO light halos, NO white or cream fog, NO bloom.
- Edges must be pixel-clean against transparency — no white fringe, no light halo,
  no semi-opaque border, no feathered white edge.
- The ONLY visible pixels should be the object itself. Everything else
  is fully transparent (alpha = 0).
`.trim();

const PIECES = {
  "room-base": {
    transparent: false,
    prompt: `
Illustrate a WIDE-SHOT SIDE VIEW of a luxurious tropical bedroom — EMPTY of furniture.

This is the BACKGROUND ONLY — no bed, no nightstand, no dresser, no lamps, no rugs,
no furniture of any kind. Just the room shell and architectural elements.

The room includes:
- BACK WALL: warm cream/off-white wall, smooth and elegant
- FLOOR: beautiful warm honey-toned hardwood floor with subtle grain, stretching
  the full width. Floor line at roughly 60-65% down from top of canvas.
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

IMPORTANT — WIDE SHOT: The room should feel VERY SPACIOUS — pull the camera BACK
further than a normal room view. Show generous empty space on both sides. High ceilings,
wide proportions. Think of a grand luxury villa suite, not a small bedroom.
The room should feel airy with lots of breathing room for furniture to be placed later.

${STYLE_D_LOCKED}
`,
  },

  rug: {
    transparent: true,
    prompt: `
Illustrate a RECTANGULAR AREA RUG on a completely transparent background.

- Rich woven texture — warm neutral tones with a sophisticated pattern
  (subtle geometric, moroccan-inspired, or tone-on-tone texture)
- Warm cream, soft gold, and muted terracotta tones
- Plush, luxurious appearance with clean edges or subtle fringe

CRITICAL PERSPECTIVE: The rug is seen in a FLAT SIDE VIEW — we are looking at
the room straight-on from the side. The rug is lying flat on the floor.
Because we are viewing from the side at eye level, the rug appears as a very
THIN HORIZONTAL STRIP — heavily foreshortened. We see mostly the front edge
and just a sliver of the top surface receding toward the back wall.

The rug runs PERPENDICULAR to us (away from the viewer toward the back wall).
It should appear as a wide but very short/thin horizontal band — like a
rectangle seen almost edge-on. Think of looking at a credit card held flat
on a table at eye level — you see mostly the front edge.

Width: roughly 55-60% of canvas width, centered.
Height: only about 5-8% of canvas height (because of extreme foreshortening).

${TRANSPARENCY}
${STYLE_D_LOCKED}
`,
  },

  bed: {
    transparent: true,
    prompt: `
Illustrate a FULL DRESSED BED on a completely transparent background.

The bed includes (all as one combined illustration):
- A rich dark wood headboard, elegant and substantial, with refined carved or
  paneled detail — luxurious but not ornate
- A matching bed frame with sturdy legs
- Plush white/cream linens — crisp sheets, fluffy duvet
- A deep dusty blue (#6B8FA3) accent throw or duvet folded at the foot
- Multiple plump white pillows (3-4) layered against the headboard
- The bedding looks PLUSH and INVITING — luxury hotel quality

CRITICAL ORIENTATION: The bed's HEADBOARD is against the BACK WALL (away from us),
and the FOOT of the bed faces TOWARD US (the viewer). We are looking at the bed
from the foot end, straight-on. This means:
- The headboard is at the TOP of the image (far from us)
- The foot board / end of the bed is at the BOTTOM of the image (close to us)
- We see the bed receding away from us — the foot is wider (closer), the
  headboard is narrower (further away) due to perspective
- Pillows are visible at the far end against the headboard
- The duvet/comforter drapes toward us over the foot

This is a STRAIGHT-ON FRONT VIEW of the foot of the bed.
The bed should fill roughly 45-50% of the canvas width, centered.

${TRANSPARENCY}
${STYLE_D_LOCKED}
`,
  },
};

async function generate(name, config) {
  console.log(`\n🎨 Generating ${name}...`);
  const startTime = Date.now();

  const params = {
    model: "gpt-image-1",
    prompt: config.prompt,
    n: 1,
    size: "1536x1024",
    quality: "medium",
  };
  if (config.transparent) {
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

const names = Object.keys(PIECES);

try {
  // Batch 1: room-base + rug
  console.log("\n── Batch 1: room-base, rug ──");
  await Promise.all([
    generate("room-base", PIECES["room-base"]),
    generate("rug", PIECES["rug"]),
  ]);

  console.log("\n⏳ Waiting 15s (rate limit)...");
  await new Promise((r) => setTimeout(r, 15000));

  // Batch 2: bed
  console.log("\n── Batch 2: bed ──");
  await generate("bed", PIECES["bed"]);

  // Resize all
  console.log("\n📦 Resizing...");
  for (const name of names) {
    const filePath = path.join(OUT_DIR, `${name}.png`);
    const beforeKB = (fs.statSync(filePath).size / 1024).toFixed(0);
    try {
      execSync(`sips --resampleWidth 1024 "${filePath}" 2>/dev/null`, { stdio: "pipe" });
      const afterKB = (fs.statSync(filePath).size / 1024).toFixed(0);
      console.log(`  ${name}: ${beforeKB} KB → ${afterKB} KB`);
    } catch {
      console.log(`  ${name}: skipped`);
    }
  }

  console.log("\n✅ Done!");
} catch (err) {
  console.error("\n❌ Failed:", err.message);
  process.exit(1);
}
