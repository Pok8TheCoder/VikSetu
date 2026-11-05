import { createShapeId, toRichText, type TLShapeId } from "@tldraw/tlschema";
import type { Editor } from "@tldraw/editor";
import { CHART_TYPE, DOC_TYPE, FILE_TYPE, SHEET_TYPE } from "./embedShapes";
import { MAP_TYPE } from "./MapShape";

export type CanvasShape = {
  id: string;
  type: string;
  x: number;
  y: number;
  w: number;
  h: number;
  text: string;
  detail: string;
};

export type CanvasAction =
  | {
      op: "geo";
      text: string;
      geo?: string;
      x?: number;
      y?: number;
      w?: number;
      h?: number;
      color?: string;
    }
  | { op: "text"; text: string; x?: number; y?: number; color?: string }
  | { op: "arrow"; from: string; to: string }
  | { op: "map"; x?: number; y?: number; w?: number; h?: number }
  | {
      op: "chart";
      id?: string;
      title?: string;
      chart?: string;
      labels?: string[];
      values?: number[];
      x?: number;
      y?: number;
      w?: number;
      h?: number;
    }
  | {
      op: "doc";
      id?: string;
      title?: string;
      format?: string;
      body?: string;
      x?: number;
      y?: number;
      w?: number;
      h?: number;
    }
  | {
      op: "sheet";
      id?: string;
      title?: string;
      columns?: string[];
      rows?: (string | number)[][];
      x?: number;
      y?: number;
      w?: number;
      h?: number;
    }
  | { op: "file"; x?: number; y?: number; w?: number; h?: number }
  | { op: "delete"; ids: string[] }
  | { op: "zoom" };

export type AgentTurn = {
  reply: string;
  actions: CanvasAction[];
  fromModel?: boolean;
};

const GEOS = new Set(["rectangle", "ellipse", "diamond", "triangle", "hexagon"]);
const COLORS = new Set([
  "black",
  "grey",
  "violet",
  "blue",
  "light-blue",
  "yellow",
  "orange",
  "green",
  "red",
]);

function plainText(shape: { props?: Record<string, unknown> }): string {
  const rich = shape.props?.richText as { content?: { content?: { text?: string }[] }[] } | undefined;
  if (!rich?.content) return "";
  const parts: string[] = [];
  for (const block of rich.content) {
    for (const node of block.content ?? []) {
      if (node.text) parts.push(node.text);
    }
  }
  return parts.join(" ").trim();
}

function clip(value: string, max = 700): string {
  const text = value.replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

function shapeText(shape: { type: string; props: Record<string, unknown> }): string {
  if (shape.type === MAP_TYPE) return "Palghar map";
  if (shape.type === CHART_TYPE) return String(shape.props.title || "Chart");
  if (shape.type === DOC_TYPE) return String(shape.props.title || "Note");
  if (shape.type === SHEET_TYPE) return String(shape.props.title || "Sheet");
  if (shape.type === FILE_TYPE) return String(shape.props.name || "File drop");
  return plainText(shape);
}

function shapeDetail(shape: { type: string; props: Record<string, unknown> }): string {
  const props = shape.props;
  if (shape.type === CHART_TYPE) return clip(`${props.chart} labels ${props.labels} values ${props.values}`);
  if (shape.type === DOC_TYPE) return clip(String(props.body || ""));
  if (shape.type === SHEET_TYPE) return clip(`columns ${props.columns} rows ${props.rows}`, 900);
  if (shape.type === FILE_TYPE) return clip(`file ${props.fileId} ${props.preview}`);
  if (shape.type === MAP_TYPE) return "Live Palghar map";
  return "";
}

export function snapshotCanvas(editor: Editor): CanvasShape[] {
  return editor.getCurrentPageShapes().map((shape) => {
    const props = shape.props as Record<string, unknown>;
    const bounds = editor.getShapePageBounds(shape);
    const record = { type: shape.type, props };
    return {
      id: shape.id,
      type: shape.type,
      x: Math.round(bounds?.x ?? shape.x),
      y: Math.round(bounds?.y ?? shape.y),
      w: Math.round(bounds?.w ?? Number(props.w ?? 0)),
      h: Math.round(bounds?.h ?? Number(props.h ?? 0)),
      text: shapeText(record),
      detail: shapeDetail(record),
    };
  });
}

function resolveId(ref: string, created: TLShapeId[], existing: CanvasShape[]): TLShapeId | null {
  if (ref.startsWith("new:")) {
    const index = Number(ref.slice(4));
    return created[index] ?? null;
  }
  const byId = existing.find((shape) => shape.id === ref);
  if (byId) return byId.id as TLShapeId;
  const needle = ref.toLowerCase();
  const byText = existing.find((shape) => shape.text.toLowerCase() === needle);
  return (byText?.id as TLShapeId) ?? null;
}

export function applyActions(editor: Editor, actions: CanvasAction[], existing: CanvasShape[]) {
  const created: TLShapeId[] = [];
  editor.run(() => {
    for (const action of actions) {
      if (action.op === "geo") {
        const id = createShapeId();
        const geo = (GEOS.has(action.geo ?? "") ? action.geo : "rectangle") as
          | "rectangle"
          | "ellipse"
          | "diamond"
          | "triangle"
          | "hexagon";
        const color = (COLORS.has(action.color ?? "") ? action.color : "blue") as
          | "black"
          | "grey"
          | "violet"
          | "blue"
          | "light-blue"
          | "yellow"
          | "orange"
          | "green"
          | "red";
        editor.createShape({
          id,
          type: "geo",
          x: action.x ?? 80 + created.length * 40,
          y: action.y ?? 80 + created.length * 28,
          props: {
            geo,
            w: action.w ?? 200,
            h: action.h ?? 96,
            color,
            fill: "solid",
            richText: toRichText(action.text || "Untitled"),
          },
        });
        created.push(id);
      } else if (action.op === "text") {
        const id = createShapeId();
        const color = (COLORS.has(action.color ?? "") ? action.color : "black") as
          | "black"
          | "grey"
          | "violet"
          | "blue"
          | "light-blue"
          | "yellow"
          | "orange"
          | "green"
          | "red";
        editor.createShape({
          id,
          type: "text",
          x: action.x ?? 120,
          y: action.y ?? 120,
          props: {
            color,
            richText: toRichText(action.text || ""),
          },
        });
        created.push(id);
      } else if (action.op === "map") {
        const id = createShapeId();
        editor.createShape({
          id,
          type: MAP_TYPE,
          x: action.x ?? 80,
          y: action.y ?? 72,
          props: {
            w: action.w ?? 760,
            h: action.h ?? 520,
          },
        });
        created.push(id);
      } else if (action.op === "chart") {
        const props = {
          w: action.w ?? 420,
          h: action.h ?? 280,
          title: action.title || "Chart",
          chart: action.chart === "line" || action.chart === "pie" ? action.chart : "bar",
          labels: JSON.stringify(action.labels ?? []),
          values: JSON.stringify((action.values ?? []).map((value) => Number(value) || 0)),
        };
        const existingId = action.id ? resolveId(action.id, created, existing) : null;
        if (existingId) {
          editor.updateShape({ id: existingId, type: CHART_TYPE, props });
        } else {
          const id = createShapeId();
          editor.createShape({ id, type: CHART_TYPE, x: action.x ?? 80, y: action.y ?? 80, props });
          created.push(id);
        }
      } else if (action.op === "doc") {
        const props = {
          w: action.w ?? 400,
          h: action.h ?? 320,
          title: action.title || "Note",
          format: action.format === "text" ? "text" : "md",
          body: action.body || "",
        };
        const existingId = action.id ? resolveId(action.id, created, existing) : null;
        if (existingId) {
          editor.updateShape({ id: existingId, type: DOC_TYPE, props });
        } else {
          const id = createShapeId();
          editor.createShape({ id, type: DOC_TYPE, x: action.x ?? 80, y: action.y ?? 80, props });
          created.push(id);
        }
      } else if (action.op === "sheet") {
        const columns = (action.columns?.length ? action.columns : ["A", "B"]).map(String);
        const rows = (action.rows?.length ? action.rows : [columns.map(() => "")]).map((row) =>
          columns.map((_, index) => String(row?.[index] ?? ""))
        );
        const props = {
          w: action.w ?? 520,
          h: action.h ?? 280,
          title: action.title || "Sheet",
          columns: JSON.stringify(columns),
          rows: JSON.stringify(rows),
        };
        const existingId = action.id ? resolveId(action.id, created, existing) : null;
        if (existingId) {
          editor.updateShape({ id: existingId, type: SHEET_TYPE, props });
        } else {
          const id = createShapeId();
          editor.createShape({ id, type: SHEET_TYPE, x: action.x ?? 80, y: action.y ?? 80, props });
          created.push(id);
        }
      } else if (action.op === "file") {
        const id = createShapeId();
        editor.createShape({
          id,
          type: FILE_TYPE,
          x: action.x ?? 80,
          y: action.y ?? 80,
          props: { w: action.w ?? 300, h: action.h ?? 220, name: "", fileId: "", preview: "" },
        });
        created.push(id);
      } else if (action.op === "arrow") {
        const from = resolveId(action.from, created, existing);
        const to = resolveId(action.to, created, existing);
        if (!from || !to) continue;
        const id = createShapeId();
        editor.createShape({ id, type: "arrow" });
        const binding = (terminal: "start" | "end", toId: TLShapeId) => ({
          type: "arrow" as const,
          fromId: id,
          toId,
          props: {
            terminal,
            normalizedAnchor: { x: 0.5, y: 0.5 },
            isExact: false,
            isPrecise: false,
            snap: "none" as const,
          },
        });
        editor.createBindings([binding("start", from), binding("end", to)]);
      } else if (action.op === "delete") {
        const ids = action.ids
          .map((ref) => resolveId(ref, created, existing))
          .filter((id): id is TLShapeId => Boolean(id));
        if (ids.length) editor.deleteShapes(ids);
      } else if (action.op === "zoom") {
        editor.zoomToFit({ animation: { duration: 280 } });
      }
    }
  });
}

export function planLocally(message: string, canvas: CanvasShape[]): AgentTurn {
  const text = message.trim();
  const lower = text.toLowerCase();

  if (/clear|wipe|reset canvas/.test(lower)) {
    const wipeMap = /reset canvas|clear map|wipe/.test(lower);
    return {
      reply: wipeMap ? "Cleared the page, including the map." : "Cleared the other shapes. The Palghar map stayed.",
      actions: [
        {
          op: "delete",
          ids: canvas.filter((shape) => wipeMap || shape.type !== MAP_TYPE).map((shape) => shape.id),
        },
        { op: "zoom" },
      ],
    };
  }

  if (/\bmap\b|embed/.test(lower) && !/connect/.test(lower)) {
    const existing = canvas.find((shape) => shape.type === MAP_TYPE);
    if (existing) {
      return {
        reply: `The Palghar map is already on the canvas at (${existing.x}, ${existing.y}). Drag its title bar to move it. The map itself stays interactive.`,
        actions: [{ op: "zoom" }],
      };
    }
    return {
      reply: "Placed the live Palghar map. Drag the title bar to move it. The map itself pans, zooms, and opens pins.",
      actions: [{ op: "map", x: 80, y: 72, w: 760, h: 520 }, { op: "zoom" }],
    };
  }

  if (/pipeline|pdf|extract|workflow/.test(lower)) {
    const existing = canvas.find((shape) => shape.type === MAP_TYPE);
    return {
      reply: "Laid out a small VikSetu pipeline: source file, extract, then the live map.",
      actions: [
        { op: "geo", text: "PS PDF 2024-25", geo: "rectangle", x: 48, y: 80, color: "blue" },
        { op: "geo", text: "Extract spend", geo: "diamond", x: 48, y: 280, color: "violet" },
        ...(existing
          ? []
          : [{ op: "map" as const, x: 360, y: 48, w: 720, h: 480 }]),
        { op: "arrow", from: "new:0", to: "new:1" },
        { op: "arrow", from: "new:1", to: existing ? existing.id : "new:2" },
        { op: "zoom" },
      ],
    };
  }

  const connect = lower.match(/connect\s+(.+?)\s+to\s+(.+)/);
  if (connect) {
    return {
      reply: `Connecting “${connect[1].trim()}” to “${connect[2].trim()}”.`,
      actions: [
        { op: "arrow", from: connect[1].trim(), to: connect[2].trim() },
        { op: "zoom" },
      ],
    };
  }

  if (/chart|graph/.test(lower)) {
    return {
      reply: "Added a chart object. With the model connected it can fill the series from spend, pins, or a dropped file.",
      actions: [{ op: "chart", title: "Chart", chart: "bar", labels: [], values: [], x: 880, y: 360, w: 420, h: 280 }],
    };
  }

  if (/spreadsheet|sheet|\btable\b/.test(lower)) {
    return {
      reply: "Added a sheet. The agent can read and replace its cells.",
      actions: [{ op: "sheet", title: "Sheet", columns: ["Item", "Value"], rows: [["", ""]], x: 880, y: 360 }],
    };
  }

  if (/markdown|\.md\b|\bnote\b|document/.test(lower)) {
    return {
      reply: "Added a note on the canvas.",
      actions: [{ op: "doc", title: "Note", format: "md", body: "", x: 880, y: 360 }],
    };
  }

  if (/drop file|file node|file drop/.test(lower)) {
    return {
      reply: "Added a file drop. Put a file on it and I can read it from the workspace.",
      actions: [{ op: "file", x: 880, y: 360 }],
    };
  }

  if (/zoom|fit/.test(lower)) {
    return { reply: "Framed everything on the page.", actions: [{ op: "zoom" }] };
  }

  const label = text.replace(/^(add|create|draw|put)\s+/i, "").trim() || "Note";
  const offset = canvas.length * 36;
  return {
    reply: `Added “${label}” on the canvas.`,
    actions: [
      {
        op: "geo",
        text: label,
        geo: "rectangle",
        x: 120 + offset,
        y: 140 + (offset % 180),
        color: "light-blue",
      },
      { op: "zoom" },
    ],
  };
}
