import { useEffect, useRef, useState } from "react";
import type { Editor } from "@tldraw/editor";
import {
  applyActions,
  ensureRequested,
  planLocally,
  snapshotCanvas,
  type AgentTurn,
  type CanvasAction,
  type FileToolNote,
  type PythonNote,
} from "./canvasAgent";
import { getChangeLog } from "./changeLog";
import { getCursorPoint } from "./cursor";
import { getMapContext } from "./mapContext";
import { applyMapActions, splitMapActions } from "./mapBridge";

const CHAT_KEY = "viksetu-canvas-chat";
const STORE_KEY = "viksetu-canvas-chats";
const AGENT_WIDTH_KEY = "viksetu-agent-width";
const AGENT_OPEN_KEY = "viksetu-agent-open";
const MAX_STEPS = 6;

// One step is a thinking and action pair. It is shown in the chat but never sent with later prompts.
type StepView = {
  thinking: string;
  note: string;
  actions: { label: string; detail: string }[];
  python: PythonNote[];
  fileTools: FileToolNote[];
  created: string[];
  error: string;
  live?: boolean;
};
type Message = { role: "user" | "agent"; text: string; steps?: StepView[] };
type Thread = { id: string; title: string; messages: Message[] };
type ChatStore = { activeId: string; threads: Thread[] };

const INTRO: Message = {
  role: "agent",
  text: "Drop files (including images) on the canvas or file node — they land in agent_workspace/inbox as objects with fileId and fileKind. I can file-read (text, hex, parse), file-list, or python anywhere under the workspace. Map layers, pins, charts, and selection are visible each turn. Ctrl-click to multi-select.",
};

function visibleText(text: string): string {
  return text.replace(/\n+via [^\n]+$/i, "");
}

function threadTitle(messages: Message[]): string {
  const user = messages.find((message) => message.role === "user");
  const text = user?.text.trim() || "New chat";
  return text.length > 42 ? `${text.slice(0, 42)}…` : text;
}

function freshThread(): Thread {
  return { id: `chat-${Date.now()}`, title: "New chat", messages: [INTRO] };
}

function loadStore(): ChatStore {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    const parsed = raw ? (JSON.parse(raw) as ChatStore) : null;
    if (parsed && Array.isArray(parsed.threads) && parsed.threads.length) {
      const threads = parsed.threads.map((thread) => ({
        ...thread,
        messages: (thread.messages || [INTRO]).slice(-40).map((message) => ({
          ...message,
          text: visibleText(message.text),
        })),
      }));
      const activeId = threads.some((thread) => thread.id === parsed.activeId) ? parsed.activeId : threads[0].id;
      return { activeId, threads };
    }
  } catch {
    // Fall through to the older single-chat save.
  }
  try {
    const raw = localStorage.getItem(CHAT_KEY);
    const parsed = raw ? (JSON.parse(raw) as Message[]) : [];
    if (Array.isArray(parsed) && parsed.length) {
      const thread = freshThread();
      thread.messages = parsed.slice(-40).map((message) => ({ ...message, text: visibleText(message.text) }));
      thread.title = threadTitle(thread.messages);
      return { activeId: thread.id, threads: [thread] };
    }
  } catch {
    // Start a new chat when nothing saved can be read.
  }
  const thread = freshThread();
  return { activeId: thread.id, threads: [thread] };
}

type Props = {
  editor: Editor | null;
};

function asTurn(value: unknown): AgentTurn | null {
  if (!value || typeof value !== "object") return null;
  const turn = value as {
    thinking?: unknown;
    reply?: unknown;
    actions?: unknown;
    source?: unknown;
    continue?: unknown;
    python?: unknown;
    file_tools?: unknown;
  };
  if (typeof turn.reply !== "string" || !Array.isArray(turn.actions)) return null;
  const python = Array.isArray(turn.python)
    ? turn.python.filter((item) => item && typeof item === "object")
    : [];
  const fileTools = Array.isArray(turn.file_tools)
    ? turn.file_tools.filter((item) => item && typeof item === "object")
    : [];
  return {
    reply: visibleText(turn.reply),
    thinking: typeof turn.thinking === "string" ? turn.thinking : "",
    actions: turn.actions.filter((item) => item && typeof item === "object") as CanvasAction[],
    fromModel: turn.source === "llm" || turn.source === "error",
    continue: turn.source === "llm" && Boolean(turn.continue),
    python: python as PythonNote[],
    file_tools: fileTools as FileToolNote[],
  };
}

// Reads the model's reasoning out of text that is still being written, including a half-finished JSON string.
function liveThinking(raw: string): string {
  const tagged = Array.from(raw.matchAll(/<think>([\s\S]*?)(?:<\/think>|$)/gi))
    .map((match) => match[1].trim())
    .filter(Boolean);
  const field = raw.match(/"thinking"\s*:\s*"((?:[^"\\]|\\[\s\S])*)/);
  let written = "";
  if (field) {
    try {
      written = JSON.parse(`"${field[1]}"`) as string;
    } catch {
      written = field[1].replace(/\\n/g, "\n").replace(/\\"/g, '"').replace(/\\\\/g, "\\");
    }
  }
  return [...tagged, written].filter(Boolean).join("\n\n");
}

async function streamTurn(body: unknown, onRaw: (raw: string) => void): Promise<AgentTurn | null> {
  const response = await fetch("/api/canvas/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok || !response.body) return null;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let raw = "";
  let final: AgentTurn | null = null;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut = buffer.indexOf("\n");
    while (cut >= 0) {
      const line = buffer.slice(0, cut).trim();
      buffer = buffer.slice(cut + 1);
      cut = buffer.indexOf("\n");
      if (!line) continue;
      let item: { type?: string; text?: string };
      try {
        item = JSON.parse(line);
      } catch {
        continue;
      }
      if (item.type === "delta") {
        raw += item.text ?? "";
        onRaw(raw);
      } else if (item.type === "final") {
        final = asTurn(item);
      }
    }
  }
  return final;
}

function clipText(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

function describeAction(action: CanvasAction): { label: string; detail: string } {
  const raw = action as unknown as Record<string, unknown>;
  const name = String(raw.title ?? raw.text ?? raw.geo ?? "");
  const target = raw.id ? ` (${String(raw.id)})` : "";
  const label = `${action.op}${name ? ` · ${clipText(name, 40)}` : ""}${target}`;
  const shown = { ...raw };
  if (typeof shown.html === "string") shown.html = clipText(shown.html, 1200);
  if (typeof shown.body === "string") shown.body = clipText(shown.body, 1200);
  return { label, detail: clipText(JSON.stringify(shown, null, 2), 2400) };
}

function StepPair({ step, index }: { step: StepView; index: number }) {
  const hasAction =
    step.actions.length > 0 || step.python.length > 0 || step.fileTools.length > 0 || Boolean(step.error);
  return (
    <div className="agent-step">
      {step.thinking && (
        <details className="agent-fold agent-fold--think" open={step.live}>
          <summary>
            <span className="agent-fold__tag">Thinking</span>
            <span className="agent-fold__meta">{step.live ? "live" : `step ${index + 1}`}</span>
          </summary>
          <pre>{step.thinking}</pre>
        </details>
      )}
      {hasAction && (
        <details className="agent-fold agent-fold--act">
          <summary>
            <span className="agent-fold__tag">Action</span>
            <span className="agent-fold__meta">
              {[...step.actions.map((item) => item.label), ...step.python.map(() => "python"), ...step.fileTools.map((item) => item.mode || "file")].join(", ") || "failed"}
            </span>
          </summary>
          {step.note && <p className="agent-fold__note">{step.note}</p>}
          {step.actions.map((item, position) => (
            <div key={position} className="agent-fold__item">
              <strong>{item.label}</strong>
              <pre>{item.detail}</pre>
            </div>
          ))}
          {step.python.map((note, position) => (
            <div key={`py-${position}`} className="agent-fold__item">
              <strong>python · {note.ok ? "ok" : `failed (${note.code ?? "?"})`}</strong>
              {note.script && <pre>{clipText(note.script, 1800)}</pre>}
              {(note.stdout || note.stderr) && <pre>{clipText(`${note.stdout || ""}${note.stderr || ""}`, 1800)}</pre>}
            </div>
          ))}
          {step.fileTools.map((note, position) => (
            <div key={`file-${position}`} className="agent-fold__item">
              <strong>
                file · {note.mode || "read"} · {note.ok ? "ok" : "failed"}
              </strong>
              <pre>
                {clipText(
                  note.error ||
                    note.text ||
                    note.dump ||
                    note.preview ||
                    JSON.stringify({ path: note.path, op: note.op }),
                  1800
                )}
              </pre>
            </div>
          ))}
          {step.created.length > 0 && <p className="agent-fold__note">created {step.created.join(", ")}</p>}
          {step.error && <p className="agent-fold__note agent-fold__note--error">{step.error}</p>}
        </details>
      )}
    </div>
  );
}

export function AgentPanel({ editor }: Props) {
  const [store, setStore] = useState<ChatStore>(loadStore);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("Thinking…");
  const [live, setLive] = useState<StepView | null>(null);
  const [open, setOpen] = useState(() => localStorage.getItem(AGENT_OPEN_KEY) !== "0");
  const [width, setWidth] = useState(() => {
    const saved = Number(localStorage.getItem(AGENT_WIDTH_KEY));
    return Number.isFinite(saved) ? Math.min(560, Math.max(260, saved)) : 340;
  });
  const resizeRef = useRef<{ startX: number; startW: number } | null>(null);
  const [managing, setManaging] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const active = store.threads.find((thread) => thread.id === store.activeId) ?? store.threads[0];
  const messages = active?.messages ?? [INTRO];

  const writeThread = (id: string, nextMessages: Message[]) => {
    setStore((current) => ({
      ...current,
      threads: current.threads.map((thread) =>
        thread.id === id
          ? { ...thread, messages: nextMessages.slice(-40), title: threadTitle(nextMessages) }
          : thread
      ),
    }));
  };

  useEffect(() => {
    localStorage.setItem(STORE_KEY, JSON.stringify(store));
  }, [store]);

  useEffect(() => {
    localStorage.setItem(AGENT_OPEN_KEY, open ? "1" : "0");
  }, [open]);

  useEffect(() => {
    localStorage.setItem(AGENT_WIDTH_KEY, String(width));
  }, [width]);

  useEffect(() => {
    const move = (event: PointerEvent) => {
      if (!resizeRef.current) return;
      const delta = resizeRef.current.startX - event.clientX;
      setWidth(Math.min(560, Math.max(260, resizeRef.current.startW + delta)));
    };
    const up = () => {
      resizeRef.current = null;
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [store, busy, live]);

  const newChat = () => {
    const thread = freshThread();
    setStore((current) => ({ activeId: thread.id, threads: [thread, ...current.threads].slice(0, 30) }));
    setManaging(false);
    setDraft("");
  };

  const openChat = (id: string) => {
    setStore((current) => ({ ...current, activeId: id }));
    setManaging(false);
  };

  const deleteChat = (id: string) => {
    setStore((current) => {
      const threads = current.threads.filter((thread) => thread.id !== id);
      if (!threads.length) {
        const thread = freshThread();
        return { activeId: thread.id, threads: [thread] };
      }
      return { activeId: current.activeId === id ? threads[0].id : current.activeId, threads };
    });
  };

  const send = async () => {
    const text = draft.trim();
    if (!text || busy || !active) return;
    const threadId = active.id;
    setDraft("");
    const base: Message[] = [...messages, { role: "user" as const, text }];
    writeThread(threadId, base);
    setBusy(true);
    // Earlier prompts reach the model as the user text and the final reply only.
    const history = base
      .filter((item) => item.text.trim() && item.text !== INTRO.text)
      .slice(-12)
      .map((item) => ({ role: item.role, text: item.text }));
    const steps: StepView[] = [];
    const trace: Record<string, unknown>[] = [];
    const applied: CanvasAction[] = [];
    let lastReply = "";
    let notice = "";
    let placed = 0;
    let stalled = false;
    let wantsMore = false;
    const show = (finalText: string) => writeThread(threadId, [...base, { role: "agent", text: finalText, steps: steps.slice() }]);
    try {
      for (let step = 0; step < MAX_STEPS; step += 1) {
        setProgress(step === 0 ? "Thinking…" : `Step ${step + 1}…`);
        const canvas = editor ? snapshotCanvas(editor) : [];
        let turn = planLocally(text, canvas);
        try {
          const body = {
            message: text,
            history,
            canvas,
            selection: canvas.filter((shape) => shape.selected),
            log: getChangeLog().slice(-40),
            map: getMapContext(),
            cursor: editor ? getCursorPoint(editor) : null,
            step,
            trace,
          };
          let lastPaint = 0;
          const onRaw = (raw: string) => {
            const now = Date.now();
            if (now - lastPaint < 60) return;
            lastPaint = now;
            const thought = liveThinking(raw);
            setLive({ thinking: thought, note: "", actions: [], python: [], fileTools: [], created: [], error: "", live: true });
            setProgress(/"actions"\s*:/.test(raw) ? "Writing actions…" : "Thinking…");
          };
          let parsed: AgentTurn | null = null;
          try {
            parsed = await streamTurn(body, onRaw);
          } catch {
            parsed = null;
          }
          if (!parsed) {
            const response = await fetch("/api/canvas/chat", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(body),
            });
            parsed = response.ok ? asTurn(await response.json()) : null;
          }
          setLive(null);
          if (parsed?.fromModel) {
            turn = parsed;
          } else if (step > 0) {
            notice = "The model stopped answering, so I stopped here.";
            break;
          }
        } catch {
          if (step > 0) {
            notice = "The model stopped answering, so I stopped here.";
            break;
          }
          turn = { ...turn, reply: `${turn.reply}\n\nOffline rules. The model API was not reachable.` };
        }
        let error = "";
        let createdNow: string[] = [];
        if (turn.actions.length) {
          const { map, canvas: canvasOps } = splitMapActions(turn.actions);
          if (map.length) {
            const mapResult = await applyMapActions(map);
            if (mapResult.errors.length) {
              error = [error, ...mapResult.errors].filter(Boolean).join("; ");
            }
          }
          if (editor && canvasOps.length) {
            try {
              const result = applyActions(editor, canvasOps, canvas, placed);
              placed = result.placed;
              createdNow = result.created;
            } catch (failure) {
              error = `Canvas update failed: ${String(failure)}`;
            }
          }
          applied.push(...turn.actions);
        }
        const python = (turn.python ?? []).map((note) => ({
          ...note,
          script: clipText(note.script ?? "", 1800),
          stdout: clipText(note.stdout ?? "", 1800),
          stderr: clipText(note.stderr ?? "", 800),
        }));
        const fileTools = (turn.file_tools ?? []).map((note) => ({
          ...note,
          text: note.text ? clipText(note.text, 1800) : undefined,
          dump: note.dump ? clipText(note.dump, 1200) : undefined,
          preview: note.preview ? clipText(note.preview, 1200) : undefined,
        }));
        steps.push({
          thinking: clipText(turn.thinking ?? "", 6000),
          note: turn.reply,
          actions: turn.actions.map(describeAction),
          python,
          fileTools,
          created: createdNow,
          error,
        });
        trace.push({
          thinking: turn.thinking ?? "",
          reply: turn.reply,
          actions: turn.actions,
          python: turn.python ?? [],
          file_tools: turn.file_tools ?? [],
          created: createdNow,
          error,
        });
        lastReply = turn.reply;
        show("");
        wantsMore = Boolean(turn.continue && turn.fromModel);
        if (!wantsMore) break;
        const produced = turn.actions.length > 0 || python.length > 0 || fileTools.length > 0;
        if (!produced) {
          if (stalled) break;
          stalled = true;
        } else {
          stalled = false;
        }
      }
      if (wantsMore && steps.length >= MAX_STEPS) notice = `Stopped after ${MAX_STEPS} steps.`;
      if (editor) {
        const extra = ensureRequested(text, applied).filter((action) => !applied.some((done) => done.op === action.op));
        if (extra.length) {
          const result = applyActions(editor, extra, snapshotCanvas(editor), placed);
          steps.push({
            thinking: "",
            note: "You asked for this object and the model did not place it, so I added it.",
            actions: extra.map(describeAction),
            python: [],
            fileTools: [],
            created: result.created,
            error: "",
          });
        }
      }
      const total = steps.reduce(
        (sum, item) => sum + item.actions.length + item.python.length + item.fileTools.length,
        0
      );
      const finalText =
        [lastReply.trim() || (total ? `Done. ${total} action${total === 1 ? "" : "s"} applied.` : "I have nothing to add."), notice]
          .filter(Boolean)
          .join("\n\n");
      show(finalText);
    } catch (failure) {
      show(`${lastReply ? `${lastReply}\n\n` : ""}Something went wrong: ${String(failure)}`);
    } finally {
      setLive(null);
      setBusy(false);
      setProgress("Thinking…");
    }
  };

  return (
    <>
      {!open && (
        <button type="button" className="agent-open-tab" onClick={() => setOpen(true)} aria-label="Open agent chat">
          Agent
        </button>
      )}
      <aside className={`agent-panel${open ? "" : " is-hidden"}`} style={{ width: open ? width : 0 }}>
        <div
          className="agent-panel__resize"
          title="Drag to resize"
          onPointerDown={(event) => {
            if (event.button !== 0) return;
            resizeRef.current = { startX: event.clientX, startW: width };
          }}
        />
        <header className="agent-head">
          <div className="agent-head-row">
            <h1>Agent</h1>
            <div className="agent-head-actions">
              <button type="button" onClick={newChat}>
                New
              </button>
              <button type="button" aria-pressed={managing} onClick={() => setManaging((value) => !value)}>
                Chats
              </button>
              <button type="button" onClick={() => setOpen(false)}>
                Hide
              </button>
            </div>
          </div>
          <p>Each step shows what it thought and what it did. Open any one on its own.</p>
        </header>
      {managing && (
        <ul className="agent-chats">
          {store.threads.map((thread) => (
            <li key={thread.id} className={thread.id === store.activeId ? "is-active" : ""}>
              <button type="button" onClick={() => openChat(thread.id)}>
                {thread.title}
              </button>
              <button type="button" aria-label={`Delete ${thread.title}`} onClick={() => deleteChat(thread.id)}>
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="agent-log" ref={logRef}>
        {messages.map((message, index) => (
          <div key={index} className="agent-turn">
            {message.steps?.map((step, position) => (
              <StepPair key={position} step={step} index={position} />
            ))}
            {message.text.trim() && (
              <p className={`agent-msg agent-msg--${message.role}`}>{visibleText(message.text)}</p>
            )}
          </div>
        ))}
        {busy && live && live.thinking && (
          <div className="agent-turn">
            <StepPair step={live} index={0} />
          </div>
        )}
        {busy && <p className="agent-msg agent-msg--agent agent-msg--pending">{progress}</p>}
      </div>
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
    </>
  );
}
