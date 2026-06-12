#!/usr/bin/env node
/**
 * Regenerate ONLY the throw blanket with a more explicit standalone prompt.
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

const STYLE_C_LOCKED = `
STYLE SPECIFICATION — "Soft Gouache / Painterly" (follow EXACTLY):
- Medium: soft gouache or tempera illustration — visible gentle brushstrokes,
  creamy opaque paint with subtle texture, like a fine illustrated picture book for adults
- Perspective: 3/4 view of a bedroom, camera slightly above eye level (~20° down),
  single vanishing point toward the back-left corner of the room
- Lighting: soft warm morning light coming from the upper-left (from a window on the back wall),
  gentle cast shadows falling to the lower-right, shadows are warm tones (NOT grey/cold)
- Color palette: warm and gentle —
  soft cream (#F5EDE3), warm linen (#F0E6D8), pale honey (#E8D8C0),
  soft dusty rose undertones (#F2E4DE), muted sage greens (#DDE8D8, #8DB98F, #5E8C61),
  warm wood tones (#D4C0A8, #B8A080, #9B8A6E),
  soft white fabrics (#FFF8F0, #F5EDE0),
  muted dusty blue for textile accents (#8BAAB8, #7A9DAD),
  warm terracotta (#C4A882)
- Line style: soft painted edges — shapes defined by color meeting color,
  occasional thin warm-brown (#A89580) painted lines for detail,
  NO hard black outlines, NO vector-sharp edges
- Texture: creamy, slightly chalky gouache texture, visible but gentle brushwork,
  paint has body and warmth, NOT slick/digital, NOT photorealistic
- Mood: dreamy, restful, blissful, serene — peaceful morning light, hand-made quality
- CRITICAL: This is a beautiful ILLUSTRATION — NOT a photograph, NOT a 3D render,
  NOT hyper-realistic, NOT cartoonish/childish. Elegant, serene, painted.
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

const PROMPT = `
Illustrate ONLY a folded/draped THROW BLANKET by itself, on a completely transparent background.

CRITICAL — THIS IS JUST THE BLANKET. DO NOT DRAW A BED. DO NOT DRAW ANY FURNITURE.
DO NOT DRAW PILLOWS, SHEETS, MATTRESS, HEADBOARD, OR ANY OTHER OBJECT.
ONLY THE THROW BLANKET FABRIC ITSELF — NOTHING ELSE.

The throw blanket is:
- A cozy knit or woven throw in warm dusty rose (#E8C8B8) or soft terracotta accent color
- Casually folded and draped as if it was just tossed — rumpled, relaxed, organic shape
- Oriented diagonally, angled roughly 10-15° clockwise (upper-left to lower-right),
  as if draped across the foot of a bed seen from a 3/4 angle
- Soft, tactile texture with visible knit or weave pattern
- Fringed or tasseled edges visible on one or two ends
- The blanket is roughly rectangular when unfolded, now loosely folded in half lengthwise
  with natural draping folds

Fill roughly 30% of canvas width, centered in the canvas.
The blanket should look like it's resting on a flat surface (but do NOT draw the surface).

${TRANSPARENCY}
${STYLE_C_LOCKED}
`.trim();

async function generate() {
  console.log("\n🎨 Generating throw_blanket...");
  const startTime = Date.now();

  const response = await client.images.generate({
    model: "gpt-image-1",
    prompt: PROMPT,
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

  const outPath = path.join(OUT_DIR, "throw_blanket.png");
  fs.writeFileSync(outPath, buffer);
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  const sizeKB = (buffer.length / 1024).toFixed(0);
  console.log(`  ✅ throw_blanket.png (${sizeKB} KB, ${elapsed}s)`);

  // Resize
  try {
    execSync(`sips --resampleWidth 1024 "${outPath}" 2>/dev/null`, { stdio: "pipe" });
    const afterKB = (fs.statSync(outPath).size / 1024).toFixed(0);
    console.log(`  📦 Resized to 1024w: ${afterKB} KB`);
  } catch {
    console.log("  ⚠️ sips resize failed");
  }
}

try {
  await generate();
  // Clean shadow halos
  console.log("\n🧹 Cleaning shadow halos...");
  execSync(`python3 scripts/clean-alpha.py --threshold 140 public/room-assets/throw_blanket.png`, {
    stdio: "inherit",
    cwd: path.resolve(__dirname, ".."),
  });
  console.log("\n✅ Done!");
} catch (err) {
  console.error("\n❌ Failed:", err.message);
  process.exit(1);
}
