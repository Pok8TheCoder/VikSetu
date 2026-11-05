import type { PointerEvent as ReactPointerEvent } from "react";
import {
  BaseBoxShapeUtil,
  HTMLContainer,
  T,
  stopEventPropagation,
  type Editor,
  type TLShape,
  type TLShapeId,
} from "tldraw";

export const CHART_TYPE = "viksetu-chart";
export const DOC_TYPE = "viksetu-doc";
export const SHEET_TYPE = "viksetu-sheet";
export const FILE_TYPE = "viksetu-file";

declare module "@tldraw/tlschema" {
  interface TLGlobalShapePropsMap {
    "viksetu-chart": { w: number; h: number; title: string; chart: string; labels: string; values: string };
    "viksetu-doc": { w: number; h: number; title: string; format: string; body: string };
    "viksetu-sheet": { w: number; h: number; title: string; columns: string; rows: string };
    "viksetu-file": { w: number; h: number; name: string; fileId: string; preview: string };
  }
}

type ChartShape = TLShape<typeof CHART_TYPE>;
type DocShape = TLShape<typeof DOC_TYPE>;
type SheetShape = TLShape<typeof SHEET_TYPE>;
type FileShape = TLShape<typeof FILE_TYPE>;

function startDrag(
  editor: Editor,
  shape: { id: TLShapeId; type: string; x: number; y: number },
  event: ReactPointerEvent<HTMLDivElement>
) {
  if (event.button !== 0) return;
  stopEventPropagation(event);
  event.preventDefault();
  editor.setSelectedShapes([shape.id]);
  const origin = editor.screenToPage({ x: event.clientX, y: event.clientY });
  const start = { x: shape.x, y: shape.y, px: origin.x, py: origin.y };
  const move = (ev: PointerEvent | MouseEvent) => {
    const page = editor.screenToPage({ x: ev.clientX, y: ev.clientY });
    editor.updateShape({
      id: shape.id,
      type: shape.type,
      x: start.x + (page.x - start.px),
      y: start.y + (page.y - start.py),
    } as Parameters<Editor["updateShapes"]>[0][number]);
  };
  const up = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

function parseList(raw: string): string[] {
  try {
    const value = JSON.parse(raw);
    return Array.isArray(value) ? value.map((item) => String(item)) : [];
  } catch {
    return [];
  }
}

function parseNumbers(raw: string): number[] {
  try {
    const value = JSON.parse(raw);
    return Array.isArray(value) ? value.map((item) => Number(item) || 0) : [];
  } catch {
    return [];
  }
}

function parseRows(raw: string): string[][] {
  try {
    const value = JSON.parse(raw);
    if (!Array.isArray(value)) return [];
    return value.map((row) => (Array.isArray(row) ? row.map((cell) => String(cell ?? "")) : []));
  } catch {
    return [];
  }
}

function ChartGraphic({ chart, labels, values }: { chart: string; labels: string[]; values: number[] }) {
  if (!values.length) return <p className="vik-empty">No series yet. Ask the agent to chart data.</p>;
  const max = Math.max(...values, 1);
  if (chart === "pie") {
    let cursor = 0;
    const total = values.reduce((sum, value) => sum + Math.max(value, 0), 0) || 1;
    const colors = ["#38bdf8", "#a78bfa", "#34d399", "#fbbf24", "#fb7185", "#94a3b8"];
    const stops = values
      .map((value, index) => {
        const start = cursor;
        cursor += (Math.max(value, 0) / total) * 100;
        return `${colors[index % colors.length]} ${start}% ${cursor}%`;
      })
      .join(", ");
    return (
      <div className="vik-pie-row">
        <div className="vik-pie" style={{ background: `conic-gradient(${stops})` }} />
        <ul>
          {labels.map((label, index) => (
            <li key={label + index}>
              {label} · {values[index] ?? 0}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (chart === "line") {
    const points = values
      .map((value, index) => {
        const x = values.length === 1 ? 50 : (index / (values.length - 1)) * 100;
        const y = 100 - (value / max) * 100;
        return `${x},${y}`;
      })
      .join(" ");
    return (
      <svg className="vik-chart-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
        <polyline fill="none" stroke="#38bdf8" strokeWidth="2" points={points} />
      </svg>
    );
  }
  return (
    <div className="vik-bars">
      {values.map((value, index) => (
        <div key={labels[index] ?? index} className="vik-bar-col">
          <div className="vik-bar" style={{ height: `${Math.max(4, (value / max) * 100)}%` }} />
          <span>{labels[index] ?? index + 1}</span>
        </div>
      ))}
    </div>
  );
}

function DocBody({ format, body }: { format: string; body: string }) {
  if (!body.trim()) return <p className="vik-empty">Empty note.</p>;
  return (
    <div className="vik-doc-body">
      {body.split("\n").map((line, index) => {
        if (format === "md" && line.startsWith("# ")) return <h3 key={index}>{line.slice(2)}</h3>;
        if (format === "md" && line.startsWith("## ")) return <h4 key={index}>{line.slice(3)}</h4>;
        if (format === "md" && (line.startsWith("- ") || line.startsWith("* "))) return <li key={index}>{line.slice(2)}</li>;
        return <p key={index}>{line || "\u00a0"}</p>;
      })}
    </div>
  );
}

function Frame({
  title,
  hint,
  onDrag,
  children,
}: {
  title: string;
  hint: string;
  onDrag: (event: ReactPointerEvent<HTMLDivElement>) => void;
  children: React.ReactNode;
}) {
  return (
    <div className="vik-embed-frame">
      <div className="vik-map-bar" onPointerDown={onDrag}>
        <span>{title}</span>
        <span className="vik-map-hint">{hint}</span>
      </div>
      <div className="vik-embed-body" onPointerDown={stopEventPropagation}>
        {children}
      </div>
    </div>
  );
}

export class ChartShapeUtil extends BaseBoxShapeUtil<ChartShape> {
  static override type = CHART_TYPE;
  static override props = {
    w: T.number,
    h: T.number,
    title: T.string,
    chart: T.string,
    labels: T.string,
    values: T.string,
  };

  override getDefaultProps(): ChartShape["props"] {
    return { w: 420, h: 280, title: "Chart", chart: "bar", labels: "[]", values: "[]" };
  }

  override getIndicatorPath(shape: ChartShape) {
    const path = new Path2D();
    path.rect(0, 0, shape.props.w, shape.props.h);
    return path;
  }

  override component(shape: ChartShape) {
    const editor = this.editor;
    return (
      <HTMLContainer>
        <Frame title={shape.props.title || "Chart"} hint={shape.props.chart} onDrag={(event) => startDrag(editor, shape, event)}>
          <ChartGraphic chart={shape.props.chart} labels={parseList(shape.props.labels)} values={parseNumbers(shape.props.values)} />
        </Frame>
      </HTMLContainer>
    );
  }
}

export class DocShapeUtil extends BaseBoxShapeUtil<DocShape> {
  static override type = DOC_TYPE;
  static override props = {
    w: T.number,
    h: T.number,
    title: T.string,
    format: T.string,
    body: T.string,
  };

  override getDefaultProps(): DocShape["props"] {
    return { w: 380, h: 320, title: "Note", format: "md", body: "" };
  }

  override getIndicatorPath(shape: DocShape) {
    const path = new Path2D();
    path.rect(0, 0, shape.props.w, shape.props.h);
    return path;
  }

  override component(shape: DocShape) {
    const editor = this.editor;
    return (
      <HTMLContainer>
        <Frame title={shape.props.title || "Note"} hint={shape.props.format === "md" ? "markdown" : "text"} onDrag={(event) => startDrag(editor, shape, event)}>
          <DocBody format={shape.props.format} body={shape.props.body} />
        </Frame>
      </HTMLContainer>
    );
  }
}

export class SheetShapeUtil extends BaseBoxShapeUtil<SheetShape> {
  static override type = SHEET_TYPE;
  static override props = {
    w: T.number,
    h: T.number,
    title: T.string,
    columns: T.string,
    rows: T.string,
  };

  override getDefaultProps(): SheetShape["props"] {
    return { w: 520, h: 280, title: "Sheet", columns: '["A","B"]', rows: '[["",""]]' };
  }

  override getIndicatorPath(shape: SheetShape) {
    const path = new Path2D();
    path.rect(0, 0, shape.props.w, shape.props.h);
    return path;
  }

  override component(shape: SheetShape) {
    const editor = this.editor;
    const columns = parseList(shape.props.columns);
    const rows = parseRows(shape.props.rows);
    const write = (nextColumns: string[], nextRows: string[][]) => {
      editor.updateShape({
        id: shape.id,
        type: SHEET_TYPE,
        props: { ...shape.props, columns: JSON.stringify(nextColumns), rows: JSON.stringify(nextRows) },
      });
    };
    return (
      <HTMLContainer>
        <Frame title={shape.props.title || "Sheet"} hint="sheet" onDrag={(event) => startDrag(editor, shape, event)}>
          <div className="vik-sheet-wrap">
            <table className="vik-sheet">
              <thead>
                <tr>
                  {columns.map((column, index) => (
                    <th key={index}>
                      <input
                        value={column}
                        onChange={(event) => {
                          const next = columns.slice();
                          next[index] = event.target.value;
                          write(next, rows);
                        }}
                      />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    {columns.map((_, columnIndex) => (
                      <td key={columnIndex}>
                        <input
                          value={row[columnIndex] ?? ""}
                          onChange={(event) => {
                            const next = rows.map((cells) => cells.slice());
                            next[rowIndex][columnIndex] = event.target.value;
                            write(columns, next);
                          }}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Frame>
      </HTMLContainer>
    );
  }
}

async function uploadFile(file: File): Promise<{ fileId: string; name: string; preview: string }> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  const chunk = 0x8000;
  for (let index = 0; index < bytes.length; index += chunk) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunk));
  }
  const response = await fetch("/api/canvas/files", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: file.name, data_b64: btoa(binary) }),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function placeDroppedFile(editor: Editor, file: File, point: { x: number; y: number }, shapeId?: TLShapeId) {
  const saved = await uploadFile(file);
  const lower = file.name.toLowerCase();
  if (shapeId) {
    editor.updateShape({
      id: shapeId,
      type: FILE_TYPE,
      props: { name: saved.name, fileId: saved.fileId, preview: saved.preview },
    });
    return;
  }
  if (lower.endsWith(".csv")) {
    const lines = saved.preview.split(/\r?\n/).filter(Boolean);
    const columns = (lines[0] ?? "A,B").split(",");
    const rows = lines.slice(1, 40).map((line) => line.split(","));
    editor.createShape({
      type: SHEET_TYPE,
      x: point.x,
      y: point.y,
      props: {
        w: 560,
        h: 300,
        title: saved.name,
        columns: JSON.stringify(columns),
        rows: JSON.stringify(rows.length ? rows : [columns.map(() => "")]),
      },
    });
    return;
  }
  if (lower.endsWith(".md") || lower.endsWith(".txt")) {
    editor.createShape({
      type: DOC_TYPE,
      x: point.x,
      y: point.y,
      props: {
        w: 420,
        h: 340,
        title: saved.name,
        format: lower.endsWith(".md") ? "md" : "text",
        body: saved.preview,
      },
    });
    return;
  }
  editor.createShape({
    type: FILE_TYPE,
    x: point.x,
    y: point.y,
    props: { w: 300, h: 220, name: saved.name, fileId: saved.fileId, preview: saved.preview },
  });
}

export class FileShapeUtil extends BaseBoxShapeUtil<FileShape> {
  static override type = FILE_TYPE;
  static override props = {
    w: T.number,
    h: T.number,
    name: T.string,
    fileId: T.string,
    preview: T.string,
  };

  override getDefaultProps(): FileShape["props"] {
    return { w: 300, h: 220, name: "", fileId: "", preview: "" };
  }

  override getIndicatorPath(shape: FileShape) {
    const path = new Path2D();
    path.rect(0, 0, shape.props.w, shape.props.h);
    return path;
  }

  override component(shape: FileShape) {
    const editor = this.editor;
    const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
      const file = event.dataTransfer.files?.[0];
      if (!file) return;
      event.preventDefault();
      event.stopPropagation();
      void placeDroppedFile(editor, file, { x: shape.x, y: shape.y }, shape.id);
    };
    return (
      <HTMLContainer>
        <div className="vik-embed-frame vik-file-frame" onDragOver={(event) => event.preventDefault()} onDrop={onDrop}>
          <div className="vik-map-bar" onPointerDown={(event) => startDrag(editor, shape, event)}>
            <span>{shape.props.name || "Drop a file"}</span>
            <span className="vik-map-hint">file</span>
          </div>
          <div className="vik-embed-body" onPointerDown={stopEventPropagation}>
            {shape.props.fileId ? (
              <>
                <p className="vik-file-path">inbox/{shape.props.fileId}</p>
                <pre className="vik-file-preview">{shape.props.preview || "Stored. The agent can read it with Python."}</pre>
              </>
            ) : (
              <p className="vik-empty">Drop a file here, or drop one anywhere on the canvas.</p>
            )}
          </div>
        </div>
      </HTMLContainer>
    );
  }
}
