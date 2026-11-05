import { useEffect, useRef, useState } from "react";
import type { Editor, TLShapeId } from "@tldraw/editor";
import {
  applyActions,
  planLocally,
  snapshotCanvas,
  type AgentTurn,
  type CanvasAction,
} from "./canvasAgent";
import { getChangeLog, useChangeLog, type ChangeEntry } from "./changeLog";
import { getMapContext } from "./mapContext";

const CHAT_KEY = "viksetu-canvas-chat";

type Message = { role: "user" | "agent"; text: string };

const INTRO: Message = {
  role: "agent",
  text: "The page is saved in this browser. I can see every object's position and size, which map layers are on, the enabled pins, notes, sheets, charts, and files you drop. Drop a file on the file node or on the canvas.",
};

function loadMessages(): Message[] {
  try {
    const raw = localStorage.getItem(CHAT_KEY);
    const parsed = raw ? (JSON.parse(raw) as Message[]) : [];
    if (Array.isArray(parsed) && parsed.length) return parsed.slice(-30);
  } catch {
    // Keep the intro if the saved chat is unreadable.
  }
  return [INTRO];
}

type Props = {
  editor: Editor | null;
};

function asTurn(value: unknown): AgentTurn | null {
  if (!value || typeof value !== "object") return null;
  const turn = value as {
    reply?: unknown;
    actions?: unknown;
    source?: unknown;
    provider?: unknown;
    model?: unknown;
  };
  if (typeof turn.reply !== "string" || !Array.isArray(turn.actions)) return null;
  const via =
    turn.source === "llm"
      ? `via ${String(turn.model || turn.provider || "model")}`
      : turn.source === "error"
        ? "model error"
        : "";
  return {
    reply: via ? `${turn.reply}\n\n${via}` : turn.reply,
    actions: turn.actions as CanvasAction[],
    fromModel: turn.source === "llm" || turn.source === "error",
  };
}

function focusEntry(editor: Editor | null, entry: ChangeEntry) {
  if (!editor || !entry.shapeId) return;
  const shape = editor.getShape(entry.shapeId as TLShapeId);
  if (!shape) return;
  editor.select(shape.id);
  editor.zoomToSelection({ animation: { duration: 220 } });
}

export function AgentPanel({ editor }: Props) {
  const changes = useChangeLog();
  const [messages, setMessages] = useState<Message[]>(loadMessages);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
    localStorage.setItem(CHAT_KEY, JSON.stringify(messages.slice(-30)));
  }, [messages, busy]);

  const send = async () => {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    const history = [...messages, { role: "user" as const, text }];
    setMessages(history);
    setBusy(true);
    const canvas = editor ? snapshotCanvas(editor) : [];
    const log = getChangeLog().slice(-40);
    let turn = planLocally(text, canvas);
    try {
      const response = await fetch("/api/canvas/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          history: history.slice(-12).map((item) => ({ role: item.role, text: item.text })),
          canvas,
          log,
          map: getMapContext(),
        }),
      });
      if (response.ok) {
        const parsed = asTurn(await response.json());
        if (parsed?.fromModel) turn = parsed;
      }
    } catch {
      turn = {
        ...turn,
        reply: `${turn.reply}\n\nOffline rules. The model API was not reachable.`,
      };
    }
    if (editor) {
      try {
        applyActions(editor, turn.actions, canvas);
      } catch (error) {
        turn = { ...turn, reply: `${turn.reply} (canvas update failed: ${String(error)})` };
      }
    }
    setMessages((current) => [...current, { role: "agent", text: turn.reply }]);
    setBusy(false);
  };

  return (
    <aside className="agent-panel">
      <header className="agent-head">
        <h1>Agent</h1>
        <p>Objects, sizes, pins, files, and this chat stay available after a refresh.</p>
      </header>
      <div className="agent-log" ref={logRef}>
        {messages.map((message, index) => (
          <p key={index} className={`agent-msg agent-msg--${message.role}`}>
            {message.text}
          </p>
        ))}
        {busy && <p className="agent-msg agent-msg--agent agent-msg--pending">Thinking…</p>}
      </div>
      <section className="change-log" aria-label="Change log">
        <header>
          <h2>Change log</h2>
          <p>Object, page position, and map coordinates. Click a row to focus it.</p>
        </header>
        <div className="change-log-list">
          {changes.length === 0 && <p className="change-log-empty">Moves, new shapes, and pin clicks show up here.</p>}
          {[...changes].reverse().map((entry) => (
            <button
              key={entry.id}
              type="button"
              className="change-row"
              onClick={() => focusEntry(editor, entry)}
            >
              <span className="change-kind">{entry.kind}</span>
              <span className="change-body">
                <strong>{entry.object}</strong>
                <span>
                  page ({entry.x}, {entry.y})
                  {entry.lng != null && entry.lat != null
                    ? ` · ${entry.lng.toFixed(5)}, ${entry.lat.toFixed(5)}`
                    : ""}
                  {entry.w ? ` · ${entry.w}×${entry.h}` : ""}
                </span>
                <span className="change-id">{entry.shapeId || "map"}</span>
              </span>
              <time>{entry.at}</time>
            </button>
          ))}
        </div>
      </section>
      <form
        className="agent-form"
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Add a pipeline, connect PDF to map…"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !draft.trim()}>
          Send
        </button>
      </form>
    </aside>
  );
}
