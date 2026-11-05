import { useState } from "react";
import { createRoot } from "react-dom/client";
import type { Editor } from "@tldraw/editor";
import { Tldraw } from "tldraw";
import "tldraw/tldraw.css";
import { AgentPanel } from "./AgentPanel";
import { watchCanvas } from "./changeLog";
import { ChartShapeUtil, DocShapeUtil, FILE_TYPE, FileShapeUtil, placeDroppedFile, SheetShapeUtil } from "./embedShapes";
import { watchMapContext } from "./mapContext";
import { MAP_TYPE, MapShapeUtil } from "./MapShape";
import "./agent.css";

function App() {
  const [editor, setEditor] = useState<Editor | null>(null);

  return (
    <div className="canvas-shell">
      <div className="canvas-stage">
        <Tldraw
          persistenceKey="viksetu-canvas"
          shapeUtils={[MapShapeUtil, ChartShapeUtil, DocShapeUtil, SheetShapeUtil, FileShapeUtil]}
          components={{ StylePanel: null }}
          onMount={(instance) => {
            instance.user.updateUserPreferences({ colorScheme: "dark" });
            watchCanvas(instance);
            watchMapContext();
            const shapes = instance.getCurrentPageShapes();
            const fresh = shapes.length === 0;
            if (!shapes.some((shape) => shape.type === MAP_TYPE)) {
              instance.createShape({
                type: MAP_TYPE,
                x: 48,
                y: 48,
                props: { w: 760, h: 520 },
              });
            }
            if (!shapes.some((shape) => shape.type === FILE_TYPE)) {
              instance.createShape({
                type: FILE_TYPE,
                x: 840,
                y: 48,
                props: { w: 300, h: 220, name: "", fileId: "", preview: "" },
              });
            }
            if (fresh) instance.zoomToFit({ animation: { duration: 280 } });
            const container = instance.getContainer();
            const allowDrop = (event: DragEvent) => {
              if (event.dataTransfer?.types?.includes("Files")) event.preventDefault();
            };
            const onDrop = (event: DragEvent) => {
              const files = event.dataTransfer?.files;
              if (!files?.length) return;
              const target = event.target as HTMLElement | null;
              if (target?.closest(".vik-file-frame")) return;
              event.preventDefault();
              event.stopPropagation();
              const point = instance.screenToPage({ x: event.clientX, y: event.clientY });
              Array.from(files).forEach((file, index) => {
                void placeDroppedFile(instance, file, { x: point.x + index * 36, y: point.y + index * 28 });
              });
            };
            container.addEventListener("dragover", allowDrop);
            container.addEventListener("drop", onDrop, true);
            setEditor(instance);
          }}
        />
      </div>
      <AgentPanel editor={editor} />
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
