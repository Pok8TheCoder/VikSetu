import type { PointerEvent as ReactPointerEvent } from "react";
import { BaseBoxShapeUtil, HTMLContainer, T, stopEventPropagation, type TLShape } from "tldraw";

export const MAP_TYPE = "viksetu-map";
export const MAP_URL = "http://127.0.0.1:5173/?embed=1";

declare module "@tldraw/tlschema" {
  interface TLGlobalShapePropsMap {
    "viksetu-map": { w: number; h: number };
  }
}

export type VikMapShape = TLShape<"viksetu-map">;

export class MapShapeUtil extends BaseBoxShapeUtil<VikMapShape> {
  static override type = MAP_TYPE;
  static override props = {
    w: T.number,
    h: T.number,
  };

  override getDefaultProps(): VikMapShape["props"] {
    return { w: 760, h: 520 };
  }

  override canEdit() {
    return true;
  }

  override getIndicatorPath(shape: VikMapShape) {
    const path = new Path2D();
    path.rect(0, 0, shape.props.w, shape.props.h);
    return path;
  }

  override component(shape: VikMapShape) {
    const editor = this.editor;
    const onBarPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
      if (event.button !== 0) return;
      stopEventPropagation(event);
      event.preventDefault();
      const bar = event.currentTarget;
      try {
        bar.setPointerCapture(event.pointerId);
      } catch {
        // Synthetic or already-captured pointers still drag via the window listeners.
      }
      editor.setSelectedShapes([shape.id]);
      const origin = editor.screenToPage({ x: event.clientX, y: event.clientY });
      const start = { x: shape.x, y: shape.y, px: origin.x, py: origin.y };
      const move = (ev: PointerEvent | MouseEvent) => {
        const page = editor.screenToPage({ x: ev.clientX, y: ev.clientY });
        editor.updateShape({
          id: shape.id,
          type: MAP_TYPE,
          x: start.x + (page.x - start.px),
          y: start.y + (page.y - start.py),
        });
      };
      const up = () => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", up);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", up);
    };

    return (
      <HTMLContainer id={shape.id} className="vik-map-shape">
        <div className="vik-map-frame is-live">
          <div
            className="vik-map-bar"
            tabIndex={0}
            aria-label="Drag Palghar map"
            draggable={false}
            onPointerDown={onBarPointerDown}
          >
            <span>Palghar map</span>
            <span className="vik-map-hint">drag this bar to move</span>
          </div>
          <div className="vik-map-stage" onPointerDown={stopEventPropagation}>
            <iframe title="Palghar district map" src={MAP_URL} draggable={false} />
          </div>
        </div>
      </HTMLContainer>
    );
  }
}
