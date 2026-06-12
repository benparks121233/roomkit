export type RenderMode = "svg" | "ai";

export interface RoomSceneProps {
  /** Which slots have been selected (slot_id → selected items). Only length matters. */
  selections: Record<string, unknown[]>;
  /** The slot currently being picked (dashed highlight zone). */
  currentSlotId: string | null;
  /** Full ordered list of active slot IDs. */
  activeSlotIds: string[];
  /** "svg" = cartoon illustration, "ai" = future AI-generated image. */
  renderMode?: RenderMode;
}
