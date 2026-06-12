import OpenAI from "openai";
import fs from "fs";
import { execSync } from "child_process";

const envContent = fs.readFileSync("/Users/benny/roomkit/.env", "utf-8");
for (const line of envContent.split("\n")) {
  const m = line.match(/^([^#=]+)=(.*)$/);
  if (m) process.env[m[1].trim()] = m[2].trim();
}
const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
const OUT = "/Users/benny/roomkit/web/public/room-assets";

const STYLE = `STYLE — Soft Gouache / Painterly (follow EXACTLY):
- Medium: soft gouache or tempera illustration, visible gentle brushstrokes, creamy opaque paint, like a fine illustrated picture book for adults
- Lighting: soft warm morning light from upper-left, gentle warm shadows to lower-right
- Palette: soft cream (#F5EDE3), warm linen (#F0E6D8), pale honey (#E8D8C0), muted sage (#DDE8D8, #8DB98F, #5E8C61), warm wood (#D4C0A8, #B8A080, #9B8A6E), soft white fabrics (#FFF8F0), muted dusty blue (#8BAAB8), warm terracotta (#C4A882)
- Soft painted edges, occasional thin warm-brown lines, NO hard black outlines
- Creamy chalky gouache texture, NOT slick/digital, NOT photorealistic
- Dreamy, restful, serene. Beautiful ILLUSTRATION, not a photo.
- Canvas: 1536x1024 pixels, landscape`;

const NO_SHADOW = `TRANSPARENCY — READ EVERY WORD:
The background is 100% transparent. ONLY the object itself has visible pixels.
DO NOT PAINT ANY SHADOW — no contact shadow, no drop shadow, no cast shadow, no dark area under the object, no light area under the object. The space beneath the legs/base/bottom of the object must be FULLY TRANSPARENT (alpha = 0).
DO NOT PAINT ANY GLOW or halo or white fringe or cream fog around the object.
If you feel the urge to ground the object with a shadow — RESIST. Leave it transparent.
ONLY the physical object. Nothing else. Zero extra pixels.`;

const PIECES = {
  wall_art: `Illustrate a SINGLE FRAMED PAINTING on a transparent background.

ANGLE (critical): The painting hangs on a wall that is NEARLY FACING THE VIEWER — almost flat/front-on. Draw it as an ALMOST FLAT rectangle with only the TINIEST hint of perspective — maybe the right edge is 2-3% shorter than the left, barely perceptible. This is NOT a dramatic 3/4 view. The painting is nearly square-on to the camera. Think: you're standing in a room looking at a painting on the wall directly in front of you, maybe shifted very slightly to one side.

The painting:
- Simple warm honey-oak wooden frame, not too thick
- Inside: a soft abstract/landscape in serene muted tones (pale greens, soft blues, warm creams)
- Landscape orientation (wider than tall)
- Fill roughly 50% of canvas width, centered

${NO_SHADOW}
${STYLE}`,

  nightstand: `Illustrate a SMALL BEDSIDE NIGHTSTAND on a transparent background.

ANGLE: We view the nightstand from slightly to the RIGHT and slightly above (~20° down). We see:
- The FRONT FACE is the main visible face (facing us). The drawer and knob are clearly visible on this face.
- The TOP surface is visible from above.
- We see a SLIVER of the RIGHT SIDE — but the front face dominates.
- The left side is NOT visible (it's turned away).
Think: the nightstand's front faces toward 4-5 o'clock on a clock face (toward the viewer who stands at the front-right).

The nightstand: simple warm honey-oak wood, one drawer with round knob, four tapered legs. Compact.
Fill roughly 25% of canvas width, centered.

${NO_SHADOW}
${STYLE}`,

  plant: `Illustrate a POTTED PLANT on a transparent background.

ANGLE: Viewed from slightly to the right and slightly above. The pot and foliage are centered.

The plant:
- A warm terracotta pot, simple rounded shape
- Lush green foliage — soft sage and muted greens (#8DB98F, #5E8C61), leafy, natural variety in leaf shapes
- Medium floor plant size

Fill roughly 20% of canvas width, centered.

${NO_SHADOW}
${STYLE}`,

  throw_blanket: `Illustrate a THROW BLANKET casually draped across the FOOT of a bed, on a transparent background.

ANGLE AND ORIENTATION (critical): The blanket drapes ACROSS a bed that runs from the UPPER-LEFT (headboard) to the LOWER-RIGHT (foot). So the throw lies roughly PERPENDICULAR to this — it drapes from the UPPER-RIGHT to the LOWER-LEFT across the bed's foot end. The fringe or tasseled edge hangs down toward the LOWER-LEFT. The fold runs diagonally, matching the bed angle.

DO NOT draw the blanket as a horizontal rectangle. It should be a DIAGONAL drape from upper-right to lower-left.

The blanket: cozy knit/woven throw in warm dusty rose (#E8C8B8) or soft terracotta. Casually folded, soft tactile texture, fringed edges. Fill roughly 30% of canvas width, centered.

${NO_SHADOW}
${STYLE}`,
};

async function gen(name, prompt) {
  console.log("Generating " + name + "...");
  const t = Date.now();
  const r = await client.images.generate({
    model: "gpt-image-1", prompt, n: 1, size: "1536x1024", quality: "medium", background: "transparent"
  });
  const buf = Buffer.from(r.data[0].b64_json, "base64");
  const p = `${OUT}/${name}.png`;
  fs.writeFileSync(p, buf);
  console.log(`  Done ${name} (${(buf.length/1024).toFixed(0)} KB, ${((Date.now()-t)/1000).toFixed(1)}s)`);
  execSync(`sips --resampleWidth 1024 "${p}" 2>/dev/null`, { stdio: "pipe" });
  console.log(`  Optimized`);
}

const names = Object.keys(PIECES);
for (let i = 0; i < names.length; i += 2) {
  const batch = names.slice(i, i + 2);
  await Promise.all(batch.map(n => gen(n, PIECES[n])));
  if (i + 2 < names.length) {
    console.log("Waiting 15s...");
    await new Promise(r => setTimeout(r, 15000));
  }
}
console.log("\nDone!");
