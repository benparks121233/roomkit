"use client";

import Image from "next/image";
import { useState } from "react";

const SHOWCASE = [
  { src: "/renders/showcase_coastal_br.jpg",         label: "Coastal",       room: "Bedroom" },
  { src: "/renders/showcase_dark_academia_lr.jpg",   label: "Dark Academia", room: "Living Room" },
  { src: "/renders/showcase_quiet_luxury_br.jpg",    label: "Quiet Luxury",  room: "Bedroom" },
  { src: "/renders/showcase_cottagecore_lr.jpg",     label: "Cottagecore",   room: "Living Room" },
];

const SWITCHER_AESTHETICS: { key: string; label: string; vibe: string; story: string }[] = [
  {
    key: "cottagecore",
    label: "Cottagecore",
    vibe: "Soft + vintage",
    story: "Sunday morning. Sun through linen curtains, tea on the nightstand. The wool throw is half on the floor because you actually used it. Everything in here is soft and a little worn and you wouldn't change a single thing.",
  },
  {
    key: "dark_academia",
    label: "Dark Academia",
    vibe: "Moody + scholarly",
    story: "It's late and you're in the zone. Desk lamp on, everything else off. The room feels like a library you're not supposed to be in after hours. Dark wood, warm leather, green glass. You could stay here all night and honestly you probably will.",
  },
  {
    key: "japandi",
    label: "Japandi",
    vibe: "Calm + minimal",
    story: "Light oak, clean lines, nothing competing for your attention. The coffee is on a side table that has nothing else on it. Everything in this room earns its spot and the empty space is the whole point.",
  },
  {
    key: "coastal",
    label: "Coastal",
    vibe: "Breezy + light",
    story: "White sheets, cracked window, that golden hour light that makes everything look warm. Woven textures, weathered wood, the kind of room that makes a Tuesday morning feel like vacation. You live here but it never stops feeling like you just arrived.",
  },
  {
    key: "industrial",
    label: "Industrial",
    vibe: "Raw + rugged",
    story: "Exposed brick, black steel, concrete where other people would put drywall. The leather chair has your shape worn into it. Nothing in here is decorative. Everything just works, and it all looks better the more you use it.",
  },
  {
    key: "quiet_luxury",
    label: "Quiet Luxury",
    vibe: "Polished + serene",
    story: "Cashmere bedding, marble surfaces, nothing loud. The room doesn't try to impress you. It just feels expensive in the way that good things do when they're not trying to prove anything. People walk in and get quiet.",
  },
  {
    key: "city_modern",
    label: "City Modern",
    vibe: "Sleek + urban",
    story: "High floor, big windows, the city doing its thing below. Matte black frames, white sheets pulled tight, clean geometric lines. You get ready in this room and walk out feeling like the main character.",
  },
  {
    key: "ski_lodge",
    label: "Ski Lodge",
    vibe: "Cozy + alpine",
    story: "Timber beams overhead, plaid duvet pulled up, the kind of heavy wool blanket that pins you to the bed. It's cold outside and warm in here and you're not going anywhere. The whole room feels like the last hour of a ski day.",
  },
  {
    key: "jungle_oasis",
    label: "Jungle Oasis",
    vibe: "Lush + tropical",
    story: "Plants everywhere and somehow they're all alive. Rattan, terracotta, woven textures that make the whole room feel warmer. The light comes through leaves before it hits the floor. Walking in here after a long day genuinely changes your mood.",
  },
  {
    key: "gamer_den",
    label: "Gamer Den",
    vibe: "Dark + techy",
    story: "Blackout curtains, ambient glow, the chair costs more than the bed and that's on purpose. It's late and you just hit your stride. The only light is the one you chose. The whole world is the size of this room right now.",
  },
  {
    key: "sports_den",
    label: "Sports Den",
    vibe: "Dark + loungey",
    story: "Game day. The leather couch has seen a hundred Sundays. The TV is too big and that's the whole point. Everything you need is within arm's reach. This room was built for one thing and it does that thing perfectly.",
  },
  {
    key: "poster_maximalist",
    label: "Poster Maximalist",
    vibe: "Eclectic + expressive",
    story: "Every wall tells on you. The concert poster, the vintage find from that flea market, the print your roommate tried to throw out. Nothing matches and that's what makes it yours. People come over and spend the first twenty minutes just looking around.",
  },
];

const DREAM_ROOMS = [
  { key: "bedroom",     label: "Bedroom",     available: true },
  { key: "living_room", label: "Living Room", available: true },
  { key: "kitchen",     label: "Kitchen",      available: false },
  { key: "office",      label: "Office",       available: false },
  { key: "bathroom",    label: "Bathroom",     available: false },
];

export default function LandingPage() {
  const [activeAesthetic, setActiveAesthetic] = useState("japandi");
  const active = SWITCHER_AESTHETICS.find((a) => a.key === activeAesthetic)!;

  return (
    <div className="landing">
      {/* ── Hero ── */}
      <section className="landing-hero">
        <h1 className="landing-hero-title">
          Your room, actually designed.
        </h1>
        <p className="landing-hero-subtitle">
          Tell us your style and budget. We'll put together a full room of real furniture you can buy in one tap.
        </p>
        <a href="/design" className="landing-cta">Design my room</a>
        <p className="landing-hero-free">Your first room is free. No credit card needed.</p>
      </section>

      {/* ── Room type cards ── */}
      <section className="landing-section">
        <div className="landing-hero-cards">
          <a href="/design?room=bedroom" className="landing-room-card">
            <div className="landing-room-card-image">
              <Image
                src="/quiz/room_bedroom.jpg"
                alt="Bedroom"
                width={560}
                height={373}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            </div>
            <div className="landing-room-card-body">
              <h3 className="landing-room-card-title">Design a bedroom</h3>
              <p className="landing-room-card-desc">12 aesthetics, full room</p>
            </div>
          </a>
          <a href="/design?room=living_room" className="landing-room-card">
            <div className="landing-room-card-image">
              <Image
                src="/quiz/room_living_room.jpg"
                alt="Living Room"
                width={560}
                height={373}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            </div>
            <div className="landing-room-card-body">
              <h3 className="landing-room-card-title">Design a living room</h3>
              <p className="landing-room-card-desc">12 aesthetics, full room</p>
            </div>
          </a>
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="landing-section">
        <h2 className="landing-section-title">How it works</h2>
        <div className="landing-hiw">

          {/* Step 1: Quiz mockup */}
          <div className="landing-hiw-step">
            <div className="landing-hiw-visual">
              <div className="hiw-mock-quiz">
                <div className="hiw-mock-quiz-q">What&#39;s your vibe?</div>
                <div className="hiw-mock-quiz-grid">
                  {["Cottagecore", "Dark Academia", "Japandi", "Coastal"].map((name, i) => (
                    <div key={name} className={`hiw-mock-quiz-card${i === 2 ? " selected" : ""}`}>
                      <div className="hiw-mock-quiz-card-img">
                        <Image
                          src={`/quiz/bedroom/core_${name.toLowerCase().replace(/ /g, "_")}.jpg`}
                          alt={name}
                          width={120}
                          height={120}
                          style={{ width: "100%", height: "100%", objectFit: "cover" }}
                        />
                      </div>
                      <span className="hiw-mock-quiz-card-label">{name}</span>
                    </div>
                  ))}
                </div>
                <div className="hiw-mock-quiz-progress">
                  <div className="hiw-mock-quiz-progress-fill" style={{ width: "30%" }} />
                </div>
              </div>
            </div>
            <div className="landing-hiw-content">
              <span className="landing-hiw-number">1</span>
              <h3 className="landing-hiw-title">Take the quiz</h3>
              <p className="landing-hiw-desc">
                Pick aesthetics, moods, materials, colors. No Pinterest boards, no design degree. Just tap what looks good to you. Takes about two minutes.
              </p>
            </div>
          </div>

          {/* Step 2: Room materializing */}
          <div className="landing-hiw-step reverse">
            <div className="landing-hiw-visual">
              <div className="hiw-mock-room">
                <div className="hiw-mock-room-render">
                  <Image
                    src="/renders/showcase_dark_academia_br.jpg"
                    alt="Your room taking shape"
                    width={480}
                    height={320}
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                  />
                  <div className="hiw-mock-room-overlay">
                    <div className="hiw-mock-room-tag" style={{ top: "35%", left: "20%" }}>Desk</div>
                    <div className="hiw-mock-room-tag" style={{ top: "45%", left: "48%" }}>Bed Frame</div>
                    <div className="hiw-mock-room-tag" style={{ top: "20%", left: "55%" }}>Wall Art</div>
                    <div className="hiw-mock-room-tag" style={{ top: "60%", left: "75%" }}>Dresser</div>
                  </div>
                </div>
              </div>
            </div>
            <div className="landing-hiw-content">
              <span className="landing-hiw-number">2</span>
              <h3 className="landing-hiw-title">We put the room together</h3>
              <p className="landing-hiw-desc">
                We pull from thousands of real products and build a complete room around your taste. Everything coordinates, everything fits the budget, and you get a render of the whole thing so you can see it before you buy anything.
              </p>
            </div>
          </div>

          {/* Step 3: Shopping mockup */}
          <div className="landing-hiw-step">
            <div className="landing-hiw-visual">
              <div className="hiw-mock-shop">
                <div className="hiw-mock-shop-header">
                  <span className="hiw-mock-shop-total">$1,247 / $1,500</span>
                  <div className="hiw-mock-shop-bar">
                    <div className="hiw-mock-shop-bar-fill" style={{ width: "83%" }} />
                  </div>
                </div>
                <div className="hiw-mock-shop-grid">
                  {[
                    { slot: "BED FRAME", price: "$289" },
                    { slot: "DUVET SET", price: "$67" },
                    { slot: "RUG", price: "$124" },
                    { slot: "DESK", price: "$199" },
                    { slot: "WALL ART", price: "$45" },
                    { slot: "FLOOR LAMP", price: "$89" },
                  ].map((item) => (
                    <div key={item.slot} className="hiw-mock-shop-card">
                      <div className="hiw-mock-shop-card-img" />
                      <div className="hiw-mock-shop-card-info">
                        <span className="hiw-mock-shop-card-slot">{item.slot}</span>
                        <span className="hiw-mock-shop-card-price">{item.price}</span>
                      </div>
                      <span className="hiw-mock-shop-card-btn">Buy</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="landing-hiw-content">
              <span className="landing-hiw-number">3</span>
              <h3 className="landing-hiw-title">Buy what you want</h3>
              <p className="landing-hiw-desc">
                Every piece has a real price and a link to buy it. Don&#39;t love the rug? Swap it. Want to go big on the desk? Do it. Buy one piece or furnish the whole room.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Render showcase ── */}
      <section className="landing-section">
        <h2 className="landing-section-title">Rooms made with RoomKit</h2>
        <div className="landing-showcase">
          {SHOWCASE.map((s) => (
            <div key={s.src} className="landing-showcase-card">
              <div className="landing-showcase-image">
                <Image
                  src={s.src}
                  alt={`${s.label} ${s.room}`}
                  width={480}
                  height={320}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
              </div>
              <div className="landing-showcase-info">
                <span className="landing-showcase-label">{s.label}</span>
                <span className="landing-showcase-room">{s.room}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Aesthetic switcher ── */}
      <section className="landing-section">
        <h2 className="landing-section-title">Explore the aesthetics</h2>
        <div className="landing-switcher">
          <div className="landing-switcher-left">
            <div className="landing-switcher-preview">
              <Image
                key={activeAesthetic}
                src={`/quiz/bedroom/core_${activeAesthetic}.jpg`}
                alt={active.label}
                width={560}
                height={560}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            </div>
            <div className="landing-switcher-detail">
              <h3 className="landing-switcher-detail-title">{active.label}</h3>
              <span className="landing-switcher-detail-vibe">{active.vibe}</span>
              <p className="landing-switcher-detail-story">{active.story}</p>
            </div>
          </div>
          <div className="landing-switcher-list">
            {SWITCHER_AESTHETICS.map((a) => (
              <button
                key={a.key}
                className={`landing-switcher-btn${activeAesthetic === a.key ? " active" : ""}`}
                onMouseEnter={() => setActiveAesthetic(a.key)}
                onClick={() => setActiveAesthetic(a.key)}
              >
                {a.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ── Dream House ── */}
      <section className="landing-section">
        <h2 className="landing-section-title">Build your dream house</h2>
        <p className="landing-section-subtitle">Design room by room. Combine them into a home.</p>
        <div className="landing-dream-rooms">
          {DREAM_ROOMS.map((r) => (
            <div key={r.key} className={`landing-dream-room${r.available ? "" : " coming-soon"}`}>
              {r.available ? (
                <a href={`/design?room=${r.key}`} className="landing-dream-room-inner">
                  <span className="landing-dream-room-label">{r.label}</span>
                  <span className="landing-dream-room-status">Design now</span>
                </a>
              ) : (
                <div className="landing-dream-room-inner">
                  <span className="landing-dream-room-label">{r.label}</span>
                  <span className="landing-dream-room-status">Coming soon</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
