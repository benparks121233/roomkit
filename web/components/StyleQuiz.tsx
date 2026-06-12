"use client";

// Unified intake wizard — every field is a paginated step.
//
// SETUP: room_type → bed_size (bedroom only) → budget
// STYLE: core → mood → palette → materials → shape → density
// INTERESTS: bridge → categories → sub-options
// FINISH: ownership → free text → submit
//
// Q1-Q3 style images are room-specific (/quiz/{roomType}/core_*.jpg, etc.).
// Q4-Q5 images are shared (/quiz/material_*.jpg, shape_*.jpg).
// Missing images fall back to color swatches.
//
// Assembles a QuizOutput + intake fields; page.tsx builds the DesignRequest.

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
    shape: string;
    density: string;
    description: string;
  };
  interests: { category: string; tags: string[] }[];
}

export interface IntakeResult {
  roomType: string;
  bedSize: string;
  budget: number;
  fullRoom: boolean;
  wants: string[];
  quiz: QuizOutput;
  summary: string;
}

interface QuizOption {
  key: string;
  label: string;
  description?: string;
  swatches: string[];
  image?: string;       // filename only — prefix built at render
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
  layout?: "cards" | "chips" | "icon-cards" | "select-cards" | "bridge" | "textarea" | "budget" | "scope";
  imageDir?: "room" | "shared";
}

// ---------------------------------------------------------------------------
// Step definitions — SETUP
// ---------------------------------------------------------------------------

const ROOM_TYPES = ["bedroom", "living_room"];
const BED_SIZES = ["twin", "full", "queen", "king"];

const Q_ROOM_TYPE: QuizStepDef = {
  id: "room_type",
  question: "What room are we designing?",
  selectMode: "single",
  layout: "select-cards",
  options: [
    { key: "bedroom",     label: "Bedroom",     swatches: [] },
    { key: "living_room", label: "Living Room",  swatches: [] },
  ],
};

const Q_BED_SIZE: QuizStepDef = {
  id: "bed_size",
  question: "What size bed?",
  selectMode: "single",
  layout: "select-cards",
  options: BED_SIZES.map((s) => ({ key: s, label: s.charAt(0).toUpperCase() + s.slice(1), swatches: [] })),
};

const Q_BUDGET: QuizStepDef = {
  id: "budget",
  question: "What\u2019s your budget?",
  hint: "Don\u2019t worry \u2014 we\u2019ll work with whatever you set.",
  selectMode: "single",
  layout: "budget",
  options: [],
};

// ---------------------------------------------------------------------------
// Step definitions — STYLE questions
// ---------------------------------------------------------------------------

const Q_CORE: QuizStepDef = {
  id: "core",
  question: "What\u2019s your aesthetic?",
  selectMode: "single",
  layout: "cards",
  imageDir: "room",
  options: [
    { key: "cottagecore",   label: "Cottagecore",   description: "Soft + vintage",     swatches: ["#F5F0E8", "#D4A9A1"], image: "core_cottagecore.jpg" },
    { key: "dark_academia", label: "Dark Academia", description: "Moody + scholarly",  swatches: ["#3B2F2F", "#8B6F47"], image: "core_dark_academia.jpg" },
    { key: "japandi",       label: "Japandi",       description: "Calm + minimal",     swatches: ["#E8E2D8", "#B8A99A"], image: "core_japandi.jpg" },
    { key: "coastal",       label: "Coastal",       description: "Breezy + light",     swatches: ["#FFFFFF", "#A8C4B8"], image: "core_coastal.jpg" },
    { key: "industrial",    label: "Industrial",    description: "Raw + rugged",       swatches: ["#3A3A3A", "#6B6B6B"], image: "core_industrial.jpg" },
    { key: "quiet_luxury",  label: "Quiet Luxury",  description: "Polished + serene",  swatches: ["#F5F0E8", "#C4A882"], image: "core_quiet_luxury.jpg" },
    { key: "sports_den",    label: "Sports Den",    description: "Dark + loungey",     swatches: ["#2A2A2A", "#8B6F47"], image: "core_sports_den.jpg" },
    { key: "city_modern",   label: "City Modern",   description: "Sleek + urban",      swatches: ["#3A3A3A", "#FFFFFF"], image: "core_city_modern.jpg" },
    { key: "ski_lodge",     label: "Ski Lodge",     description: "Cozy + alpine",      swatches: ["#8B6F47", "#D4B896"], image: "core_ski_lodge.jpg" },
    { key: "jungle_oasis", label: "Jungle Oasis",  description: "Lush + tropical",    swatches: ["#4A6741", "#C4A882"], image: "core_jungle_oasis.jpg" },
    { key: "gamer_den",    label: "Gamer Den",     description: "Dark + techy",       swatches: ["#1A1A2E", "#7B5EA7"], image: "core_gamer_den.jpg" },
    { key: "poster_maximalist", label: "Poster Maximalist", description: "Eclectic + expressive", swatches: ["#C67B5C", "#E8C547"], image: "core_poster_maximalist.jpg" },
  ],
};

const Q_MOOD: QuizStepDef = {
  id: "mood",
  question: "How should the room feel?",
  selectMode: "single",
  layout: "cards",
  imageDir: "room",
  options: [
    { key: "soft_still",       label: "Soft & Still",        swatches: ["#E8E2D8", "#D4CFC6"], image: "mood_soft_still.jpg" },
    { key: "bright_airy",      label: "Bright & Airy",       swatches: ["#FFFFFF", "#F5F0E8"], image: "mood_bright_airy.jpg" },
    { key: "warm_cozy",        label: "Warm & Cozy",         swatches: ["#C4A882", "#8B6F47"], image: "mood_warm_cozy.jpg" },
    { key: "bold_confident",   label: "Bold & Confident",    swatches: ["#8B1A2B", "#C89B3C"], image: "mood_bold_confident.jpg" },
    { key: "moody_deep",       label: "Moody & Deep",        swatches: ["#2A2A2A", "#4A3A2A"], image: "mood_moody_deep.jpg" },
    { key: "playful_eclectic", label: "Playful & Eclectic",  swatches: ["#C67B5C", "#6B7C4E"], image: "mood_playful_eclectic.jpg" },
    { key: "heritage",         label: "Heritage",            swatches: ["#5E4B3B", "#C89B3C"], image: "mood_heritage.jpg" },
    { key: "alpine",           label: "Alpine",              swatches: ["#8B6F47", "#D4B896"], image: "mood_alpine.jpg" },
  ],
};

const MOOD_ORDER: Record<string, string[]> = {
  cottagecore:   ["warm_cozy", "soft_still", "bright_airy", "heritage", "playful_eclectic", "alpine", "bold_confident", "moody_deep"],
  dark_academia: ["moody_deep", "heritage", "warm_cozy", "bold_confident", "soft_still", "alpine", "playful_eclectic", "bright_airy"],
  japandi:       ["soft_still", "bright_airy", "warm_cozy", "moody_deep", "heritage", "bold_confident", "alpine", "playful_eclectic"],
  coastal:       ["bright_airy", "soft_still", "warm_cozy", "playful_eclectic", "alpine", "bold_confident", "heritage", "moody_deep"],
  industrial:    ["moody_deep", "bold_confident", "warm_cozy", "alpine", "playful_eclectic", "heritage", "soft_still", "bright_airy"],
  quiet_luxury:  ["heritage", "soft_still", "warm_cozy", "bold_confident", "bright_airy", "moody_deep", "alpine", "playful_eclectic"],
  sports_den:    ["moody_deep", "bold_confident", "heritage", "warm_cozy", "playful_eclectic", "alpine", "soft_still", "bright_airy"],
  city_modern:   ["bold_confident", "moody_deep", "heritage", "bright_airy", "soft_still", "warm_cozy", "alpine", "playful_eclectic"],
  ski_lodge:     ["alpine", "warm_cozy", "soft_still", "moody_deep", "heritage", "bright_airy", "bold_confident", "playful_eclectic"],
  jungle_oasis:  ["warm_cozy", "soft_still", "bright_airy", "playful_eclectic", "alpine", "bold_confident", "heritage", "moody_deep"],
  gamer_den:     ["moody_deep", "bold_confident", "playful_eclectic", "warm_cozy", "alpine", "soft_still", "heritage", "bright_airy"],
  poster_maximalist: ["playful_eclectic", "bold_confident", "warm_cozy", "moody_deep", "alpine", "bright_airy", "heritage", "soft_still"],
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
    { key: "verdant",       label: "Verdant",         swatches: ["#2D5A3D", "#6B7C4E", "#B5A167"], image: "palette_verdant.jpg" },
    { key: "electric",      label: "Electric",        swatches: ["#2A4FBF", "#E85D5D", "#F0C040"], image: "palette_electric.jpg" },
  ],
};

const PALETTE_ORDER: Record<string, string[]> = {
  cottagecore:   ["blush_sage", "warm_neutrals", "verdant", "coastal_soft", "earthy_rich", "jewel_tones", "electric", "dark_moody"],
  dark_academia: ["dark_moody", "earthy_rich", "jewel_tones", "verdant", "warm_neutrals", "blush_sage", "coastal_soft", "electric"],
  japandi:       ["warm_neutrals", "coastal_soft", "blush_sage", "verdant", "dark_moody", "earthy_rich", "jewel_tones", "electric"],
  coastal:       ["coastal_soft", "warm_neutrals", "blush_sage", "verdant", "earthy_rich", "electric", "jewel_tones", "dark_moody"],
  industrial:    ["dark_moody", "earthy_rich", "warm_neutrals", "jewel_tones", "verdant", "electric", "coastal_soft", "blush_sage"],
  quiet_luxury:  ["warm_neutrals", "blush_sage", "coastal_soft", "earthy_rich", "verdant", "dark_moody", "jewel_tones", "electric"],
  sports_den:    ["dark_moody", "earthy_rich", "jewel_tones", "warm_neutrals", "verdant", "coastal_soft", "electric", "blush_sage"],
  city_modern:   ["dark_moody", "warm_neutrals", "electric", "coastal_soft", "jewel_tones", "earthy_rich", "verdant", "blush_sage"],
  ski_lodge:     ["earthy_rich", "warm_neutrals", "verdant", "dark_moody", "blush_sage", "jewel_tones", "coastal_soft", "electric"],
  jungle_oasis:  ["verdant", "earthy_rich", "warm_neutrals", "blush_sage", "dark_moody", "jewel_tones", "coastal_soft", "electric"],
  gamer_den:     ["dark_moody", "electric", "jewel_tones", "verdant", "earthy_rich", "warm_neutrals", "coastal_soft", "blush_sage"],
  poster_maximalist: ["electric", "jewel_tones", "earthy_rich", "warm_neutrals", "verdant", "blush_sage", "dark_moody", "coastal_soft"],
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
    { key: "wood_linen",     label: "Wood & Linen",    swatches: ["#D4B896"], image: "material_wood_linen.jpg" },
    { key: "walnut_leather", label: "Walnut & Leather", swatches: ["#5E4B3B"], image: "material_walnut_leather.jpg" },
    { key: "velvet_brass",   label: "Velvet & Brass",   swatches: ["#8B1A2B"], image: "material_velvet_brass.jpg" },
    { key: "rattan_cotton",  label: "Rattan & Cotton",  swatches: ["#D4C5A9"], image: "material_rattan_cotton.jpg" },
  ],
};

const Q_SHAPE: QuizStepDef = {
  id: "shape",
  question: "Straight lines or soft curves?",
  selectMode: "single",
  layout: "cards",
  imageDir: "shared",
  options: [
    { key: "clean_straight", label: "Straight lines",  swatches: ["#E8E2D8"], image: "shape_straight.jpg" },
    { key: "organic_curved", label: "Curves + arches", swatches: ["#E8E2D8"], image: "shape_curved.jpg" },
    { key: "mixed",          label: "A mix of both",   swatches: ["#E8E2D8"], image: "shape_mixed.jpg" },
  ],
};

const Q_DENSITY: QuizStepDef = {
  id: "density",
  question: "How much stuff do you want in the room?",
  selectMode: "single",
  layout: "icon-cards",
  options: [
    { key: "minimal",  label: "Minimal",   description: "Just the essentials", swatches: [] },
    { key: "balanced", label: "Balanced",   description: "Full but not cluttered", swatches: [] },
    { key: "layered",  label: "Layered",    description: "Lived-in, collected", swatches: [] },
  ],
};

// ---------------------------------------------------------------------------
// Step definitions — INTERESTS
// ---------------------------------------------------------------------------

const Q_BRIDGE: QuizStepDef = {
  id: "bridge",
  question: "Almost done \u2014 tell us what you're into.",
  hint: "These don't affect your furniture \u2014 they'll help us pick art, prints, and decor that actually feel like you.",
  selectMode: "single",
  layout: "bridge",
  options: [],
};

const Q_INTERESTS: QuizStepDef = {
  id: "interests",
  question: "Pick anything that's your thing.",
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

// ---------------------------------------------------------------------------
// Step definitions — FINISH
// ---------------------------------------------------------------------------

const Q_SCOPE: QuizStepDef = {
  id: "scope",
  question: "How much of the room do you need?",
  selectMode: "single",
  layout: "scope",
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
// Ownership groups — mirrors slot_taxonomy.yaml
// ---------------------------------------------------------------------------

interface OwnershipGroup {
  label: string;
  items: string[];
}

const ROOM_OWNERSHIP_GROUPS: Record<string, OwnershipGroup[]> = {
  bedroom: [
    { label: "Bed",        items: ["bed_frame", "mattress", "sheets", "comforter", "pillows"] },
    { label: "Storage",    items: ["nightstand", "dresser"] },
    { label: "Lighting",   items: ["ceiling_light", "table_lamp", "floor_lamp"] },
    { label: "Decor",      items: ["wall_art", "plants", "mirror"] },
    { label: "Soft Goods", items: ["rug", "curtains", "throw_blanket"] },
  ],
  living_room: [
    { label: "Seating",       items: ["sofa", "armchair", "ottoman"] },
    { label: "Entertainment", items: ["tv", "tv_stand", "sound_bar"] },
    { label: "Tables",        items: ["coffee_table", "side_table"] },
    { label: "Lighting",      items: ["ceiling_light", "floor_lamp", "table_lamp"] },
    { label: "Decor",         items: ["wall_art", "plants", "mirror", "bookshelf"] },
    { label: "Soft Goods",    items: ["rug", "curtains", "throw_pillows", "throw_blanket"] },
  ],
};

// ---------------------------------------------------------------------------
// Style description assembly
// ---------------------------------------------------------------------------

const CORE_PHRASES: Record<string, string> = {
  cottagecore:        "cottagecore",
  dark_academia:      "dark academia",
  japandi:            "japandi",
  coastal:            "coastal",
  industrial:         "industrial",
  quiet_luxury:       "quiet luxury",
  sports_den:         "sports den",
  city_modern:        "city modern",
  ski_lodge:          "ski lodge",
  jungle_oasis:       "jungle oasis",
  gamer_den:          "gamer den",
  poster_maximalist:  "poster maximalist",
};

const MOOD_PHRASES: Record<string, string> = {
  soft_still:       "soft and still, with a quiet contemplative energy",
  bright_airy:      "bright and airy, with plenty of natural light",
  warm_cozy:        "warm and cozy, intimate and enveloping",
  bold_confident:   "bold and confident, with saturated decisive tones",
  moody_deep:       "moody and atmospheric, with rich depth",
  playful_eclectic: "playful and eclectic, with vibrant mixed energy",
  heritage:         "refined and heritage-inspired, with antiques, rich woods, and understated old-money elegance",
  alpine:           "alpine and lodge-like, with timber, wool, and cozy-grand mountain warmth",
};

const MATERIAL_PHRASES: Record<string, string> = {
  wood_linen:     "natural wood and linen",
  walnut_leather: "walnut and leather",
  velvet_brass:   "velvet and brass accents",
  rattan_cotton:  "rattan and cotton",
};

const PALETTE_PHRASES: Record<string, string> = {
  warm_neutrals: "in warm neutrals with cream, oak, and terracotta accents",
  earthy_rich:   "in earthy tones with walnut, mustard, and olive",
  jewel_tones:   "in jewel tones with deep teal, burgundy, and gold",
  coastal_soft:  "in coastal tones with white, seafoam, and sand",
  dark_moody:    "in dark tones with charcoal, dark wood, and warm amber",
  blush_sage:    "in soft blush and sage with dusty pink, green, and cream",
  verdant:       "in deep botanical greens with emerald, olive, and warm brass accents",
  electric:      "in saturated modern brights with bold color-blocking — cobalt, coral, and sunshine yellow, kept intentional and premium",
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
  shape: string,
  density: string,
  freeText: string,
): string {
  const corePhrase = CORE_PHRASES[core] ?? core;
  const moodPhrase = MOOD_PHRASES[mood] ?? mood;
  const matPhrase = materials.map((m) => MATERIAL_PHRASES[m] ?? m).join(" and ");
  const palPhrase = PALETTE_PHRASES[palette] ?? palette;
  const shapeSentence = SHAPE_PHRASES[shape] ?? "";
  const densSentence = DENSITY_PHRASES[density] ?? "";

  const roomLabel = roomType.replace(/_/g, " ");
  let desc = `I want a ${corePhrase} ${roomLabel} \u2014 ${moodPhrase}, ${palPhrase}.`;
  if (matPhrase) desc += ` I'm drawn to ${matPhrase}.`;
  if (shapeSentence) desc += ` ${shapeSentence}`;
  if (densSentence) desc += ` ${densSentence}`;
  if (freeText.trim()) desc += ` ${freeText.trim()}`;
  return desc;
}

const CORE_LABELS: Record<string, string> = {
  cottagecore: "Cottagecore", dark_academia: "Dark Academia", japandi: "Japandi",
  coastal: "Coastal", industrial: "Industrial", quiet_luxury: "Quiet Luxury",
  sports_den: "Sports Den", city_modern: "City Modern", ski_lodge: "Ski Lodge",
};

const MOOD_LABELS: Record<string, string> = {
  soft_still: "Soft & Still", bright_airy: "Bright & Airy",
  warm_cozy: "Warm & Cozy", bold_confident: "Bold & Confident",
  moody_deep: "Moody & Deep", playful_eclectic: "Playful & Eclectic",
  heritage: "Heritage", alpine: "Alpine",
};

const PALETTE_LABELS: Record<string, string> = {
  warm_neutrals: "Warm Neutrals", earthy_rich: "Earthy & Rich",
  jewel_tones: "Jewel Tones", coastal_soft: "Coastal Soft",
  dark_moody: "Dark & Moody", blush_sage: "Blush & Sage",
  verdant: "Verdant", electric: "Electric",
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
// Density icon — abstract dots: sparse / medium / dense
// ---------------------------------------------------------------------------

function DensityIcon({ density }: { density: string }) {
  const dots: [number, number][] =
    density === "minimal"
      ? [[50, 35], [30, 65], [70, 65]]
      : density === "balanced"
        ? [[50, 20], [25, 45], [75, 45], [35, 70], [65, 70]]
        : /* layered */ [[50, 15], [25, 35], [75, 35], [15, 55], [50, 55], [85, 55], [30, 75], [60, 75], [80, 70]];
  return (
    <svg viewBox="0 0 100 100" className="density-icon" aria-hidden="true">
      {dots.map(([cx, cy], i) => (
        <circle key={i} cx={cx} cy={cy} r="6" fill="currentColor" opacity="0.55" />
      ))}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Icon card (density)
// ---------------------------------------------------------------------------

function IconCard({
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
      className={`quiz-icon-card ${selected ? "selected" : ""}`}
      onClick={onClick}
    >
      <DensityIcon density={option.key} />
      <span className="quiz-icon-card-label">{option.label}</span>
      {option.description && (
        <span className="quiz-icon-card-desc">{option.description}</span>
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Select card (room type, bed size — text-only option in a grid)
// ---------------------------------------------------------------------------

function SelectCard({
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
      className={`quiz-select-card ${selected ? "selected" : ""}`}
      onClick={onClick}
    >
      <span className="quiz-select-card-label">{option.label}</span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  onComplete: (result: IntakeResult) => void;
}

export default function StyleQuiz({ onComplete }: Props) {
  // Setup state
  const [roomType, setRoomType] = useState("bedroom");
  const [bedSize, setBedSize] = useState("queen");
  const [budget, setBudget] = useState(2500);
  const [budgetText, setBudgetText] = useState("2,500");
  const [fullRoom, setFullRoom] = useState(true);
  const [wants, setWants] = useState<string[]>([]);

  // Style state
  const [core, setCore] = useState("");
  const [mood, setMood] = useState("");
  const [palette, setPalette] = useState("");
  const [materials, setMaterials] = useState<string[]>([]);
  const [shape, setShape] = useState("");
  const [density, setDensity] = useState("");

  // Interest state
  const [interests, setInterests] = useState<string[]>([]);
  const [interestTags, setInterestTags] = useState<Record<string, string[]>>({});
  const [freeText, setFreeText] = useState("");

  const [stepIndex, setStepIndex] = useState(0);

  // Build step list — bed_size only for bedroom
  function getSteps(): QuizStepDef[] {
    const steps: QuizStepDef[] = [Q_ROOM_TYPE];
    if (roomType === "bedroom") steps.push(Q_BED_SIZE);
    steps.push(
      Q_BUDGET,
      Q_CORE, Q_MOOD, Q_PALETTE, Q_MATERIALS, Q_SHAPE, Q_DENSITY,
      Q_BRIDGE, Q_INTERESTS, Q_SUBS,
      Q_SCOPE, Q_FREETEXT,
    );
    return steps;
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

  function getImagePrefix(step: QuizStepDef): string {
    if (step.imageDir === "room") return `/quiz/${roomType}/`;
    return "/quiz/";
  }

  // --- Selection getters/setters ---

  function getSelection(id: string): string | string[] {
    switch (id) {
      case "room_type": return roomType;
      case "bed_size": return bedSize;
      case "core": return core;
      case "mood": return mood;
      case "palette": return palette;
      case "materials": return materials;
      case "shape": return shape;
      case "density": return density;
      case "interests": return interests;
      default: return "";
    }
  }

  function toggleSelection(id: string, key: string, maxSelect?: number) {
    switch (id) {
      case "room_type":
        if (key !== roomType) {
          setRoomType(key);
          setWants([]); // groups differ per room
        }
        break;
      case "bed_size": setBedSize(key); break;
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

  // Wants chip toggles (partial room mode)
  function toggleWant(item: string) {
    setWants((prev) =>
      prev.includes(item) ? prev.filter((i) => i !== item) : [...prev, item],
    );
  }

  function toggleWantGroup(items: string[]) {
    const allSelected = items.every((i) => wants.includes(i));
    if (allSelected) {
      setWants((prev) => prev.filter((i) => !items.includes(i)));
    } else {
      setWants((prev) => Array.from(new Set([...prev, ...items])));
    }
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
      case "room_type": return roomType !== "";
      case "bed_size": return bedSize !== "";
      case "budget": return true;
      case "core": return core !== "";
      case "mood": return mood !== "";
      case "palette": return palette !== "";
      case "materials": return materials.length > 0;
      case "shape": return shape !== "";
      case "density": return density !== "";
      case "bridge": return true;
      case "interests": return true;
      case "interest_details": return true;
      case "scope": return fullRoom || wants.length > 0;
      case "freetext": return true;
      default: return true;
    }
  }

  function handleNext() {
    if (stepIndex < totalSteps - 1) {
      setStepIndex(stepIndex + 1);
    } else {
      // Final step — assemble and submit
      const description = assembleDescription(
        core, roomType, mood, materials, palette, shape, density, freeText,
      );
      const summary = buildSummary(core, mood, palette);
      const interestOutput = interests.map((cat) => ({
        category: cat,
        tags: interestTags[cat] ?? [],
      }));

      onComplete({
        roomType,
        bedSize,
        budget,
        fullRoom,
        wants,
        quiz: {
          style: { core, mood, palette, materials, shape, density, description },
          interests: interestOutput,
        },
        summary,
      });
    }
  }

  function handleBack() {
    if (stepIndex > 0) setStepIndex(stepIndex - 1);
  }

  // --- Render ---

  const options = getOrderedOptions(current);
  const imagePrefix = getImagePrefix(current);

  function renderStep() {
    // Bridge — no options
    if (current.layout === "bridge") {
      return null;
    }

    // Budget slider
    if (current.layout === "budget") {
      return (
        <div className="budget-step">
          <div className="budget-input-wrapper">
            <span className="budget-currency">$</span>
            <input
              type="text"
              inputMode="numeric"
              value={budgetText}
              onChange={(e) => {
                const raw = e.target.value.replace(/[^0-9]/g, "");
                setBudgetText(raw);
                const val = parseInt(raw, 10);
                if (!isNaN(val) && val >= 0) {
                  setBudget(Math.min(val, 5000));
                } else if (raw === "") {
                  setBudget(0);
                }
              }}
              onBlur={() => {
                const clamped = Math.min(Math.max(budget, 0), 5000);
                setBudget(clamped);
                setBudgetText(clamped.toLocaleString());
              }}
              onFocus={(e) => {
                setBudgetText(budget === 0 ? "" : String(budget));
                e.target.select();
              }}
              placeholder="2,500"
              className="budget-text-input"
            />
          </div>
          <input
            type="range"
            min={0}
            max={5000}
            step={10}
            value={budget}
            onChange={(e) => {
              const val = Number(e.target.value);
              setBudget(val);
              setBudgetText(val.toLocaleString());
            }}
            className="budget-slider"
          />
          <div className="budget-range-labels">
            <span>$0</span>
            <span>$5,000</span>
          </div>
        </div>
      );
    }

    // Scope — hero choice + conditional picker
    if (current.layout === "scope") {
      const groups = ROOM_OWNERSHIP_GROUPS[roomType] ?? [];
      return (
        <div className="scope-step">
          <div className="scope-choice-grid">
            <button
              type="button"
              className={`scope-choice-card primary ${fullRoom ? "selected" : ""}`}
              onClick={() => { setFullRoom(true); setWants([]); }}
            >
              <span className="scope-choice-label">Design my whole room</span>
              <span className="scope-choice-desc">We'll source everything from scratch.</span>
            </button>
            <button
              type="button"
              className={`scope-choice-card ${!fullRoom ? "selected" : ""}`}
              onClick={() => setFullRoom(false)}
            >
              <span className="scope-choice-label">I just need a few pieces</span>
              <span className="scope-choice-desc">Pick the items you want us to find.</span>
            </button>
          </div>

          {!fullRoom && (
            <div className="scope-picker">
              <p className="scope-picker-label">What are you looking for?</p>
              <div className="ownership-groups">
                {groups.map((group) => (
                  <div key={group.label} className="ownership-section">
                    <span
                      className="ownership-section-label"
                      onClick={() => toggleWantGroup(group.items)}
                    >
                      {group.label}
                    </span>
                    <div className="ownership-chips">
                      {group.items.map((item) => (
                        <button
                          key={item}
                          type="button"
                          className={`ownership-chip ${wants.includes(item) ? "selected" : ""}`}
                          onClick={() => toggleWant(item)}
                        >
                          <svg className="chip-check" viewBox="0 0 14 14" fill="none">
                            <path d="M2.5 7.5L5.5 10.5L11.5 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                          {item.replace(/_/g, " ")}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      );
    }

    // Free text
    if (current.layout === "textarea") {
      return (
        <textarea
          className="quiz-textarea"
          value={freeText}
          onChange={(e) => setFreeText(e.target.value)}
          placeholder="A color you love, a piece you're building around, anything..."
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

    // Select cards (room type, bed size)
    if (current.layout === "select-cards") {
      return (
        <div className="quiz-select-grid">
          {options.map((opt) => (
            <SelectCard
              key={opt.key}
              option={opt}
              selected={isSelected(current.id, opt.key)}
              onClick={() => toggleSelection(current.id, opt.key)}
            />
          ))}
        </div>
      );
    }

    // Icon cards (density)
    if (current.layout === "icon-cards") {
      return (
        <div className="quiz-icon-card-grid">
          {options.map((opt) => (
            <IconCard
              key={opt.key}
              option={opt}
              selected={isSelected(current.id, opt.key)}
              onClick={() => toggleSelection(current.id, opt.key, current.maxSelect)}
            />
          ))}
        </div>
      );
    }

    // Image cards (core, mood, palette, materials, shape)
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
      <div className="quiz-progress">
        <div className="quiz-progress-track">
          <div className="quiz-progress-fill" style={{ width: `${progressPct}%` }} />
        </div>
        <span className="quiz-progress-label">{stepIndex + 1} / {totalSteps}</span>
      </div>

      <h2 className="quiz-question">{current.question}</h2>
      {current.hint && <p className="quiz-hint">{current.hint}</p>}

      {renderStep()}

      <div className="quiz-nav">
        {stepIndex > 0 && (
          <button type="button" className="quiz-btn quiz-btn-back" onClick={handleBack}>
            Back
          </button>
        )}
        <button
          type="button"
          className={`quiz-btn ${isLastStep ? "quiz-btn-submit" : "quiz-btn-next"}`}
          disabled={!canAdvance()}
          onClick={handleNext}
        >
          {isLastStep ? "Design my room" : "Next"}
        </button>
      </div>
    </div>
  );
}
