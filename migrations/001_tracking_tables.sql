-- RoomKit tracking schema v1
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New query)

-- =========================================================================
-- TABLE 1: selections
-- One row per SLOT per run. Denormalized for easy aggregation.
-- =========================================================================
create table if not exists selections (
  id            bigint generated always as identity primary key,
  run_id        text not null,
  created_at    timestamptz not null default now(),

  -- Room context
  room_type     text not null,                  -- 'bedroom', 'living_room'
  aesthetic     text not null,                  -- 'japandi', 'gamer_den', etc.
  mood          text,                           -- 'calm, grounded, uncluttered'
  color_palette text[],                         -- {'cream','oak','sage'}
  keywords      text[],                         -- {'minimalist','zen','clean'}
  budget        numeric(10,2) not null,         -- user's total budget

  -- Slot + product
  slot_id       text not null,                  -- 'bed_frame', 'wall_art', etc.
  product_id    text not null,                  -- Amazon ASIN
  product_name  text not null,
  product_price numeric(10,2) not null,
  retailer      text not null default 'amazon', -- future: multi-retailer
  is_multiselect boolean not null default false  -- wall_art/plants = true
);

-- Indexes for the key aggregation queries
create index if not exists idx_selections_run     on selections (run_id);
create index if not exists idx_selections_slot    on selections (slot_id, aesthetic);
create index if not exists idx_selections_product on selections (product_id);
create index if not exists idx_selections_created on selections (created_at);


-- =========================================================================
-- TABLE 2: events
-- One row per funnel event. Append-only event log.
-- =========================================================================
create table if not exists events (
  id            bigint generated always as identity primary key,
  run_id        text not null,
  created_at    timestamptz not null default now(),

  -- Event classification
  event_type    text not null,
  -- Valid event_type values:
  --   'design_started'       — user submitted the intake form
  --   'design_completed'     — pipeline finished, selections returned
  --   'render_requested'     — user clicked "See your room"
  --   'render_generated'     — render API returned successfully
  --   'render_viewed'        — render image loaded in browser
  --   'hotspot_clicked'      — user clicked a product hotspot on render
  --   'export_cart_clicked'  — user clicked "Add all to Amazon cart"
  --   'buy_link_clicked'     — user clicked a product buy link

  -- Event-specific payload (flexible JSONB)
  data          jsonb default '{}',
  -- Examples:
  --   design_started:    {"room_type": "bedroom", "budget": 1500, "aesthetic": "japandi"}
  --   design_completed:  {"slot_count": 15, "total_spent": 1423.50, "api_cost": 0.27}
  --   render_requested:  {}
  --   render_generated:  {"render_cost": 0.10, "cached": false}
  --   hotspot_clicked:   {"slot_id": "bed_frame", "product_id": "B0CX3DFHTS"}
  --   buy_link_clicked:  {"slot_id": "wall_art", "product_id": "B09XYZ", "price": 29.99}
  --   export_cart_clicked: {"product_count": 16, "total_price": 1423.50}

  -- Cost tracking (only set for cost-bearing events)
  api_cost      numeric(8,4)                    -- e.g. 0.2300 for selection LLM cost
);

-- Indexes for funnel queries
create index if not exists idx_events_run      on events (run_id);
create index if not exists idx_events_type     on events (event_type);
create index if not exists idx_events_created  on events (created_at);


-- =========================================================================
-- GRANTS — service_role needs explicit access to tables created by postgres
-- =========================================================================
grant all on selections to service_role;
grant all on events to service_role;
grant usage, select on all sequences in schema public to service_role;
