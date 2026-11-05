export type MapPinBrief = {
  pinId: string;
  name: string;
  category: string;
  lng: number;
  lat: number;
  taluka?: string;
};

export type SelectedPin = {
  pinId: string;
  name: string;
  category: string;
  lng: number;
  lat: number;
  summary?: string;
  description?: string;
};

export type MapContext = {
  layers: Record<string, boolean>;
  pins: MapPinBrief[];
  enabledCount: number;
  selected: SelectedPin | null;
};

let state: MapContext = { layers: {}, pins: [], enabledCount: 0, selected: null };
let listening = false;

export function getMapContext(): MapContext {
  return state;
}

export function watchMapContext() {
  if (listening) return;
  listening = true;
  window.addEventListener("message", (event: MessageEvent) => {
    const data = event.data as {
      source?: string;
      kind?: string;
      layers?: Record<string, boolean>;
      pins?: MapPinBrief[];
      enabledCount?: number;
      pinId?: string;
      name?: string;
      layer?: string;
      lng?: number;
      lat?: number;
      summary?: string;
      description?: string;
    };
    if (!data || data.source !== "viksetu-map") return;
    if (data.kind === "state") {
      const pins = Array.isArray(data.pins) ? data.pins : [];
      state = {
        ...state,
        layers: data.layers ?? {},
        pins,
        enabledCount: data.enabledCount ?? pins.length,
      };
    }
    if (data.kind === "pin") {
      state = {
        ...state,
        selected: {
          pinId: data.pinId ?? "",
          name: data.name ?? "",
          category: data.layer ?? "",
          lng: data.lng ?? 0,
          lat: data.lat ?? 0,
          summary: data.summary ?? "",
          description: data.description ?? "",
        },
      };
    }
  });
}
