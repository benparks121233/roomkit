import { SCENE } from "./constants";
import type { RoomSceneProps } from "./types";
import RoomBackground from "./RoomBackground";
import SlotHighlight from "./SlotHighlight";

// Pieces (layer 1–6)
import Rug from "./pieces/Rug";
import BedFrame from "./pieces/BedFrame";
import Nightstand from "./pieces/Nightstand";
import Dresser from "./pieces/Dresser";
import Mattress from "./pieces/Mattress";
import Sheets from "./pieces/Sheets";
import Comforter from "./pieces/Comforter";
import Pillows from "./pieces/Pillows";
import TableLamp from "./pieces/TableLamp";
import ThrowBlanket from "./pieces/ThrowBlanket";
import FloorLamp from "./pieces/FloorLamp";
import Mirror from "./pieces/Mirror";
import Curtains from "./pieces/Curtains";
import CeilingLight from "./pieces/CeilingLight";

// Multi-select zones
import GalleryWallZone from "./zones/GalleryWallZone";
import PlantZone from "./zones/PlantZone";

export default function RoomScene({
  selections,
  currentSlotId,
  renderMode = "svg",
}: RoomSceneProps) {
  if (renderMode === "ai") {
    return (
      <div style={{ aspectRatio: "800/520", background: "#FAF8F5", borderRadius: 16 }}>
        <p style={{ textAlign: "center", paddingTop: "40%", color: "#A8A29E" }}>
          AI scene coming soon
        </p>
      </div>
    );
  }

  const isPlaced = (slotId: string) => (selections[slotId]?.length ?? 0) > 0;
  const countFor = (slotId: string) => selections[slotId]?.length ?? 0;

  return (
    <svg
      viewBox={`0 0 ${SCENE.viewBox.w} ${SCENE.viewBox.h}`}
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Room scene showing selected furniture"
      style={{ width: "100%", height: "auto", borderRadius: 16, overflow: "hidden" }}
    >
      {/* Layer 0: Background */}
      <RoomBackground />

      {/* Layer 1: Rug */}
      {isPlaced("rug") && <Rug />}

      {/* Layer 2: Large furniture */}
      {isPlaced("bed_frame") && <BedFrame />}
      {isPlaced("nightstand") && <Nightstand />}
      {isPlaced("dresser") && <Dresser />}

      {/* Layer 3: On-furniture items */}
      {isPlaced("mattress") && <Mattress />}
      {isPlaced("sheets") && <Sheets />}
      {isPlaced("comforter") && <Comforter />}
      {isPlaced("pillows") && <Pillows />}
      {isPlaced("table_lamp") && <TableLamp />}
      {isPlaced("throw_blanket") && <ThrowBlanket />}

      {/* Layer 4: Freestanding */}
      {isPlaced("floor_lamp") && <FloorLamp />}
      {isPlaced("plants") && <PlantZone count={countFor("plants")} />}
      {isPlaced("mirror") && <Mirror />}

      {/* Layer 5: Wall items */}
      {isPlaced("wall_art") && <GalleryWallZone count={countFor("wall_art")} />}
      {isPlaced("curtains") && <Curtains />}

      {/* Layer 6: Ceiling */}
      {isPlaced("ceiling_light") && <CeilingLight />}

      {/* Highlight zone for the slot currently being picked */}
      {currentSlotId && !isPlaced(currentSlotId) && (
        <SlotHighlight slotId={currentSlotId} />
      )}
    </svg>
  );
}
