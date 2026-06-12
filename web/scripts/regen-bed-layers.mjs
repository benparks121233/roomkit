#!/usr/bin/env node
/**
 * Generate 5 bed sub-layers that stack to recreate the existing bed exactly.
 * Each layer occupies the same canvas position so they overlay perfectly.
 *
 * Layers (bottom to top):
 *   1. bed_frame   — dark walnut/cherry headboard + frame + legs, NO bedding
 *   2. mattress    — plain white/cream mattress sitting in the frame
 *   3. sheets      — white/cream duvet/sheets draped over, no pillows, no runner
 *   4. comforter   — the dusty blue (#6B8FA3) accent runner across the middle
 *   5. pillows     — 3-4 plump cream pillows against the headboard
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

// ─── EXACT BED REFERENCE ────────────────────────────────────────────
// Every prompt must describe the SAME bed so pieces align when stacked.
const BED_REFERENCE = `
REFERENCE BED (all layers must match this EXACTLY):
- Dark walnut/cherry wood with refined paneled detail on the headboard
- Two recessed rectangular panels on the headboard, subtle crown molding at top
- Low-profile matching wood bed frame, simple sturdy legs
- The bed is seen STRAIGHT-ON from the foot end (headboard at top, foot toward us)
- The headboard is centered, roughly 48% of canvas width
- The bed frame bottom/legs are at roughly 78% down the canvas
- The headboard top is at roughly 28% down the canvas
- Rich, warm wood tone — NOT light oak, NOT black, a warm medium-dark brown/cherry

CRITICAL: This layer must be positioned and sized so that when ALL five layers
(bed_frame, mattress, sheets, comforter, pillows) are stacked at the EXACT same
position and size, they reconstruct the complete bed. Every layer uses the same
canvas positioning and proportions.
`.trim();

const STYLE_D_LOCKED = `
STYLE SPECIFICATION — "Lush Luxury Illustrated" (follow EXACTLY):
- Medium: rich digital illustration with soft painterly texture — slightly more
  realistic than gouache but NOT photorealistic. Think high-end editorial illustration
  or concept art for a luxury hotel brochure. Soft brush texture visible but refined.
- Perspective: FLAT SIDE VIEW (elevation view) — camera is straight-on at eye level.
  Simple 2D composition.
- Lighting: warm golden tropical morning light, lush and rich, soft volumetric warmth
- Color palette: rich dark wood (#6B4E3D, #8B6F5C), crisp white linens (#FFF8F0, #F5EDE0),
  deep dusty blue (#6B8FA3) for accent, warm brass/gold for hardware
- Texture: refined painterly — smooth but with subtle brush quality
- CRITICAL: Beautiful ILLUSTRATION, NOT a photograph, NOT a 3D render, NOT cartoonish.
- Canvas: 1536×1024 pixels, landscape orientation
`.trim();

const TRANSPARENCY = `
TRANSPARENCY & CUTOUT (critical):
- Background MUST be 100% transparent. ONLY the described object is visible.
- NO shadows, NO glow, NO halos, NO white fringe.
- Pixel-clean edges against transparency.
`.trim();

const LAYERS = {
  bed_frame: `
Illustrate ONLY the wooden BED FRAME (headboard + side rails + foot board + legs)
on a completely transparent background. NO mattress, NO bedding, NO sheets, NO pillows.

The frame is:
- A dark walnut/cherry wood headboard with two recessed rectangular panels and
  subtle crown molding along the top edge
- Matching wood side rails connecting headboard to a low foot board
- Sturdy tapered legs at each corner
- The frame interior is EMPTY — you can see through to the transparent background
  where a mattress would sit
- The foot board is low and simple

${BED_REFERENCE}
${TRANSPARENCY}
${STYLE_D_LOCKED}
`,

  mattress: `
Illustrate ONLY a plain MATTRESS on a completely transparent background.
NO sheets, NO bedding, NO pillows, NO bed frame.

The mattress is:
- A thick, plush rectangular mattress in plain white/cream fabric
- Slightly rounded/puffy edges from padding
- Viewed straight-on from the foot end — the front edge is wider (closer to us),
  the back edge narrower (further away)
- Sized and positioned to sit INSIDE the bed frame — the mattress top surface
  starts where the frame rails are, roughly 40% down the canvas
- The mattress is slightly smaller than the frame interior
- Plain fabric — no sheets, no patterns, just a clean mattress

${BED_REFERENCE}
${TRANSPARENCY}
${STYLE_D_LOCKED}
`,

  sheets: `
Illustrate ONLY white/cream SHEETS AND DUVET draped over a bed shape,
on a completely transparent background. NO pillows, NO blue runner, NO bed frame.

The sheets/duvet are:
- Crisp white/cream (#FFF8F0, #F5EDE0) hotel-quality linens
- A fluffy duvet/comforter that drapes over the sides and hangs down over the
  foot of the bed toward the viewer
- Natural soft folds and gentle wrinkles — plush and inviting
- The duvet covers the full bed area from near the headboard to past the foot
- Draping over both sides and the foot, with soft gathered edges
- NO pillows visible, NO blue accent runner — just the white/cream bedding

Sized and positioned to cover the mattress area of the bed.

${BED_REFERENCE}
${TRANSPARENCY}
${STYLE_D_LOCKED}
`,

  comforter: `
Illustrate ONLY a dusty blue ACCENT RUNNER / BED SCARF on a completely transparent
background. NO bed frame, NO sheets, NO pillows, NO mattress.

The runner is:
- A folded fabric runner in deep dusty blue (#6B8FA3)
- Draped horizontally across the bed, roughly at the halfway point between
  headboard and foot — sitting on top of the white duvet
- The runner hangs down slightly over both sides of the bed
- It's about 15-20% of the bed's length (not full width, just an accent band)
- Soft, luxurious fabric with subtle folds
- The runner appears as a horizontal band of blue

Position it at roughly 55-60% down the canvas (on the lower half of the bed area).

${BED_REFERENCE}
${TRANSPARENCY}
${STYLE_D_LOCKED}
`,

  pillows: `
Illustrate ONLY plump BED PILLOWS on a completely transparent background.
NO bed frame, NO sheets, NO blue runner, NO mattress.

The pillows are:
- 3-4 large, plump cream/white (#FFF8F0) pillows
- Arranged leaning against an invisible headboard at the top/back of the bed
- Two larger pillows in back, one or two slightly smaller ones in front
- Soft, puffy, with natural creases and shadows between them
- They sit at the TOP of the bed area, roughly 32-42% down the canvas
- Luxurious hotel-style euro and standard pillows

${BED_REFERENCE}
${TRANSPARENCY}
${STYLE_D_LOCKED}
`,
};

async function generate(name, prompt) {
  console.log(`\n🎨 Generating ${name}...`);
  const startTime = Date.now();

  const response = await client.images.generate({
    model: "gpt-image-1",
    prompt,
    n: 1,
    size: "1536x1024",
    quality: "medium",
    background: "transparent",
  });

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

const names = Object.keys(LAYERS);

try {
  // Batch of 2 at a time
  for (let i = 0; i < names.length; i += 2) {
    const batch = names.slice(i, i + 2);
    console.log(`\n── Batch ${Math.floor(i / 2) + 1}: ${batch.join(", ")} ──`);
    await Promise.all(batch.map((name) => generate(name, LAYERS[name])));
    if (i + 2 < names.length) {
      console.log("\n⏳ Waiting 15s (rate limit)...");
      await new Promise((r) => setTimeout(r, 15000));
    }
  }

  // Resize
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

  console.log("\n✅ Done! Bed layers in public/room-assets/");
  console.log("  Stack order (bottom→top): bed_frame → mattress → sheets → comforter → pillows");
} catch (err) {
  console.error("\n❌ Failed:", err.message);
  process.exit(1);
}
