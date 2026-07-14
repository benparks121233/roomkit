"use client";

// Unified intake wizard — every field is a paginated step.
//
// SETUP: room_type → scope (full/pieces) → bed_size (if bed items needed) → budget
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
  excludedSlots: string[];
  mirrorType: string | null;
  screenSize: string | null;
  tvPriority: boolean;
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
  imageDir: "shared",
  options: [
    { key: "bedroom",     label: "Bedroom",     swatches: [], image: "room_bedroom.jpg" },
    { key: "living_room", label: "Living Room",  swatches: [], image: "room_living_room.jpg" },
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

const Q_CORE_BEDROOM: QuizStepDef = {
  id: "core",
  question: "What\u2019s your aesthetic?",
  hint: "These are for inspiration \u2014 we\u2019ll source real products that match your vibe.",
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

const Q_CORE_LIVING_ROOM: QuizStepDef = {
  id: "core",
  question: "What\u2019s your aesthetic?",
  hint: "These are for inspiration \u2014 we\u2019ll source real products that match your vibe.",
  selectMode: "single",
  layout: "cards",
  imageDir: "room",
  options: [
    { key: "cottagecore",   label: "Country Parlor",   description: "Soft + collected",   swatches: ["#F5F0E8", "#D4A9A1"], image: "core_cottagecore.jpg" },
    { key: "dark_academia", label: "Library Lounge",    description: "Moody + scholarly",  swatches: ["#3B2F2F", "#8B6F47"], image: "core_dark_academia.jpg" },
    { key: "japandi",       label: "Still Room",        description: "Calm + intentional", swatches: ["#E8E2D8", "#B8A99A"], image: "core_japandi.jpg" },
    { key: "coastal",       label: "Shore House",       description: "Breezy + sun-washed", swatches: ["#FFFFFF", "#A8C4B8"], image: "core_coastal.jpg" },
    { key: "industrial",    label: "Warehouse Loft",    description: "Raw + open",         swatches: ["#3A3A3A", "#6B6B6B"], image: "core_industrial.jpg" },
    { key: "quiet_luxury",  label: "The Salon",         description: "Polished + refined", swatches: ["#F5F0E8", "#C4A882"], image: "core_quiet_luxury.jpg" },
    { key: "sports_den",    label: "The Den",           description: "Dark + loungey",     swatches: ["#2A2A2A", "#8B6F47"], image: "core_sports_den.jpg" },
    { key: "city_modern",   label: "High Rise",         description: "Sleek + angular",    swatches: ["#3A3A3A", "#FFFFFF"], image: "core_city_modern.jpg" },
    { key: "ski_lodge",     label: "Fireside",          description: "Warm + alpine",      swatches: ["#8B6F47", "#D4B896"], image: "core_ski_lodge.jpg" },
    { key: "jungle_oasis", label: "Greenhouse",         description: "Lush + wild",        swatches: ["#4A6741", "#C4A882"], image: "core_jungle_oasis.jpg" },
    { key: "gamer_den",    label: "Command Center",     description: "Dark + immersive",   swatches: ["#1A1A2E", "#7B5EA7"], image: "core_gamer_den.jpg" },
    { key: "poster_maximalist", label: "The Gallery",   description: "Eclectic + layered", swatches: ["#C67B5C", "#E8C547"], image: "core_poster_maximalist.jpg" },
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
  imageDir: "room",
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
  question: "Here\u2019s your vibe.",
  hint: "Next up: tell us what you\u2019re into so we can nail the art, prints, and decor.",
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

// ---------------------------------------------------------------------------
// Step definitions — PREFERENCES (slot-gating survey)
// ---------------------------------------------------------------------------

const Q_BEDDING_TYPE: QuizStepDef = {
  id: "bedding_type",
  question: "What goes on the bed?",
  hint: "Comforter = single piece. Duvet = insert + decorative cover.",
  selectMode: "single",
  layout: "cards",
  imageDir: "shared",
  options: [
    { key: "comforter", label: "Comforter", swatches: [], image: "bedding_comforter.jpg" },
    { key: "duvet",     label: "Duvet (insert + cover)", swatches: [], image: "bedding_duvet.jpg" },
  ],
};

const Q_LIGHTING_TYPES: QuizStepDef = {
  id: "lighting_types",
  question: "What lighting do you want?",
  hint: "Pick all that apply.",
  selectMode: "multi",
  layout: "cards",
  imageDir: "shared",
  options: [
    { key: "ceiling_light", label: "Overhead / Ceiling", swatches: [], image: "lighting_ceiling.jpg" },
    { key: "table_lamp",    label: "Table Lamp", swatches: [], image: "lighting_table_lamp.jpg" },
    { key: "floor_lamp",    label: "Floor Lamp", swatches: [], image: "lighting_floor_lamp.jpg" },
    { key: "sconce",        label: "Wall Sconce", swatches: [], image: "lighting_sconce.jpg" },
  ],
};

const Q_DESK_PREF: QuizStepDef = {
  id: "desk_pref",
  question: "Do you want a desk area?",
  selectMode: "single",
  layout: "select-cards",
  options: [
    { key: "yes", label: "Yes — desk + chair", swatches: [] },
    { key: "no",  label: "No desk needed", swatches: [] },
  ],
};

const Q_MIRROR_PREF: QuizStepDef = {
  id: "mirror_pref",
  question: "What kind of mirror?",
  selectMode: "single",
  layout: "cards",
  imageDir: "shared",
  options: [
    { key: "round",       label: "Round",        swatches: [], image: "mirror_round.jpg" },
    { key: "arched",      label: "Arched",       swatches: [], image: "mirror_arched.jpg" },
    { key: "rectangular", label: "Rectangular",  swatches: [], image: "mirror_rectangular.jpg" },
    { key: "full_length", label: "Full-length",  swatches: [], image: "mirror_full_length.jpg" },
    { key: "any",         label: "No preference", swatches: [], image: "mirror_wall.jpg" },
    { key: "none",        label: "None",          swatches: [], image: "mirror_none.jpg" },
  ],
};

// ---------------------------------------------------------------------------
// Step definitions — LIVING ROOM PREFERENCES
// ---------------------------------------------------------------------------

const Q_ENTERTAINMENT_PREF: QuizStepDef = {
  id: "entertainment_pref",
  question: "Do you want an entertainment space?",
  selectMode: "single",
  layout: "select-cards",
  options: [
    { key: "yes", label: "Yes \u2014 TV setup", swatches: [] },
    { key: "no",  label: "No TV", swatches: [] },
  ],
};

const Q_SCREEN_SIZE: QuizStepDef = {
  id: "screen_size",
  question: "What size TV?",
  selectMode: "single",
  layout: "select-cards",
  options: [
    { key: "small",  label: "Small (32\u201343\")",  swatches: [] },
    { key: "medium", label: "Medium (50\u201355\")", swatches: [] },
    { key: "large",  label: "Large (65\")",       swatches: [] },
    { key: "xl",     label: "Extra Large (75\"+)", swatches: [] },
  ],
};

const Q_TV_PLACEMENT: QuizStepDef = {
  id: "tv_placement",
  question: "TV stand or wall mount?",
  selectMode: "single",
  layout: "cards",
  imageDir: "shared",
  options: [
    { key: "stand", label: "TV Stand",    swatches: [], image: "tv_stand.jpg" },
    { key: "mount", label: "Wall Mount",  swatches: [], image: "tv_mount.jpg" },
  ],
};

const Q_BOOKSHELF_PREF: QuizStepDef = {
  id: "bookshelf_pref",
  question: "Do you want a bookshelf?",
  selectMode: "single",
  layout: "select-cards",
  options: [
    { key: "yes", label: "Yes", swatches: [] },
    { key: "no",  label: "No",  swatches: [] },
  ],
};

const Q_SEATING_PREF: QuizStepDef = {
  id: "seating_pref",
  question: "What seating do you want beyond a sofa?",
  selectMode: "single",
  layout: "cards",
  imageDir: "shared",
  options: [
    { key: "armchair",  label: "Armchair",        swatches: [], image: "seating_armchair.jpg" },
    { key: "sofa_only", label: "Just the sofa",   swatches: [], image: "seating_sofa_only.jpg" },
  ],
};

const Q_LR_LIGHTING_TYPES: QuizStepDef = {
  id: "lr_lighting_types",
  question: "What lighting do you want?",
  hint: "Pick all that apply.",
  selectMode: "multi",
  layout: "cards",
  imageDir: "shared",
  options: [
    { key: "ceiling_light", label: "Overhead / Ceiling", swatches: [], image: "lighting_ceiling.jpg" },
    { key: "floor_lamp",    label: "Floor Lamp", swatches: [], image: "lighting_floor_lamp.jpg" },
    { key: "table_lamp",    label: "Table Lamp", swatches: [], image: "lighting_table_lamp.jpg" },
  ],
};

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
    { label: "Bed",        items: ["bed_frame", "mattress", "sheets", "comforter", "duvet_insert", "duvet_cover", "pillows"] },
    { label: "Storage & Workspace", items: ["nightstand", "dresser", "desk", "desk_chair"] },
    { label: "Lighting",   items: ["ceiling_light", "table_lamp", "floor_lamp", "sconce"] },
    { label: "Decor",      items: ["wall_art", "plants", "mirror"] },
    { label: "Soft Goods", items: ["rug", "curtains", "throw_blanket"] },
  ],
  living_room: [
    { label: "Seating",       items: ["sofa", "armchair"] },
    { label: "Entertainment", items: ["tv", "tv_stand", "tv_mount"] },
    { label: "Tables",        items: ["coffee_table", "side_table"] },
    { label: "Lighting",      items: ["ceiling_light", "floor_lamp", "table_lamp"] },
    { label: "Decor",         items: ["wall_art", "plants", "bookshelf"] },
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

const CORE_LABELS_BEDROOM: Record<string, string> = {
  cottagecore: "Cottagecore", dark_academia: "Dark Academia", japandi: "Japandi",
  coastal: "Coastal", industrial: "Industrial", quiet_luxury: "Quiet Luxury",
  sports_den: "Sports Den", city_modern: "City Modern", ski_lodge: "Ski Lodge",
  jungle_oasis: "Jungle Oasis", gamer_den: "Gamer Den", poster_maximalist: "Poster Maximalist",
};

const CORE_LABELS_LIVING_ROOM: Record<string, string> = {
  cottagecore: "Country Parlor", dark_academia: "Library Lounge", japandi: "Still Room",
  coastal: "Shore House", industrial: "Warehouse Loft", quiet_luxury: "The Salon",
  sports_den: "The Den", city_modern: "High Rise", ski_lodge: "Fireside",
  jungle_oasis: "Greenhouse", gamer_den: "Command Center", poster_maximalist: "The Gallery",
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

function buildSummary(core: string, mood: string, palette: string, roomType: string): string {
  const coreLabels = roomType === "living_room" ? CORE_LABELS_LIVING_ROOM : CORE_LABELS_BEDROOM;
  return [coreLabels[core], MOOD_LABELS[mood], PALETTE_LABELS[palette]].filter(Boolean).join(" \u00b7 ");
}

// ---------------------------------------------------------------------------
// Image card with swatch fallback
// ---------------------------------------------------------------------------

function SelectIndicator({ mode, selected }: { mode: SelectMode; selected: boolean }) {
  if (mode === "multi") {
    return (
      <span className={`select-indicator checkbox ${selected ? "checked" : ""}`}>
        {selected && <svg width="10" height="10" viewBox="0 0 12 12"><path d="M2 6l3 3 5-5" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>}
      </span>
    );
  }
  return (
    <span className={`select-indicator radio ${selected ? "checked" : ""}`}>
      {selected && <span className="radio-dot" />}
    </span>
  );
}

function QuizImageCard({
  option,
  selected,
  onClick,
  imagePrefix,
  selectMode = "single",
}: {
  option: QuizOption;
  selected: boolean;
  onClick: () => void;
  imagePrefix: string;
  selectMode?: SelectMode;
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
        <SelectIndicator mode={selectMode} selected={selected} />
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
  imagePrefix,
}: {
  option: QuizOption;
  selected: boolean;
  onClick: () => void;
  imagePrefix?: string;
}) {
  return (
    <button
      type="button"
      className={`quiz-select-card ${selected ? "selected" : ""}`}
      onClick={onClick}
    >
      <span className="quiz-select-card-label">{option.label}</span>
      {option.image && imagePrefix && (
        <div className="quiz-select-card-image">
          <Image
            src={`${imagePrefix}${option.image}`}
            alt={option.label}
            width={320}
            height={200}
            style={{ objectFit: "cover", width: "100%", height: "100%", borderRadius: "6px" }}
          />
        </div>
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  onComplete: (result: IntakeResult) => void;
  initialRoomType?: string;
}

export default function StyleQuiz({ onComplete, initialRoomType }: Props) {
  // Setup state
  const [roomType, setRoomType] = useState(initialRoomType || "bedroom");
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

  // Preference state (slot-gating survey) — all start unselected.
  // Bedroom prefs
  const [beddingType, setBeddingType] = useState("");
  const [lightingTypes, setLightingTypes] = useState<string[]>([]);
  const [deskPref, setDeskPref] = useState("");
  const [mirrorPref, setMirrorPref] = useState("");
  // Living room prefs
  const [entertainmentPref, setEntertainmentPref] = useState("");
  const [screenSize, setScreenSize] = useState("");
  const [tvPriority, setTvPriority] = useState(false);
  const [tvPlacement, setTvPlacement] = useState("");
  const [bookshelfPref, setBookshelfPref] = useState("");
  const [seatingPref, setSeatingPref] = useState("");
  const [lrLightingTypes, setLrLightingTypes] = useState<string[]>([]);

  // Interest state
  const [interests, setInterests] = useState<string[]>([]);
  const [interestTags, setInterestTags] = useState<Record<string, string[]>>({});
  const [freeText, setFreeText] = useState("");

  const [stepIndex, setStepIndex] = useState(initialRoomType ? 1 : 0);

  // Build step list — scope gates preferences, density after preferences.
  function getSteps(): QuizStepDef[] {
    const _BED_SIZE_SLOTS = new Set([
      "bed_frame", "mattress", "sheets", "comforter",
      "duvet_insert", "duvet_cover", "pillows", "shams",
    ]);
    const needsBedSize = fullRoom || wants.some((w) => _BED_SIZE_SLOTS.has(w));

    const steps: QuizStepDef[] = [Q_ROOM_TYPE];
    // Scope first — gates budget minimum and whether bed_size is needed.
    steps.push(Q_SCOPE);
    if (roomType === "bedroom" && needsBedSize) steps.push(Q_BED_SIZE);
    const qCore = roomType === "living_room" ? Q_CORE_LIVING_ROOM : Q_CORE_BEDROOM;
    steps.push(
      Q_BUDGET,
      qCore, Q_MOOD, Q_PALETTE, Q_MATERIALS, Q_SHAPE,
    );
    // Preference steps — full-room only.
    // Partial-room users expressed preferences via the item picker in scope.
    if (fullRoom && roomType === "bedroom") {
      steps.push(Q_BEDDING_TYPE, Q_LIGHTING_TYPES, Q_DESK_PREF, Q_MIRROR_PREF);
    }
    if (fullRoom && roomType === "living_room") {
      steps.push(Q_ENTERTAINMENT_PREF);
      if (entertainmentPref === "yes") {
        steps.push(Q_SCREEN_SIZE, Q_TV_PLACEMENT);
      }
      steps.push(Q_BOOKSHELF_PREF, Q_SEATING_PREF, Q_LR_LIGHTING_TYPES);
    }
    // Density AFTER preferences — controls ambient items (plants, curtains,
    // throw) that preferences don't address.
    steps.push(Q_DENSITY);
    steps.push(
      Q_BRIDGE, Q_INTERESTS, Q_SUBS,
      Q_FREETEXT,
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
      case "bedding_type": return beddingType;
      case "lighting_types": return lightingTypes;
      case "desk_pref": return deskPref;
      case "mirror_pref": return mirrorPref;
      case "entertainment_pref": return entertainmentPref;
      case "screen_size": return screenSize;
      case "tv_placement": return tvPlacement;
      case "bookshelf_pref": return bookshelfPref;
      case "seating_pref": return seatingPref;
      case "lr_lighting_types": return lrLightingTypes;
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
      case "bedding_type": setBeddingType(key); break;
      case "lighting_types":
        setLightingTypes((prev) => {
          if (prev.includes(key)) return prev.filter((k) => k !== key);
          return [...prev, key];
        });
        break;
      case "desk_pref": setDeskPref(key); break;
      case "mirror_pref": setMirrorPref(key); break;
      case "entertainment_pref": setEntertainmentPref(key); break;
      case "screen_size": setScreenSize(key); setTvPriority(false); break;
      case "tv_placement": setTvPlacement(key); break;
      case "bookshelf_pref": setBookshelfPref(key); break;
      case "seating_pref": setSeatingPref(key); break;
      case "lr_lighting_types":
        setLrLightingTypes((prev) => {
          if (prev.includes(key)) return prev.filter((k) => k !== key);
          return [...prev, key];
        });
        break;
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
  // Bedding exclusivity: comforter vs duvet system are mutually exclusive.
  const _DUVET_SYSTEM = ["duvet_insert", "duvet_cover"];
  function toggleWant(item: string) {
    setWants((prev) => {
      if (prev.includes(item)) {
        return prev.filter((i) => i !== item);
      }
      let next = [...prev, item];
      // Enforce bedding exclusivity
      if (item === "comforter") {
        next = next.filter((i) => !_DUVET_SYSTEM.includes(i));
      } else if (_DUVET_SYSTEM.includes(item)) {
        next = next.filter((i) => i !== "comforter");
      }
      return next;
    });
  }

  function toggleWantGroup(items: string[]) {
    // For "select all" check, ignore the mutually-exclusive bedding items
    // so the group can toggle cleanly.
    const checkableItems = items.filter((i) => !_DUVET_SYSTEM.includes(i));
    const allSelected = checkableItems.every((i) => wants.includes(i));
    if (allSelected) {
      setWants((prev) => prev.filter((i) => !items.includes(i)));
    } else {
      // When selecting the whole bed group, default to comforter (exclude duvet system)
      const toAdd = items.filter((i) => !_DUVET_SYSTEM.includes(i));
      setWants((prev) => Array.from(new Set([...prev, ...toAdd])));
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
      case "budget": {
        if (budget <= 0) return false;
        if (fullRoom) return budget >= 1000;
        return true;
      }
      case "core": return core !== "";
      case "mood": return mood !== "";
      case "palette": return palette !== "";
      case "materials": return materials.length > 0;
      case "shape": return shape !== "";
      case "density": return density !== "";
      case "bedding_type": return beddingType !== "";
      case "lighting_types": return lightingTypes.length > 0;
      case "desk_pref": return deskPref !== "";
      case "mirror_pref": return mirrorPref !== "";
      case "entertainment_pref": return entertainmentPref !== "";
      case "screen_size": {
        if (screenSize === "") return false;
        const minBudget = ({ small: 750, medium: 1500, large: 2000, xl: 3000 } as Record<string, number>)[screenSize];
        if (minBudget && budget < minBudget && !tvPriority) return false;
        return true;
      }
      case "tv_placement": return tvPlacement !== "";
      case "bookshelf_pref": return bookshelfPref !== "";
      case "seating_pref": return seatingPref !== "";
      case "lr_lighting_types": return lrLightingTypes.length > 0;
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
      const summary = buildSummary(core, mood, palette, roomType);
      const interestOutput = interests.map((cat) => ({
        category: cat,
        tags: interestTags[cat] ?? [],
      }));

      // Compute excluded slots from preference answers.
      // Only on full-room path — partial-room uses wants (item picker) instead.
      const excluded: string[] = [];
      if (fullRoom && roomType === "bedroom") {
        // Bedding: comforter vs duvet — exclude the one not picked.
        // Each direction explicitly named so empty state excludes nothing.
        if (beddingType === "comforter") {
          excluded.push("duvet_insert", "duvet_cover");
        } else if (beddingType === "duvet") {
          excluded.push("comforter");
        }
        // Lighting: exclude types not selected (only if user made a selection)
        if (lightingTypes.length > 0) {
          if (!lightingTypes.includes("ceiling_light")) excluded.push("ceiling_light");
          if (!lightingTypes.includes("table_lamp")) excluded.push("table_lamp");
          if (!lightingTypes.includes("floor_lamp")) excluded.push("floor_lamp");
          if (!lightingTypes.includes("sconce")) excluded.push("sconce");
        }
        // Desk
        if (deskPref === "no") excluded.push("desk", "desk_chair");
        // Mirror
        if (mirrorPref === "none") excluded.push("mirror");
      }

      if (fullRoom && roomType === "living_room") {
        // Mirror — always excluded from living room
        excluded.push("mirror");
        // Entertainment
        if (entertainmentPref === "no") {
          excluded.push("tv", "tv_stand", "tv_mount");
        } else {
          // Stand XOR mount
          if (tvPlacement === "stand") excluded.push("tv_mount");
          if (tvPlacement === "mount") excluded.push("tv_stand");
        }
        // Bookshelf
        if (bookshelfPref === "no") excluded.push("bookshelf");
        // Seating
        if (seatingPref === "sofa_only") excluded.push("armchair");
        // Lighting
        if (lrLightingTypes.length > 0) {
          if (!lrLightingTypes.includes("ceiling_light")) excluded.push("ceiling_light");
          if (!lrLightingTypes.includes("floor_lamp")) excluded.push("floor_lamp");
          if (!lrLightingTypes.includes("table_lamp")) excluded.push("table_lamp");
        }
      }

      onComplete({
        roomType,
        bedSize,
        budget,
        fullRoom,
        wants,
        excludedSlots: excluded,
        mirrorType: mirrorPref && mirrorPref !== "none" && mirrorPref !== "any" ? mirrorPref : null,
        screenSize: entertainmentPref === "yes" && screenSize ? screenSize : null,
        tvPriority: tvPriority,
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
    // Bridge — style recap + transition to interests
    if (current.layout === "bridge") {
      const coreStep = roomType === "living_room" ? Q_CORE_LIVING_ROOM : Q_CORE_BEDROOM;
      const coreOpt = coreStep.options.find((o) => o.key === core);
      const moodOpt = Q_MOOD.options.find((o) => o.key === mood);
      const paletteOpt = Q_PALETTE.options.find((o) => o.key === palette);
      const coreImg = coreOpt?.image
        ? `/quiz/${roomType}/${coreOpt.image}`
        : null;

      return (
        <div className="bridge-preview">
          {coreImg && (
            <div className="bridge-image">
              <Image
                src={coreImg}
                alt={coreOpt?.label ?? "Your aesthetic"}
                width={400}
                height={400}
                style={{ objectFit: "cover", width: "100%", height: "100%", borderRadius: "10px" }}
              />
            </div>
          )}
          <div className="bridge-details">
            {coreOpt && (
              <span className="bridge-aesthetic">{coreOpt.label}</span>
            )}
            {moodOpt && (
              <span className="bridge-mood">{moodOpt.label}</span>
            )}
            {paletteOpt && (
              <div className="bridge-swatches">
                {paletteOpt.swatches.map((c, i) => (
                  <div key={i} className="bridge-swatch" style={{ background: c }} />
                ))}
                <span className="bridge-palette-label">{paletteOpt.label}</span>
              </div>
            )}
          </div>
        </div>
      );
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

          {/* Budget warnings */}
          {fullRoom && budget > 0 && budget < 1000 && (
            <div style={{ marginTop: "1rem", padding: "0.75rem 1rem", background: "rgba(185, 28, 28, 0.08)", border: "1px solid rgba(185, 28, 28, 0.25)", borderRadius: "0.5rem", fontSize: "0.88rem", lineHeight: 1.5, color: "#7F1D1D" }}>
              <strong>Full-room designs need at least $1,000.</strong>
              {" "}Increase your budget or go back and choose specific pieces instead.
            </div>
          )}
          {!fullRoom && budget > 0 && budget < 500 && (
            <div style={{ marginTop: "1rem", padding: "0.75rem 1rem", background: "rgba(180, 83, 9, 0.08)", border: "1px solid rgba(180, 83, 9, 0.25)", borderRadius: "0.5rem", fontSize: "0.88rem", lineHeight: 1.5, color: "#78350F" }}>
              At low budgets, some items may not generate — we&#39;ll do our best with what&#39;s available.
            </div>
          )}
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
              <span className="scope-choice-label"><strong>Design my whole room</strong> <span style={{ fontWeight: 400, fontSize: "0.8rem", opacity: 0.55 }}>(recommended)</span></span>
              <span className="scope-choice-desc">We&#39;ll source everything from scratch.</span>
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
                      {group.items.map((item) => {
                        // Bedding exclusivity: disable the other system's chips
                        const comforterSelected = wants.includes("comforter");
                        const duvetSelected = _DUVET_SYSTEM.some((s) => wants.includes(s));
                        const disabled =
                          (item === "comforter" && duvetSelected) ||
                          (_DUVET_SYSTEM.includes(item) && comforterSelected);
                        return (
                        <button
                          key={item}
                          type="button"
                          className={`ownership-chip ${wants.includes(item) ? "selected" : ""}`}
                          onClick={() => !disabled && toggleWant(item)}
                          style={disabled ? { opacity: 0.35, cursor: "not-allowed" } : undefined}
                          title={disabled ? "Can't use both comforter and duvet" : undefined}
                        >
                          <svg className="chip-check" viewBox="0 0 14 14" fill="none">
                            <path d="M2.5 7.5L5.5 10.5L11.5 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                          {item.replace(/_/g, " ")}
                        </button>
                        );
                      })}
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
        return <p className="quiz-hint">No interests selected. Hit Next to continue.</p>;
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

    // Select cards (room type, bed size, yes/no prefs)
    if (current.layout === "select-cards") {
      // Budget thresholds per TV size tier.  These are HIGHER than the raw
      // feasibility math (floor / cap) because a technically feasible room
      // with $200 left for all non-TV furniture is junk.  Thresholds are set
      // so the remaining budget after TV produces a decent room.
      // normal: 35% entertainment cap.  priority: 45% cap (user chose lean room).
      const TV_MIN_BUDGETS: Record<string, number> = {
        small: 750, medium: 1500, large: 2000, xl: 3000,
      };
      const TV_PRIORITY_MIN: Record<string, number> = {
        small: 820, medium: 1000, large: 1250, xl: 1750,
      };
      const TIER_DOWN: Record<string, string> = {
        xl: "large", large: "medium", medium: "small",
      };
      const SIZE_LABELS: Record<string, string> = {
        small: "32–43\"", medium: "50–55\"", large: "65\"", xl: "75\"+",
      };

      const belowNormal =
        current.id === "screen_size" &&
        screenSize !== "" &&
        TV_MIN_BUDGETS[screenSize] !== undefined &&
        budget < TV_MIN_BUDGETS[screenSize];
      const canPrioritize =
        belowNormal &&
        TV_PRIORITY_MIN[screenSize] !== undefined &&
        budget >= TV_PRIORITY_MIN[screenSize];
      // Warning shows if below normal threshold AND user hasn't resolved it
      // by clicking "Prioritize" (which is only valid when canPrioritize).
      const tvBudgetWarning = belowNormal && !(tvPriority && canPrioritize);
      const tvPriorityConfirmed = belowNormal && tvPriority && canPrioritize;
      const tvMinBudget = TV_MIN_BUDGETS[screenSize] ?? 0;
      const smallerTier = TIER_DOWN[screenSize] ?? "";

      return (
        <div className="quiz-select-grid">
          {options.map((opt) => (
            <SelectCard
              key={opt.key}
              option={opt}
              selected={isSelected(current.id, opt.key)}
              onClick={() => toggleSelection(current.id, opt.key)}
              imagePrefix={imagePrefix}
            />
          ))}
          {tvBudgetWarning && (
            <div style={{ gridColumn: "1 / -1", marginTop: "0.5rem", padding: "0.75rem 1rem", background: "rgba(180, 83, 9, 0.08)", border: "1px solid rgba(180, 83, 9, 0.25)", borderRadius: "0.5rem", fontSize: "0.88rem", lineHeight: 1.5, color: "#78350F" }}>
              <strong>Tight fit.</strong>{" "}
              A {SIZE_LABELS[screenSize] ?? screenSize} TV works best with a
              ${tvMinBudget.toLocaleString()}+ budget.
              <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem", flexWrap: "wrap" }}>
                <button
                  type="button"
                  onClick={() => {
                    setBudget(tvMinBudget);
                    setBudgetText(tvMinBudget.toLocaleString());
                    setTvPriority(false);
                  }}
                  style={{ padding: "0.4rem 0.85rem", borderRadius: "0.375rem", border: "1px solid rgba(180, 83, 9, 0.4)", background: "rgba(180, 83, 9, 0.12)", color: "#78350F", cursor: "pointer", fontSize: "0.84rem", fontWeight: 500 }}
                >
                  Expand budget to ${tvMinBudget.toLocaleString()}
                </button>
                {smallerTier && (
                  <button
                    type="button"
                    onClick={() => {
                      setScreenSize(smallerTier);
                      setTvPriority(false);
                    }}
                    style={{ padding: "0.4rem 0.85rem", borderRadius: "0.375rem", border: "1px solid rgba(180, 83, 9, 0.4)", background: "rgba(180, 83, 9, 0.12)", color: "#78350F", cursor: "pointer", fontSize: "0.84rem", fontWeight: 500 }}
                  >
                    Go {SIZE_LABELS[smallerTier] ?? smallerTier} instead
                  </button>
                )}
                {canPrioritize && (
                  <button
                    type="button"
                    onClick={() => {
                      setTvPriority(true);
                    }}
                    style={{ padding: "0.4rem 0.85rem", borderRadius: "0.375rem", border: "1px solid rgba(180, 83, 9, 0.4)", background: "rgba(180, 83, 9, 0.12)", color: "#78350F", cursor: "pointer", fontSize: "0.84rem", fontWeight: 500 }}
                  >
                    Prioritize the TV (leaner room)
                  </button>
                )}
              </div>
            </div>
          )}
          {tvPriorityConfirmed && (
            <div style={{ gridColumn: "1 / -1", marginTop: "0.5rem", padding: "0.75rem 1rem", background: "rgba(22, 101, 52, 0.08)", border: "1px solid rgba(22, 101, 52, 0.25)", borderRadius: "0.5rem", fontSize: "0.88rem", lineHeight: 1.5, color: "#14532D" }}>
              <strong>TV prioritized.</strong>{" "}
              Your room will be leaner to fund the {SIZE_LABELS[screenSize] ?? screenSize} screen.
              <button
                type="button"
                onClick={() => setTvPriority(false)}
                style={{ marginLeft: "0.75rem", padding: "0.25rem 0.6rem", borderRadius: "0.375rem", border: "1px solid rgba(22, 101, 52, 0.3)", background: "transparent", color: "#14532D", cursor: "pointer", fontSize: "0.82rem" }}
              >
                Undo
              </button>
            </div>
          )}
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

    // Image cards (core, mood, palette, materials, shape, preferences)
    return (
      <div className="quiz-card-grid" data-count={options.length}>
        {options.map((opt) => (
          <QuizImageCard
            key={opt.key}
            option={opt}
            selected={isSelected(current.id, opt.key)}
            onClick={() => toggleSelection(current.id, opt.key, current.maxSelect)}
            imagePrefix={imagePrefix}
            selectMode={current.selectMode}
          />
        ))}
      </div>
    );
  }

  const progressPct = ((stepIndex + 1) / totalSteps) * 100;
  const isLastStep = stepIndex === totalSteps - 1;

  // Section label based on current step
  const SETUP_IDS = new Set(["room_type", "bed_size", "budget"]);
  const STYLE_IDS = new Set(["core", "mood", "palette", "materials", "shape"]);
  const PREF_IDS = new Set(["scope", "bedding_type", "lighting_types", "desk_pref", "mirror_pref", "entertainment_pref", "screen_size", "tv_placement", "bookshelf_pref", "seating_pref", "lr_lighting_types", "density"]);
  const sectionLabel = SETUP_IDS.has(current.id) ? "Setup"
    : STYLE_IDS.has(current.id) ? "Style"
    : PREF_IDS.has(current.id) ? "Preferences"
    : "Finishing up";

  return (
    <div className="quiz-container">
      <div className="quiz-progress">
        <div className="quiz-progress-track">
          <div className="quiz-progress-fill" style={{ width: `${progressPct}%` }} />
        </div>
        <span className="quiz-progress-label">{sectionLabel}</span>
      </div>

      <h2 className="quiz-question">{current.question}</h2>
      {(current.hint || current.selectMode === "multi") && (
        <p className="quiz-hint">
          {current.hint || (current.maxSelect ? `Pick up to ${current.maxSelect}` : "Select all that apply")}
        </p>
      )}

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
