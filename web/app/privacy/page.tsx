export default function PrivacyPage() {
  return (
    <main style={styles.container}>
      <article style={styles.card}>
        <h1 style={styles.title}>Privacy Policy</h1>
        <p style={styles.effective}>Effective date: July 1, 2026</p>

        <p style={styles.paragraph}>
          RoomKit (&quot;we,&quot; &quot;us&quot;) is operated by{" "}
          <strong>the operator of RoomKit</strong>, based in{" "}
          <strong>Illinois</strong>. This policy describes what data
          we collect, why, and how you can control it.
        </p>

        <Section title="What We Collect">
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Data</th>
                <th style={styles.th}>Where stored</th>
                <th style={styles.th}>Why</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={styles.td}>Email address and password hash</td>
                <td style={styles.td}>Supabase auth (hosted Postgres)</td>
                <td style={styles.td}>Account identity and login</td>
              </tr>
              <tr>
                <td style={styles.td}>Age confirmation (checkbox, not date of birth)</td>
                <td style={styles.td}>Supabase auth user metadata</td>
                <td style={styles.td}>COPPA compliance (13+ only)</td>
              </tr>
              <tr>
                <td style={styles.td}>Room designs (style, budget, slot allocations, selected products)</td>
                <td style={styles.td}>Supabase database (designs table)</td>
                <td style={styles.td}>Core product &mdash; your saved rooms</td>
              </tr>
              <tr>
                <td style={styles.td}>Interaction events (design created, finalized, render requested, product link clicked)</td>
                <td style={styles.td}>Supabase database (events table)</td>
                <td style={styles.td}>Internal funnel analytics to improve the product</td>
              </tr>
              <tr>
                <td style={styles.td}>Product selections per slot (product ID, price, aesthetic, mood)</td>
                <td style={styles.td}>Supabase database (selections table)</td>
                <td style={styles.td}>Product recommendation improvement</td>
              </tr>
              <tr>
                <td style={styles.td}>AI-generated room renders</td>
                <td style={styles.td}>Server filesystem</td>
                <td style={styles.td}>Visual output for your design</td>
              </tr>
              <tr>
                <td style={styles.td}>Hotspot overlays (clickable product regions on renders)</td>
                <td style={styles.td}>Server filesystem</td>
                <td style={styles.td}>Interactive product identification in renders</td>
              </tr>
            </tbody>
          </table>
        </Section>

        <Section title="What We Do NOT Collect">
          <p style={styles.paragraph}>
            We do not collect browsing history, device fingerprints, precise
            location, contacts, social media profiles, or payment information.
            We do not use tracking pixels, third-party analytics services
            (Google Analytics, Mixpanel, etc.), or advertising networks.
            The only cookies are Supabase authentication session cookies
            required for login.
          </p>
        </Section>

        <Section title="Third-Party Services">
          <p style={styles.paragraph}>
            We use the following services to operate RoomKit. Each receives only
            the data described below &mdash; none receive your email, name, or
            account identity.
          </p>
          <ul style={styles.list}>
            <li style={styles.li}>
              <strong>Amazon Associates:</strong> Product buy links include our
              affiliate tag. When you click a buy link, Amazon sees the click and
              any resulting purchase. Amazon receives the affiliate tag (site-level,
              not user-level) &mdash; we do not send your email, user ID, or any
              personal information to Amazon.
            </li>
            <li style={styles.li}>
              <strong>OpenAI (gpt-image-1):</strong> Room style descriptions are
              sent to generate renders. No user identity, email, or account
              information is included in these requests.
            </li>
            <li style={styles.li}>
              <strong>Anthropic (Claude):</strong> Style interpretation,
              composition planning, and product selection prompts are sent to
              Claude. No user identity, email, or account information is included
              in these requests.
            </li>
            <li style={styles.li}>
              <strong>Stripe:</strong> Processes payments. When you purchase a
              room pack, Stripe receives your payment method and billing
              information. We do not receive or store your card number. Stripe&apos;s
              privacy policy governs their handling of your payment data.
            </li>
            <li style={styles.li}>
              <strong>Supabase:</strong> Hosts our database and authentication.
              Supabase is the data processor; RoomKit is the data controller.
              Supabase&apos;s privacy policy applies to their infrastructure.
            </li>
          </ul>
        </Section>

        <Section title="How We Use Your Data">
          <ul style={styles.list}>
            <li style={styles.li}>To generate, save, and display your room designs</li>
            <li style={styles.li}>To improve product recommendations and design quality using aggregated interaction data</li>
            <li style={styles.li}>To maintain your account and authenticate your sessions</li>
          </ul>
          <p style={styles.paragraph}>
            We do not sell your data. We do not share your personal information
            with advertisers. RoomKit does not train AI models on your data.
            Our AI providers (Anthropic and OpenAI) do not use API inputs for
            model training under their current API terms.
          </p>
        </Section>

        <Section title="Data Retention">
          <p style={styles.paragraph}>
            Your designs and associated data persist until you delete your
            account. There is no automatic expiration. Render images are stored
            on the server and accessible via an unguessable URL (a unique ID).
            They are not indexed or listed publicly, but anyone with the direct
            URL can view them. Render images are permanently deleted when you
            delete your account.
          </p>
        </Section>

        <Section title="Account Deletion">
          <p style={styles.paragraph}>
            You can permanently delete your account and all associated data from
            the <a href="/account" style={styles.link}>Account page</a>. Deletion
            removes:
          </p>
          <ul style={styles.list}>
            <li style={styles.li}>Your login credentials (email and password hash) from Supabase auth</li>
            <li style={styles.li}>All saved designs from the database</li>
            <li style={styles.li}>All interaction events and product selection records</li>
            <li style={styles.li}>All render images and hotspot overlays from the server</li>
          </ul>
          <p style={styles.paragraph}>
            Deletion is permanent and cannot be undone. All data is removed in a
            single operation &mdash; there is no recovery period.
          </p>
        </Section>

        <Section title="Children's Privacy">
          <p style={styles.paragraph}>
            RoomKit is not intended for children under 13. We require age
            confirmation (13 or older) at signup and do not knowingly collect
            data from anyone under 13. If you believe a child under 13 has
            created an account, contact us and we will delete it.
          </p>
        </Section>

        <Section title="Changes to This Policy">
          <p style={styles.paragraph}>
            If we make material changes, we will update the effective date at the
            top of this page. Continued use of RoomKit after a change constitutes
            acceptance of the updated policy.
          </p>
        </Section>

        <Section title="Contact">
          <p style={styles.paragraph}>
            For privacy questions or data deletion requests, email{" "}
            <strong>privacy@roomkit.studio</strong>.
          </p>
        </Section>

        <a href="/" style={styles.backLink}>Back to RoomKit</a>
      </article>
    </main>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={styles.section}>
      <h2 style={styles.sectionTitle}>{title}</h2>
      {children}
    </section>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: "100vh",
    display: "flex",
    justifyContent: "center",
    background: "#f8f7f4",
    fontFamily: "'DM Sans', sans-serif",
    padding: "60px 20px",
  },
  card: {
    background: "#fff",
    borderRadius: 12,
    padding: "2.5rem 2rem",
    width: "100%",
    maxWidth: 720,
    boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
    alignSelf: "flex-start",
  },
  title: {
    fontFamily: "'DM Serif Display', serif",
    fontSize: "1.8rem",
    margin: 0,
    color: "#1a1a1a",
  },
  effective: {
    color: "#888",
    fontSize: "0.85rem",
    marginTop: 4,
    marginBottom: 32,
  },
  section: {
    marginBottom: 28,
  },
  sectionTitle: {
    fontFamily: "'DM Serif Display', serif",
    fontSize: "1.15rem",
    color: "#1a1a1a",
    marginBottom: 8,
    marginTop: 0,
  },
  paragraph: {
    color: "#444",
    fontSize: "0.9rem",
    lineHeight: 1.65,
    margin: "0 0 12px",
  },
  list: {
    margin: "0 0 12px",
    paddingLeft: 20,
  },
  li: {
    color: "#444",
    fontSize: "0.9rem",
    lineHeight: 1.65,
    marginBottom: 6,
  },
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
    fontSize: "0.85rem",
    marginBottom: 12,
  },
  th: {
    textAlign: "left" as const,
    padding: "8px 10px",
    borderBottom: "2px solid #eee",
    color: "#666",
    fontWeight: 600,
    fontSize: "0.8rem",
    textTransform: "uppercase" as const,
    letterSpacing: "0.03em",
  },
  td: {
    padding: "8px 10px",
    borderBottom: "1px solid #f0f0f0",
    color: "#444",
    verticalAlign: "top" as const,
  },
  link: {
    color: "#1a1a1a",
    fontWeight: 600,
  },
  backLink: {
    display: "block",
    textAlign: "center" as const,
    marginTop: 32,
    color: "#888",
    fontSize: "0.85rem",
    textDecoration: "none",
  },
};
