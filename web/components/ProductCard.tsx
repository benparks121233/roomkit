// web/components/ProductCard.tsx
// Single slot card: product image, name, price, "Buy on Amazon" CTA.
// The CTA fires a POST /click event before navigating to the affiliate URL.
// buy_url comes from the ProductSnapshot — never constructed in the frontend.
// Stage 9: implement.

export default function ProductCard({ snapshot }: { snapshot: unknown }) {
  // Stage 9: image, name, price, buy_url (from snapshot), slot_id, run_id
  return <div>ProductCard — Stage 9</div>;
}
