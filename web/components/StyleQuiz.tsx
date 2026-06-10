"use client";

// Intake questionnaire — visual narrowing: wide room → vignette → color → macro → macro.
// STYLE (Q1-Q7): core → mood → palette → materials → texture (conditional) → shape → density
// BRIDGE (Q8): transition card
// INTERESTS (Q9-Q11): categories → sub-options → free text
//
// Q1-Q3 images are room-specific (/quiz/{roomType}/core_*.jpg, mood_*.jpg, palette_*.jpg).
// Q4-Q5 images are shared (/quiz/material_*.jpg, texture_*.jpg).
// Missing images fall back to color swatches.
//
// Assembles a QuizOutput object; style.description feeds the existing /design API.

import Image from "next/image";
import { useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface QuizOutput {
  style: {
    core: string;
    mood: string;
    palette: string;
    materials: string[];
    texture: string;
    shape: string;
    density: string;
    description: string;
  };
  interests: { category: string; tags: string[] }[];
}

interface QuizOption {
  key: string;
  label: string;
  description?: string;
  swatches: string[];
  image?: string;       // filename only, e.g. "core_japandi.jpg" — prefix built at render
  icon?: string;        // emoji for interest chips
}

type SelectMode = "single" | "multi";

interface QuizStepDef {
  id: string;
  question: string;
  hint?: string;
  selectMode: SelectMode;
  maxSelect?: number;
  options: QuizOption[];
  layout?: "cards" | "chips" | "text-cards" | "bridge" | "textarea";
  imageDir?: "room" | "shared"; // "room" = /quiz/{roomType}/, "shared" = /quiz/
}

// ---------------------------------------------------------------------------
// Quiz data — STYLE questions
// ---------------------------------------------------------------------------

const Q_CORE: QuizStepDef = {
  id: "core",
  question: "What\u2019s your aesthetic?",
  selectMode: "single",
  layout: "cards",
  imageDir: "room",
  options: [
    { key: "cottagecore",   label: "Cottagecore",   description: "Soft florals, vintage wood, pastoral warmth",        swatches: ["#F5F0E8", "#D4A9A1"], image: "core_cottagecore.jpg" },
    { key: "dark_academia", label: "Dark Academia", description: "Rich wood, leather, deep tones, scholarly warmth",   swatches: ["#3B2F2F", "#8B6F47"], image: "core_dark_academia.jpg" },
    { key: "japandi",       label: "Japandi",       description: "Minimal wood, clean lines, calm intentionality",     swatches: ["#E8E2D8", "#B8A99A"], image: "core_japandi.jpg" },
    { key: "coastal",       label: "Coastal",       description: "White, rattan, blue accents, breezy natural light",  swatches: ["#FFFFFF", "#A8C4B8"], image: "core_coastal.jpg" },
    { key: "industrial",    label: "Industrial",    description: "Exposed metal, concrete, dark wood, raw utility",    swatches: ["#3A3A3A", "#6B6B6B"], image: "core_industrial.jpg" },
    { key: "quiet_luxury",  label: "Quiet Luxury",  description: "Cream, marble, brass, understated old-money calm",   swatches: ["#F5F0E8", "#C4A882"], image: "core_quiet_luxury.jpg" },
    { key: "sports_den",    label: "Sports Den",    description: "Dark leather, warm glow, bar cart, lounge energy",   swatches: ["#2A2A2A", "#8B6F47"], image: "core_sports_den.jpg" },
    { key: "city_modern",   label: "City Modern",   description: "Sleek high-rise, glass, monochrome, one bold accent", swatches: ["#3A3A3A", "#FFFFFF"], image: "core_city_modern.jpg" },
    { key: "ski_lodge",     label: "Ski Lodge",     description: "Stone hearth, timber beams, wool, faux fur, alpine warmth", swatches: ["#8B6F47", "#D4B896"], image: "core_ski_lodge.jpg" },
  ],
};

const Q_MOOD: QuizStepDef = {
  id: "mood",
  question: "How should the room feel?",
  selectMode: "single",
  layout: "cards",
  imageDir: "room",
  options: [
    { key: "soft_still",       label: "Soft & Still",       description: "Quiet, contemplative, low-energy calm",  swatches: ["#E8E2D8", "#D4CFC6"], image: "mood_soft_still.jpg" },
    { key: "bright_airy",      label: "Bright & Airy",      description: "Light-filled, cheerful, uplifting",      swatches: ["#FFFFFF", "#F5F0E8"], image: "mood_bright_airy.jpg" },
    { key: "warm_cozy",        label: "Warm & Cozy",        description: "Intimate, enveloping, inviting warmth",  swatches: ["#C4A882", "#8B6F47"], image: "mood_warm_cozy.jpg" },
    { key: "bold_confident",   label: "Bold & Confident",   description: "Saturated, decisive, statement-making",  swatches: ["#8B1A2B", "#C89B3C"], image: "mood_bold_confident.jpg" },
    { key: "moody_deep",       label: "Moody & Deep",       description: "Dark, atmospheric, rich depth",          swatches: ["#2A2A2A", "#4A3A2A"], image: "mood_moody_deep.jpg" },
    { key: "playful_eclectic", label: "Playful & Eclectic", description: "Vibrant energy, mixed patterns, fun",    swatches: ["#C67B5C", "#6B7C4E"], image: "mood_playful_eclectic.jpg" },
  ],
};

// Mood ordering by core — best-fit first
const MOOD_ORDER: Record<string, string[]> = {
  cottagecore:     ["warm_cozy", "soft_still", "bright_airy", "playful_eclectic", "bold_confident", "moody_deep"],
  dark_academia:   ["moody_deep", "warm_cozy", "bold_confident", "soft_still", "playful_eclectic", "bright_airy"],
  japandi:         ["soft_still", "bright_airy", "warm_cozy", "moody_deep", "bold_confident", "playful_eclectic"],
  coastal:         ["bright_airy", "soft_still", "warm_cozy", "playful_eclectic", "bold_confident", "moody_deep"],
  grandmillennial: ["warm_cozy", "bold_confident", "playful_eclectic", "soft_still", "bright_airy", "moody_deep"],
  industrial:      ["moody_deep", "bold_confident", "warm_cozy", "playful_eclectic", "soft_still", "bright_airy"],
};

const Q_PALETTE: QuizStepDef = {
  id: "palette",
  question: "Which colors feel like home?",
  selectMode: "single",
  layout: "cards",
  imageDir: "room",
  options: [
    { key: "warm_neutrals", label: "Warm Neutrals", swatches: ["#F5F0E8", "#C4A882", "#C67B5C"], image: "palette_warm_neutrals.jpg" },
    { key: "earthy_rich",   label: "Earthy & Rich",  swatches: ["#5E4B3B", "#C89B3C", "#6B7C4E"], image: "palette_earthy_rich.jpg" },
    { key: "jewel_tones",   label: "Jewel Tones",    swatches: ["#1A5E5E", "#8B1A2B", "#C89B3C"], image: "palette_jewel_tones.jpg" },
    { key: "coastal_soft",  label: "Coastal Soft",    swatches: ["#FFFFFF", "#A8C4B8", "#D4C5A9"], image: "palette_coastal_soft.jpg" },
    { key: "dark_moody",    label: "Dark & Moody",    swatches: ["#3A3A3A", "#5E4B3B", "#C89B3C"], image: "palette_dark_moody.jpg" },
    { key: "blush_sage",    label: "Blush & Sage",    swatches: ["#D4A9A1", "#9CAF88", "#F5F0E8"], image: "palette_blush_sage.jpg" },
  ],
};

// Palette ordering by core — best-fit first
const PALETTE_ORDER: Record<string, string[]> = {
  cottagecore:     ["blush_sage", "warm_neutrals", "coastal_soft", "earthy_rich", "jewel_tones", "dark_moody"],
  dark_academia:   ["dark_moody", "earthy_rich", "jewel_tones", "warm_neutrals", "blush_sage", "coastal_soft"],
  japandi:         ["warm_neutrals", "coastal_soft", "blush_sage", "dark_moody", "earthy_rich", "jewel_tones"],
  coastal:         ["coastal_soft", "warm_neutrals", "blush_sage", "earthy_rich", "jewel_tones", "dark_moody"],
  grandmillennial: ["blush_sage", "jewel_tones", "warm_neutrals", "earthy_rich", "coastal_soft", "dark_moody"],
  industrial:      ["dark_moody", "earthy_rich", "warm_neutrals", "jewel_tones", "coastal_soft", "blush_sage"],
};

const Q_MATERIALS: QuizStepDef = {
  id: "materials",
  question: "What materials are you drawn to?",
  hint: "Pick up to 2",
  selectMode: "multi",
  maxSelect: 2,
  layout: "cards",
  imageDir: "shared",
  options: [
    { key: "wood_linen",     label: "Natural Wood & Linen", swatches: ["#D4B896"], image: "material_wood_linen.jpg" },
    { key: "walnut_leather", label: "Walnut & Leather",     swatches: ["#5E4B3B"], image: "material_walnut_leather.jpg" },
    { key: "velvet_brass",   label: "Velvet & Brass",       swatches: ["#8B1A2B"], image: "material_velvet_brass.jpg" },
    { key: "rattan_cotton",  label: "Rattan & Cotton",      swatches: ["#D4C5A9"], image: "material_rattan_cotton.jpg" },
    { key: "metal_concrete", label: "Metal & Concrete",     swatches: ["#7A7A7A"], image: "material_metal_concrete.jpg" },
  ],
};

// Texture options by core group
const TEXTURE_CALM_AIRY: QuizStepDef = {
  id: "texture",
  question: "How do you feel about texture?",
  selectMode: "single",
  layout: "cards",
  imageDir: "shared",
  options: [
    { key: "sheer_light",  label: "Light and sheer",  description: "Linen curtains, cotton throws",   swatches: ["#F5F0E8"], image: "texture_sheer_light.jpg" },
    { key: "soft_nubby",   label: "Soft and nubby",   description: "Boucle, chunky knits",            swatches: ["#E8E0D4"], image: "texture_soft_nubby.jpg" },
    { key: "smooth_clean", label: "Smooth and clean",  description: "Flat weaves, matte surfaces",     swatches: ["#D4D0CA"], image: "texture_smooth_clean.jpg" },
  ],
};

const TEXTURE_RETRO_RICH: QuizStepDef = {
  id: "texture",
  question: "What kind of texture are you into?",
  selectMode: "single",
  layout: "cards",
  imageDir: "shared",
  options: [
    { key: "rich_tactile",     label: "Rich and tactile",     description: "Velvet, tufting, deep pile",      swatches: ["#5E4B3B"], image: "texture_rich_tactile.jpg" },
    { key: "woven_layered",    label: "Woven and layered",    description: "Kilims, macrame, mixed textiles", swatches: ["#C89B3C"], image: "texture_woven_layered.jpg" },
    { key: "polished_refined", label: "Polished and refined", description: "Leather, lacquer, silk",          swatches: ["#8B1A2B"], image: "texture_polished_refined.jpg" },
  ],
};

const TEXTURE_EDGY: QuizStepDef = {
  id: "texture",
  question: "What\u2019s your texture?",
  selectMode: "single",
  layout: "cards",
  imageDir: "shared",
  options: [
    { key: "raw_industrial", label: "Raw and industrial", description: "Exposed metal, concrete, distressed wood", swatches: ["#6B6B6B"], image: "texture_raw_industrial.jpg" },
    { key: "sleek_minimal",  label: "Sleek and minimal",  description: "Matte black, flat surfaces, clean edges", swatches: ["#3A3A3A"], image: "texture_sleek_minimal.jpg" },
    { key: "mixed_grit",     label: "Mixed grit",         description: "Some rough, some polished",               swatches: ["#5E4B3B"], image: "texture_mixed_grit.jpg" },
  ],
};

const Q_SHAPE: QuizStepDef = {
  id: "shape",
  question: "Straight lines or soft curves?",
  selectMode: "single",
  layout: "text-cards",
  options: [
    { key: "clean_straight", label: "Clean, straight lines",     swatches: [] },
    { key: "organic_curved", label: "Organic curves and arches", swatches: [] },
    { key: "mixed",          label: "A mix of both",             swatches: [] },
  ],
};

const Q_DENSITY: QuizStepDef = {
  id: "density",
  question: "How much stuff do you want in the room?",
  selectMode: "single",
  layout: "text-cards",
  options: [
    { key: "minimal",  label: "Keep it minimal", description: "Just the essentials, lots of breathing room", swatches: [] },
    { key: "balanced", label: "Balanced",         description: "A full room, but not cluttered",              swatches: [] },
    { key: "layered",  label: "Layer it up",      description: "I like a lived-in, collected feel",           swatches: [] },
  ],
};

const Q_BRIDGE: QuizStepDef = {
  id: "bridge",
  question: "Almost done \u2014 tell us what you\u2019re into.",
  hint: "These don\u2019t affect your furniture \u2014 they\u2019ll help us pick art, prints, and decor that actually feel like you.",
  selectMode: "single",
  layout: "bridge",
  options: [],
};

const Q_INTERESTS: QuizStepDef = {
  id: "interests",
  question: "Pick anything that\u2019s your thing.",
  selectMode: "multi",
  layout: "chips",
  options: [
    { key: "music",    label: "Music",             swatches: [], icon: "\ud83c\udfb5" },
    { key: "sports",   label: "Sports",            swatches: [], icon: "\u26bd" },
    { key: "plants",   label: "Plants & greenery", swatches: [], icon: "\ud83c\udf3f" },
    { key: "travel",   label: "Travel",            swatches: [], icon: "\ud83d\uddfa\ufe0f" },
    { key: "art_film", label: "Art & film",        swatches: [], icon: "\ud83c\udfac" },
    { key: "books",    label: "Books & reading",   swatches: [], icon: "\ud83d\udcda" },
    { key: "gaming",   label: "Gaming",            swatches: [], icon: "\ud83c\udfae" },
  ],
};

// Interest sub-options per category
interface SubOption { label: string; tag: string }

const INTEREST_SUBS: Record<string, SubOption[]> = {
  music: [
    { label: "Vinyl & records",        tag: "vinyl" },
    { label: "Concert & band posters", tag: "concert_posters" },
    { label: "Instruments on display", tag: "instruments" },
  ],
  sports: [
    { label: "Team gear & jerseys",    tag: "team_gear" },
    { label: "Athletic / action art",  tag: "athletic_art" },
    { label: "Basketball",             tag: "basketball" },
    { label: "Football",               tag: "football" },
    { label: "Soccer",                 tag: "soccer" },
    { label: "Baseball",               tag: "baseball" },
    { label: "Hockey",                 tag: "hockey" },
    { label: "Tennis",                  tag: "tennis" },
    { label: "Golf",                    tag: "golf" },
  ],
  plants: [
    { label: "Just a couple",  tag: "plants_minimal" },
    { label: "A nice amount",  tag: "plants_some" },
    { label: "Full jungle",    tag: "plants_lots" },
  ],
  travel: [
    { label: "Maps & globes",          tag: "maps_globes" },
    { label: "Destination prints",     tag: "destination_prints" },
    { label: "Souvenirs & artifacts",  tag: "souvenirs" },
  ],
  art_film: [
    { label: "Movie posters",             tag: "movie_posters" },
    { label: "Gallery / fine art prints",  tag: "gallery_prints" },
    { label: "Photography",               tag: "photography" },
  ],
  books: [
    { label: "Open shelving & stacks",   tag: "open_shelving" },
    { label: "Literary prints & quotes", tag: "literary_prints" },
  ],
  gaming: [
    { label: "Neon / LED accents",           tag: "neon_led" },
    { label: "Gaming art & prints",          tag: "gaming_art" },
    { label: "Display shelving for figures", tag: "display_figures" },
  ],
};

const Q_SUBS: QuizStepDef = {
  id: "interest_details",
  question: "Tell us a bit more.",
  selectMode: "multi",
  layout: "chips",
  options: [],
};

const Q_FREETEXT: QuizStepDef = {
  id: "freetext",
  question: "Anything else we should know?",
  hint: "Totally optional.",
  selectMode: "single",
  layout: "textarea",
  options: [],
};

// ---------------------------------------------------------------------------
// Style description assembly — grammatical full sentences
// ---------------------------------------------------------------------------

const CORE_PHRASES: Record<string, string> = {
  cottagecore:     "cottagecore",
  dark_academia:   "dark academia",
  japandi:         "japandi",
  coastal:         "coastal",
  grandmillennial: "grandmillennial",
  industrial:      "industrial",
};

const MOOD_PHRASES: Record<string, string> = {
  soft_still:       "soft and still, with a quiet contemplative energy",
  bright_airy:      "bright and airy, with plenty of natural light",
  warm_cozy:        "warm and cozy, intimate and enveloping",
  bold_confident:   "bold and confident, with saturated decisive tones",
  moody_deep:       "moody and atmospheric, with rich depth",
  playful_eclectic: "playful and eclectic, with vibrant mixed energy",
};

const MATERIAL_PHRASES: Record<string, string> = {
  wood_linen:     "natural wood and linen",
  walnut_leather: "walnut and leather",
  velvet_brass:   "velvet and brass accents",
  rattan_cotton:  "rattan and cotton",
  metal_concrete: "metal and concrete",
};

const PALETTE_PHRASES: Record<string, string> = {
  warm_neutrals: "in warm neutrals with cream, oak, and terracotta accents",
  earthy_rich:   "in earthy tones with walnut, mustard, and olive",
  jewel_tones:   "in jewel tones with deep teal, burgundy, and gold",
  coastal_soft:  "in coastal tones with white, seafoam, and sand",
  dark_moody:    "in dark tones with charcoal, dark wood, and warm amber",
  blush_sage:    "in soft blush and sage with dusty pink, green, and cream",
};

const TEXTURE_PHRASES: Record<string, string> = {
  sheer_light:      "I like light, sheer textures \u2014 linen curtains, cotton throws.",
  soft_nubby:       "I\u2019m drawn to soft, nubby textures like boucle and chunky knits.",
  smooth_clean:     "I prefer smooth, clean surfaces \u2014 flat weaves and matte finishes.",
  rich_tactile:     "I love rich, tactile textures \u2014 velvet, tufting, deep pile.",
  woven_layered:    "I like woven, layered textiles \u2014 kilims, macrame, mixed patterns.",
  polished_refined: "I prefer polished finishes \u2014 leather, lacquer, silk.",
  raw_industrial:   "I like raw textures \u2014 exposed metal, concrete, distressed wood.",
  sleek_minimal:    "I prefer sleek, minimal surfaces \u2014 matte black, clean edges.",
  mixed_grit:       "I like a mix of rough and polished textures.",
};

const SHAPE_PHRASES: Record<string, string> = {
  clean_straight: "I lean toward clean, straight lines.",
  organic_curved: "I prefer organic curves and arches.",
  mixed:          "I like a mix of straight lines and soft curves.",
};

const DENSITY_PHRASES: Record<string, string> = {
  minimal:  "Keep it minimal \u2014 just the essentials, lots of breathing room.",
  balanced: "I want a full room, but not cluttered.",
  layered:  "I like a layered, lived-in, collected feel.",
};

function assembleDescription(
  core: string,
  roomType: string,
  mood: string,
  materials: string[],
  palette: string,
  texture: string,
  shape: string,
  density: string,
  freeText: string,
): string {
  const corePhrase = CORE_PHRASES[core] ?? core;
  const moodPhrase = MOOD_PHRASES[mood] ?? mood;
  const matPhrase = materials.map((m) => MATERIAL_PHRASES[m] ?? m).join(" and ");
  const palPhrase = PALETTE_PHRASES[palette] ?? palette;
  const texSentence = TEXTURE_PHRASES[texture] ?? "";
  const shapeSentence = SHAPE_PHRASES[shape] ?? "";
  const densSentence = DENSITY_PHRASES[density] ?? "";

  const roomLabel = roomType.replace(/_/g, " ");
  let desc = `I want a ${corePhrase} ${roomLabel} \u2014 ${moodPhrase}, ${palPhrase}.`;
  if (matPhrase) desc += ` I\u2019m drawn to ${matPhrase}.`;
  if (texSentence) desc += ` ${texSentence}`;
  if (shapeSentence) desc += ` ${shapeSentence}`;
  if (densSentence) desc += ` ${densSentence}`;
  if (freeText.trim()) desc += ` ${freeText.trim()}`;
  return desc;
}

// Summary labels for the completion pill
const CORE_LABELS: Record<string, string> = {
  cottagecore: "Cottagecore", dark_academia: "Dark Academia", japandi: "Japandi",
  coastal: "Coastal", grandmillennial: "Grandmillennial", industrial: "Industrial",
};

const MOOD_LABELS: Record<string, string> = {
  soft_still: "Soft & Still", bright_airy: "Bright & Airy",
  warm_cozy: "Warm & Cozy", bold_confident: "Bold & Confident",
  moody_deep: "Moody & Deep", playful_eclectic: "Playful & Eclectic",
};

const PALETTE_LABELS: Record<string, string> = {
  warm_neutrals: "Warm Neutrals", earthy_rich: "Earthy & Rich",
  jewel_tones: "Jewel Tones", coastal_soft: "Coastal Soft",
  dark_moody: "Dark & Moody", blush_sage: "Blush & Sage",
};

function buildSummary(core: string, mood: string, palette: string): string {
  return [CORE_LABELS[core], MOOD_LABELS[mood], PALETTE_LABELS[palette]].filter(Boolean).join(" \u00b7 ");
}

// ---------------------------------------------------------------------------
// Image card with swatch fallback
// ---------------------------------------------------------------------------

function QuizImageCard({
  option,
  selected,
  onClick,
  imagePrefix,
}: {
  option: QuizOption;
  selected: boolean;
  onClick: () => void;
  imagePrefix: string;
}) {
  const [imgFailed, setImgFailed] = useState(false);
  const hasImage = option.image && !imgFailed;

  return (
    <button
      type="button"
      className={`quiz-card ${selected ? "selected" : ""}`}
      onClick={onClick}
    >
      <div className="quiz-card-visual">
        {hasImage ? (
          <Image
            src={`${imagePrefix}${option.image}`}
            alt={option.label}
            width={280}
            height={180}
            style={{ objectFit: "cover", width: "100%", height: "100%" }}
            onError={() => setImgFailed(true)}
          />
        ) : (
          <SwatchFallback colors={option.swatches} />
        )}
      </div>
      <div className="quiz-card-body">
        <span className="quiz-card-label">{option.label}</span>
        {option.description && (
          <span className="quiz-card-desc">{option.description}</span>
        )}
      </div>
    </button>
  );
}

function SwatchFallback({ colors }: { colors: string[] }) {
  if (colors.length === 0) return <div className="swatch-empty" />;
  if (colors.length === 1) {
    return <div className="swatch-fill" style={{ background: colors[0] }} />;
  }
  return (
    <div className="swatch-multi">
      {colors.map((c, i) => (
        <div key={i} className="swatch-multi-seg" style={{ background: c }} />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Text card (no image, just label + optional description)
// ---------------------------------------------------------------------------

function TextCard({
  option,
  selected,
  onClick,
}: {
  option: QuizOption;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`quiz-option ${selected ? "selected" : ""}`}
      onClick={onClick}
    >
      <span className="quiz-option-label">{option.label}</span>
      {option.description && (
        <span className="quiz-option-desc">{option.description}</span>
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  roomType: string;
  onComplete: (output: QuizOutput, summary: string) => void;
}

export default function StyleQuiz({ roomType, onComplete }: Props) {
  // Style answers
  const [core, setCore] = useState("");
  const [mood, setMood] = useState("");
  const [palette, setPalette] = useState("");
  const [materials, setMaterials] = useState<string[]>([]);
  const [texture, setTexture] = useState("");
  const [shape, setShape] = useState("");
  const [density, setDensity] = useState("");

  // Interest answers
  const [interests, setInterests] = useState<string[]>([]);
  const [interestTags, setInterestTags] = useState<Record<string, string[]>>({});
  const [freeText, setFreeText] = useState("");

  const [stepIndex, setStepIndex] = useState(0);

  // Build steps array dynamically (texture depends on core)
  function getSteps(): QuizStepDef[] {
    let textureStep = TEXTURE_CALM_AIRY;
    if (core === "dark_academia" || core === "grandmillennial") textureStep = TEXTURE_RETRO_RICH;
    else if (core === "industrial") textureStep = TEXTURE_EDGY;

    return [
      Q_CORE,         // 0
      Q_MOOD,         // 1 — reordered by core
      Q_PALETTE,      // 2 — reordered by core
      Q_MATERIALS,    // 3
      textureStep,    // 4 — conditional options
      Q_SHAPE,        // 5
      Q_DENSITY,      // 6
      Q_BRIDGE,       // 7
      Q_INTERESTS,    // 8
      Q_SUBS,         // 9
      Q_FREETEXT,     // 10
    ];
  }

  const steps = getSteps();
  const totalSteps = steps.length;
  const current = steps[stepIndex];

  // Reorder options by core relevance
  function getOrderedOptions(step: QuizStepDef): QuizOption[] {
    if (step.id === "mood" && core && MOOD_ORDER[core]) {
      const order = MOOD_ORDER[core];
      return [...step.options].sort(
        (a, b) => order.indexOf(a.key) - order.indexOf(b.key),
      );
    }
    if (step.id === "palette" && core && PALETTE_ORDER[core]) {
      const order = PALETTE_ORDER[core];
      return [...step.options].sort(
        (a, b) => order.indexOf(a.key) - order.indexOf(b.key),
      );
    }
    return step.options;
  }

  // Image path prefix based on step type
  function getImagePrefix(step: QuizStepDef): string {
    if (step.imageDir === "room") return `/quiz/${roomType}/`;
    return "/quiz/";
  }

  // --- Selection getters/setters by step id ---

  function getSelection(id: string): string | string[] {
    switch (id) {
      case "core": return core;
      case "mood": return mood;
      case "palette": return palette;
      case "materials": return materials;
      case "texture": return texture;
      case "shape": return shape;
      case "density": return density;
      case "interests": return interests;
      default: return "";
    }
  }

  function toggleSelection(id: string, key: string, maxSelect?: number) {
    switch (id) {
      case "core": setCore(key); break;
      case "mood": setMood(key); break;
      case "palette": setPalette(key); break;
      case "materials":
        setMaterials((prev) => {
          if (prev.includes(key)) return prev.filter((k) => k !== key);
          if (prev.length >= (maxSelect ?? 99)) return prev;
          return [...prev, key];
        });
        break;
      case "texture": setTexture(key); break;
      case "shape": setShape(key); break;
      case "density": setDensity(key); break;
      case "interests":
        setInterests((prev) =>
          prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
        );
        break;
    }
  }

  function isSelected(id: string, key: string): boolean {
    const sel = getSelection(id);
    return Array.isArray(sel) ? sel.includes(key) : sel === key;
  }

  // Interest sub-tag toggling
  function toggleSubTag(category: string, tag: string) {
    setInterestTags((prev) => {
      const existing = prev[category] ?? [];
      const updated = existing.includes(tag)
        ? existing.filter((t) => t !== tag)
        : [...existing, tag];
      return { ...prev, [category]: updated };
    });
  }

  // --- Navigation ---

  function canAdvance(): boolean {
    switch (current.id) {
      case "core": return core !== "";
      case "mood": return mood !== "";
      case "palette": return palette !== "";
      case "materials": return materials.length > 0;
      case "texture": return texture !== "";
      case "shape": return shape !== "";
      case "density": return density !== "";
      case "bridge": return true;
      case "interests": return true;
      case "interest_details": return true;
      case "freetext": return true;
      default: return true;
    }
  }

  function handleNext() {
    if (stepIndex < totalSteps - 1) {
      // If moving past core, clear texture (it depends on core)
      if (current.id === "core") {
        setTexture("");
      }
      setStepIndex(stepIndex + 1);
    } else {
      // Final step — assemble output
      const description = assembleDescription(
        core, roomType, mood, materials, palette, texture, shape, density, freeText,
      );
      const summary = buildSummary(core, mood, palette);

      const interestOutput = interests.map((cat) => ({
        category: cat,
        tags: interestTags[cat] ?? [],
      }));

      onComplete(
        {
          style: { core, mood, palette, materials, texture, shape, density, description },
          interests: interestOutput,
        },
        summary,
      );
    }
  }

  function handleBack() {
    if (stepIndex > 0) setStepIndex(stepIndex - 1);
  }

  // --- Render helpers ---

  const options = getOrderedOptions(current);
  const imagePrefix = getImagePrefix(current);

  function renderOptions() {
    if (current.layout === "bridge") {
      return null;
    }

    if (current.layout === "textarea") {
      return (
        <textarea
          className="quiz-textarea"
          value={freeText}
          onChange={(e) => setFreeText(e.target.value)}
          placeholder="A color you love, a piece you\u2019re building around, anything..."
          rows={3}
        />
      );
    }

    // Interest sub-options — grouped by category
    if (current.id === "interest_details") {
      if (interests.length === 0) {
        return <p className="quiz-hint">You didn&apos;t pick any \u2014 hit Next to skip.</p>;
      }
      return (
        <div className="interest-subs">
          {interests.map((cat) => {
            const subs = INTEREST_SUBS[cat];
            if (!subs) return null;
            const catLabel = Q_INTERESTS.options.find((o) => o.key === cat)?.label ?? cat;
            const selected = interestTags[cat] ?? [];
            return (
              <div key={cat} className="interest-sub-group">
                <span className="interest-sub-label">{catLabel}</span>
                <div className="interest-sub-chips">
                  {subs.map((sub) => (
                    <button
                      key={sub.tag}
                      type="button"
                      className={`interest-chip ${selected.includes(sub.tag) ? "selected" : ""}`}
                      onClick={() => toggleSubTag(cat, sub.tag)}
                    >
                      {sub.label}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    // Interest chips with emoji
    if (current.layout === "chips") {
      return (
        <div className="interest-chip-grid">
          {options.map((opt) => (
            <button
              key={opt.key}
              type="button"
              className={`interest-chip-lg ${isSelected(current.id, opt.key) ? "selected" : ""}`}
              onClick={() => toggleSelection(current.id, opt.key)}
            >
              {opt.icon && <span className="interest-icon">{opt.icon}</span>}
              <span>{opt.label}</span>
            </button>
          ))}
        </div>
      );
    }

    // Text cards (shape, density)
    if (current.layout === "text-cards") {
      return (
        <div className="quiz-options">
          {options.map((opt) => (
            <TextCard
              key={opt.key}
              option={opt}
              selected={isSelected(current.id, opt.key)}
              onClick={() => toggleSelection(current.id, opt.key, current.maxSelect)}
            />
          ))}
        </div>
      );
    }

    // Image cards (core, mood, palette, materials, texture)
    return (
      <div className="quiz-card-grid">
        {options.map((opt) => (
          <QuizImageCard
            key={opt.key}
            option={opt}
            selected={isSelected(current.id, opt.key)}
            onClick={() => toggleSelection(current.id, opt.key, current.maxSelect)}
            imagePrefix={imagePrefix}
          />
        ))}
      </div>
    );
  }

  const progressPct = ((stepIndex + 1) / totalSteps) * 100;
  const isLastStep = stepIndex === totalSteps - 1;

  return (
    <div className="quiz-container">
      {/* Progress bar */}
      <div className="quiz-progress">
        <div className="quiz-progress-track">
          <div className="quiz-progress-fill" style={{ width: `${progressPct}%` }} />
        </div>
        <span className="quiz-progress-label">{stepIndex + 1} / {totalSteps}</span>
      </div>

      <h2 className="quiz-question">{current.question}</h2>
      {current.hint && <p className="quiz-hint">{current.hint}</p>}

      {renderOptions()}

      {/* Nav */}
      <div className="quiz-nav">
        {stepIndex > 0 && (
          <button type="button" className="quiz-btn quiz-btn-back" onClick={handleBack}>
            Back
          </button>
        )}
        <button
          type="button"
          className="quiz-btn quiz-btn-next"
          disabled={!canAdvance()}
          onClick={handleNext}
        >
          {isLastStep ? "Done" : "Next"}
        </button>
      </div>
    </div>
  );
}
