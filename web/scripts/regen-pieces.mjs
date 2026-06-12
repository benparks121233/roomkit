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

const STYLE = `
STYLE SPECIFICATION — "Soft Gouache / Painterly" (follow EXACTLY):
- Medium: soft gouache or tempera illustration — visible gentle brushstrokes, creamy opaque paint with subtle texture, like a fine illustrated picture book for adults
- Lighting: soft warm morning light from the upper-left, gentle warm shadows to the lower-right
- Color palette: soft cream (#F5EDE3), warm linen (#F0E6D8), pale honey (#E8D8C0), muted sage (#DDE8D8, #8DB98F, #5E8C61), warm wood (#D4C0A8, #B8A080, #9B8A6E), soft white fabrics (#FFF8F0), muted dusty blue (#8BAAB8), warm terracotta (#C4A882)
- Line style: soft painted edges, occasional thin warm-brown (#A89580) lines, NO hard black outlines
- Texture: creamy chalky gouache, gentle brushwork, NOT slick/digital, NOT photorealistic
- Mood: dreamy, restful, blissful, serene
- CRITICAL: beautiful ILLUSTRATION — NOT a photograph, NOT a 3D render, NOT cartoonish
- Canvas: 1536×1024 pixels, landscape`.trim();

const TRANSP = `
TRANSPARENCY (critical):
- Background 100% transparent. ONLY the object is visible.
- NO shadow, NO glow, NO halo, NO white fringe. Everything around the object = fully transparent (alpha=0).
- Pixel-clean edges against transparency.`.trim();

// ROOM CAMERA: viewer stands at the front-right of the room, looking toward the back-left corner.
// Back wall runs from lower-left (closer) up to the corner at upper-center-right (farther).
// Side wall runs from that corner toward lower-right.
// Floor planks run from lower-left to upper-right.

const PIECES = {
  wall_art: `
Illustrate a SINGLE FRAMED PAINTING hanging on a wall, on a transparent background.

PERSPECTIVE (critical — match exactly):
The painting hangs on a BACK WALL that recedes from LEFT (closer to the viewer) to RIGHT (farther away).
The camera views it from a 3/4 angle — we are standing to the front-right of the wall.
So the painting appears as a SLIGHT TRAPEZOID:
- The LEFT edge of the frame is slightly TALLER (closer to us)
- The RIGHT edge is slightly SHORTER (farther from us)
- The TOP edge of the frame tilts very slightly upward from left to right (following the wall's perspective)
- This is a SUBTLE effect — maybe 3-5% perspective distortion, not dramatic

The painting:
- Simple warm honey-oak wooden frame
- Inside: a soft abstract/landscape painting in serene muted tones (pale greens, soft blues, warm creams)
- Landscape orientation (wider than tall)
- Fill roughly 50% of canvas width, centered

${TRANSP}
${STYLE}
`,

  nightstand: `
Illustrate a SMALL BEDSIDE NIGHTSTAND on a transparent background.

PERSPECTIVE (critical — match exactly):
The nightstand sits AGAINST THE BACK WALL, on the LEFT SIDE of the room.
The camera views it from the FRONT-RIGHT — we are standing to the right and slightly in front.
So we see:
- The FRONT FACE of the nightstand (facing toward us / toward the right side of the image) — this is the LARGEST visible face
- The TOP surface, seen from slightly above (~20° down)
- The LEFT SIDE is mostly hidden (against the wall) — we see just a sliver or nothing
- The RIGHT SIDE is partly visible as the nightstand angles away from us

The nightstand:
- Simple warm honey-oak wood, one drawer with round knob, four tapered legs
- Compact bedside proportions
- Fill roughly 22-25% of canvas width, centered

${TRANSP}
${STYLE}
`,

  rug: `
Illustrate a RECTANGULAR AREA RUG lying flat on the floor, on a transparent background.

PERSPECTIVE (critical — match exactly):
The rug lies on a FLOOR that recedes from the FRONT-RIGHT (near, bottom of image) toward the BACK-LEFT (far, upper area of image).
The camera looks from front-right toward back-left, slightly above (~20° down).
So the rug appears as a FORESHORTENED PARALLELOGRAM:
- The NEAR EDGE (closest to viewer, lower-right area) is the LONGEST/WIDEST
- The FAR EDGE (away from viewer, upper-left area) is SHORTER (perspective foreshortening)
- The left edge angles from lower-left toward upper-left
- The right edge angles from lower-right toward upper-center
- The overall shape tilts: the long axis runs from lower-right to upper-left
  (NOT straight horizontal, NOT straight vertical — diagonal, matching floor perspective)

The rug:
- Soft woven texture, warm neutral tones (cream and warm beige)
- Subtle tone-on-tone border or gentle stripe pattern
- Soft plush appearance, gentle fringe on the short ends
- Fill roughly 50% of canvas width, centered

${TRANSP}
${STYLE}
`,

  table_lamp: `
Illustrate a SMALL TABLE LAMP on a transparent background.

PERSPECTIVE (critical — match exactly):
The lamp sits on a nightstand AGAINST THE BACK WALL, on the LEFT SIDE of the room.
The camera views it from the FRONT-RIGHT and slightly above.
So we see:
- The front of the lampshade (facing toward us / toward right)
- The shade is slightly foreshortened — the far/left edge recedes slightly
- We look slightly down into the shade opening at the top
- The base sits on a surface that recedes toward the upper-left

The lamp:
- Warm cream or linen fabric shade, slightly tapered (wider at bottom)
- Slim turned-wood stem in warm tones
- Round base
- NO glow, NO light effect — just the physical lamp object
- Fill roughly 15% of canvas width, centered

${TRANSP}
${STYLE}
`,
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
  console.log(`  Optimized ${name}`);
}

// 2 at a time to stay under rate limit
const names = Object.keys(PIECES);
for (let i = 0; i < names.length; i += 2) {
  const batch = names.slice(i, i + 2);
  await Promise.all(batch.map(n => gen(n, PIECES[n])));
  if (i + 2 < names.length) {
    console.log("Waiting 15s for rate limit...");
    await new Promise(r => setTimeout(r, 15000));
  }
}
console.log("\nDone!");
