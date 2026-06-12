#!/usr/bin/env node
/**
 * Regenerate pieces that were destroyed by overly aggressive alpha cleanup.
 * These are the cream/white-colored pieces where the shadow filter ate into the object.
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

const PIECES = {
  bed: `
Illustrate a FULL DRESSED BED on a completely transparent background.

The bed includes (all as one combined illustration):
- A wooden headboard in warm honey-oak, gently curved top, visible wood grain and gouache brushwork
- A bed frame in matching wood with short tapered legs
- A plush mattress (mostly hidden under bedding)
- Crisp soft white/cream sheets with a gentle fold visible at the top edge
- A cozy dusty blue (#8BAAB8) comforter/duvet draped naturally over the bed,
  hanging softly over the edges, slightly rumpled and inviting
- Two plump cream/white pillows against the headboard with soft shading

Orientation: headboard faces upper-left, foot of bed faces lower-right (matching the room's 3/4 angle).
The bed should fill roughly 50-55% of the canvas width, centered in the canvas.

${TRANSPARENCY}
${STYLE_C_LOCKED}
`,

  ceiling_light: `
Illustrate a PENDANT CEILING LIGHT on a completely transparent background.

- A thin cord or chain hanging from the very top of the canvas
- A simple, elegant drum or dome shade in warm cream/linen fabric
- Simple, minimal design — not ornate
- Render ONLY the physical fixture (cord + shade). Do NOT paint any glow,
  light rays, or luminous effects. Just the object itself.

The fixture hangs from the top-center of the canvas.
The cord should start at the very top edge.
Fill roughly 15% of canvas width.

${TRANSPARENCY}
${STYLE_C_LOCKED}
`,

  table_lamp: `
Illustrate a SMALL TABLE LAMP on a completely transparent background.

- A warm cream or linen fabric shade, slightly tapered (wider at bottom)
- A slim turned-wood or ceramic stem in warm tones
- A round or oval base
- Render ONLY the physical lamp (shade + stem + base). Do NOT paint any glow,
  light halo, bloom, or luminous cloud around the shade. Just the solid object.

Orientation: 3/4 view matching the room perspective.
Fill roughly 12-15% of canvas width, centered in the canvas.

${TRANSPARENCY}
${STYLE_C_LOCKED}
`,

  floor_lamp: `
Illustrate a TALL STANDING FLOOR LAMP on a completely transparent background.

- A tall slim stem/pole in warm brass or wood tone
- A simple drum or angled shade in warm cream/linen fabric at the top
- A round weighted base at the bottom
- Render ONLY the physical lamp (shade + stem + base). Do NOT paint any glow,
  light halo, bloom, or luminous cloud around the shade. Just the solid object.

Orientation: 3/4 view matching the room perspective.
Fill roughly 12-15% of canvas width and about 55-60% of canvas height, centered.

${TRANSPARENCY}
${STYLE_C_LOCKED}
`,

  rug: `
Illustrate a RECTANGULAR AREA RUG on a completely transparent background.

- Soft woven texture — warm neutral tones, cream and warm beige with subtle pattern
  (simple border or very subtle tone-on-tone geometric/stripe pattern)
- Soft, plush appearance with gentle fringe or clean edges
- Rectangular, sized to go under a bed

Orientation: seen from above at 3/4 angle — foreshortened, the far edge narrower than
the near edge, matching the room's floor perspective. The rug lies FLAT on the floor plane.
Fill roughly 45-50% of canvas width, centered.

${TRANSPARENCY}
${STYLE_C_LOCKED}
`,

  curtains: `
Illustrate a PAIR OF CURTAINS / WINDOW DRAPES on a completely transparent background.

- Two soft fabric panels in warm cream or linen tone, one on each side
- Gently gathered/draped, hanging from near the top — natural soft folds
- Between the curtain panels: leave an open gap (transparent)
- The panels should frame a window-sized opening
- Fabric has soft, flowing quality with visible painted texture

Orientation: front-facing with subtle 3/4 perspective (matching back wall angle).
Fill roughly 30-35% of canvas width, centered. Height: roughly 50% of canvas.

${TRANSPARENCY}
${STYLE_C_LOCKED}
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

const pieceNames = Object.keys(PIECES);

try {
  // Generate in batches of 2 (rate limit: 5/min)
  for (let i = 0; i < pieceNames.length; i += 2) {
    const batch = pieceNames.slice(i, i + 2);
    console.log(`\n── Batch ${Math.floor(i / 2) + 1}: ${batch.join(", ")} ──`);
    await Promise.all(batch.map((name) => generate(name, PIECES[name])));
    if (i + 2 < pieceNames.length) {
      console.log("\n⏳ Waiting 15s (rate limit)...");
      await new Promise((r) => setTimeout(r, 15000));
    }
  }
  optimizePngs(pieceNames);
  console.log("\n✅ Done! Regenerated:", pieceNames.join(", "));
} catch (err) {
  console.error("\n❌ Failed:", err.message);
  process.exit(1);
}
