"use client";

import Image from "next/image";
import { useState } from "react";

const SHOWCASE = [
  { src: "/renders/showcase_japandi_lr.jpg",        label: "Japandi",       room: "Living Room" },
  { src: "/renders/showcase_city_modern_br.jpg",     label: "City Modern",   room: "Bedroom" },
  { src: "/renders/showcase_dark_academia_br.jpg",   label: "Dark Academia", room: "Bedroom" },
  { src: "/renders/showcase_quiet_luxury_br.jpg",    label: "Quiet Luxury",  room: "Bedroom" },
];

const SWITCHER_AESTHETICS: { key: string; label: string; vibe: string; story: string }[] = [
  {
    key: "cottagecore",
    label: "Cottagecore",
    vibe: "Soft + vintage",
    story: "You wake up slow. Sun through linen curtains, a mug of tea already cooling on the nightstand. The wool throw is half on the floor because you actually slept under it. The room smells like dried flowers and old books and you have absolutely nowhere to be.",
  },
  {
    key: "dark_academia",
    label: "Dark Academia",
    vibe: "Moody + scholarly",
    story: "It's 1am and you're in the zone. The desk lamp throws a warm circle across your notebook. Velvet sheets, a green banker's lamp, the faint smell of leather binding. You could be in a flat above a bookshop in Edinburgh. The world outside doesn't exist right now.",
  },
  {
    key: "japandi",
    label: "Japandi",
    vibe: "Calm + minimal",
    story: "You take a breath and the room gives you space for it. Light oak, clean lines, nothing fighting for your attention. The linen duvet is still warm. Your coffee is on a side table that has nothing else on it. This is what Monday morning is supposed to feel like.",
  },
  {
    key: "coastal",
    label: "Coastal",
    vibe: "Breezy + light",
    story: "The window is cracked and you can almost hear the waves. White sheets kicked sideways, a woven basket in the corner, the kind of light that makes everything look golden. You're on your second day of vacation except you live here. Every morning is the first morning.",
  },
  {
    key: "industrial",
    label: "Industrial",
    vibe: "Raw + rugged",
    story: "Exposed brick, black steel, the hum of the city outside. The leather armchair has your shape worn into it. You built this room the way you'd build a motorcycle — nothing extra, everything functional, and it looks better with every scratch.",
  },
  {
    key: "quiet_luxury",
    label: "Quiet Luxury",
    vibe: "Polished + serene",
    story: "You run your hand across the bedding and it's cashmere. The marble nightstand catches the morning light. Nothing in this room is trendy, nothing is loud, and nothing cost less than it should have. People walk in and just get quiet. That's the point.",
  },
  {
    key: "city_modern",
    label: "City Modern",
    vibe: "Sleek + urban",
    story: "32nd floor, floor-to-ceiling glass, the skyline doing its thing. Everything in here is sharp — matte black frames, white sheets pulled tight, geometric lines. You get dressed in this room and you walk out feeling like you own the building.",
  },
  {
    key: "ski_lodge",
    label: "Ski Lodge",
    vibe: "Cozy + alpine",
    story: "Your legs are still burning from the last run. You're under a plaid duvet with timber beams overhead and you can hear the fire downstairs. The flannel is warm, the wool is heavy, and you're not moving from this spot until someone brings you hot chocolate.",
  },
  {
    key: "jungle_oasis",
    label: "Jungle Oasis",
    vibe: "Lush + tropical",
    story: "The monstera is taller than you now. Rattan creaks when you sit down, the air feels thicker, greener. There's a trailing pothos above the headboard that you haven't killed yet and it feels like a personal victory. This room doesn't have a vibe — it has an ecosystem.",
  },
  {
    key: "gamer_den",
    label: "Gamer Den",
    vibe: "Dark + techy",
    story: "Blackout curtains, ambient glow, three monitors and a chair that cost more than the bed. It's 2am and you just hit your stride. The only light is the one you chose. Nobody's knocking. The world is exactly the size of this room and that's perfect.",
  },
  {
    key: "sports_den",
    label: "Sports Den",
    vibe: "Dark + loungey",
    story: "Game day. The leather couch has seen a hundred Sundays. The TV is too big and that's the whole idea. There's a cooler within arm's reach and the remote hasn't moved since Tuesday. This room was built around one activity and it does that activity flawlessly.",
  },
  {
    key: "poster_maximalist",
    label: "Poster Maximalist",
    vibe: "Eclectic + expressive",
    story: "Every wall is a timeline of the things you love. That concert you'll never forget. The movie poster your roommate tried to throw away. A vintage print from a flea market you found at 7am on a Saturday. People walk in and spend twenty minutes just reading the walls.",
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
          Design your dream room.
        </h1>
        <p className="landing-hero-subtitle">
          You pick the vibe. We fill the room — real furniture, real prices, one click to buy any piece. Your style, your budget, nothing fake.
        </p>
        <a href="/design" className="landing-cta">Design my room</a>
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
              <p className="landing-room-card-desc">13 aesthetics, full room</p>
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
              <p className="landing-room-card-desc">13 aesthetics, full room</p>
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
              <h3 className="landing-hiw-title">Tell us your style</h3>
              <p className="landing-hiw-desc">
                A quick visual quiz — pick aesthetics, moods, materials, colors. No measurements, no Pinterest boards, no design degree. Just tap what feels right. Two minutes and we know your taste better than your roommate does.
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
              <h3 className="landing-hiw-title">We build the room</h3>
              <p className="landing-hiw-desc">
                AI pulls from thousands of real products, matches them to your style, and assembles a complete room that actually works together. Every piece fits, every color coordinates, and nothing blows the budget. Then we render it so you can see the whole thing.
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
              <h3 className="landing-hiw-title">Shop every piece</h3>
              <p className="landing-hiw-desc">
                Your room is a shopping list. Every item has a live link and a real price. Don&#39;t love the rug? Swap it. Want to splurge on the desk? Go for it. Buy one piece or buy them all — the room is the menu, you choose what to order.
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
