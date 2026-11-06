import { useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import type { Editor } from "@tldraw/editor";
import { Tldraw } from "tldraw";
import "tldraw/tldraw.css";
import { AgentPanel } from "./AgentPanel";
import { placeEmbedAt, VikToolbar } from "./EmbedMenu";
import { watchCanvas } from "./changeLog";
import { watchCursor } from "./cursor";
import { LayerDock } from "./LayerDock";
import { CustomShapeUtil } from "./CustomShape";
import { ChartShapeUtil, DocShapeUtil, FILE_TYPE, FileShapeUtil, SheetShapeUtil } from "./embedShapes";
import { dropFilesOnCanvas } from "./fileDrop";
import { watchMapContext } from "./mapContext";
import { MAP_TYPE, MapShapeUtil } from "./MapShape";
import "./agent.css";

function App() {
  const [editor, setEditor] = useState<Editor | null>(null);
  const stageRef = useRef<HTMLDivElement>(null);

  return (
    <div className="canvas-shell">
      <div className="canvas-stage" ref={stageRef}>
        <Tldraw
          persistenceKey="viksetu-canvas"
          shapeUtils={[MapShapeUtil, ChartShapeUtil, DocShapeUtil, SheetShapeUtil, FileShapeUtil, CustomShapeUtil]}
          components={{ StylePanel: null, Toolbar: VikToolbar }}
          onMount={(instance) => {
            instance.user.updateUserPreferences({ colorScheme: "dark" });
            watchCanvas(instance);
            watchMapContext();
            watchCursor(instance);
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
                props: { w: 300, h: 220, name: "", fileId: "", preview: "", uploadPct: 100, kind: "" },
              });
            }
            if (fresh) instance.zoomToFit({ animation: { duration: 280 } });
            const container = instance.getContainer();
            const allowDrop = (event: DragEvent) => {
              const types = event.dataTransfer?.types;
              if (types?.includes("Files") || types?.includes("text/plain")) event.preventDefault();
            };
            const onDrop = (event: DragEvent) => {
              const embed = event.dataTransfer?.getData("text/plain") ?? "";
              if (embed.startsWith("viksetu-embed:")) {
                event.preventDefault();
                event.stopPropagation();
                placeEmbedAt(instance, embed.slice("viksetu-embed:".length), event.clientX, event.clientY);
                return;
              }
              const files = event.dataTransfer?.files;
              if (!files?.length) return;
              const target = event.target as HTMLElement | null;
              if (target?.closest(".vik-file-frame")) return;
              event.preventDefault();
              event.stopPropagation();
              void dropFilesOnCanvas(instance, files, event.clientX, event.clientY);
            };
            container.addEventListener("dragover", allowDrop);
            container.addEventListener("drop", onDrop, true);
            setEditor(instance);
          }}
        />
        <LayerDock editor={editor} stage={stageRef} />
      </div>
      <AgentPanel editor={editor} />
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
