"""Generate VikSetu 5-page PDF with full pages, tables, and diagrams."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from fpdf import FPDF
from fpdf.enums import XPos, YPos

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "VIKSETU_Project_Document_5Pages.pdf"
DIAG = ROOT / "docs" / "viksetu_diagrams"

MARGIN = 18
BODY = 9
LINE = 4.5

SECTOR_DATA = [
    ("General admin", 340000, 339638),
    ("Works / roads", 750000, 749986),
    ("Water supply", 340000, 340000),
    ("Social welfare", 440000, 400680),
    ("Education", 0, 0),
    ("Public health", 0, 0),
    ("Total", 2200000, 1939204),
]


class Doc(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(110, 110, 110)
        self.cell(0, 8, f"VikSetu Project Document  |  Page {self.page_no()} of 5", align="C")


def reset_x(pdf: Doc) -> None:
    pdf.set_x(pdf.l_margin)


def heading(pdf: Doc, text: str, size: float = 11) -> None:
    pdf.set_font("Helvetica", "B", size)
    pdf.set_text_color(18, 55, 90)
    reset_x(pdf)
    pdf.multi_cell(pdf.epw, 5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(0.5)


def para(pdf: Doc, text: str) -> None:
    pdf.set_font("Helvetica", "", BODY)
    reset_x(pdf)
    pdf.multi_cell(pdf.epw, LINE, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)


def bullets(pdf: Doc, items: list[str]) -> None:
    pdf.set_font("Helvetica", "", BODY)
    for item in items:
        reset_x(pdf)
        pdf.set_x(pdf.l_margin + 3)
        pdf.multi_cell(
            pdf.epw - 3,
            LINE,
            f"- {item}",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
    pdf.ln(0.5)


def figure(pdf: Doc, path: Path, title: str | None = None, height_mm: float | None = None) -> None:
    if title:
        pdf.set_font("Helvetica", "I", 8.5)
        reset_x(pdf)
        pdf.multi_cell(pdf.epw, 4, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    w = pdf.epw
    if height_mm:
        pdf.image(str(path), x=pdf.l_margin, w=w, h=height_mm)
    else:
        pdf.image(str(path), x=pdf.l_margin, w=w)
    pdf.ln(2)


def spend_table(pdf: Doc) -> None:
    heading(pdf, "Sample Extract: PS Panchayat Samiti Spend FY 2024-25 (Rs)", 10)
    pdf.set_font("Helvetica", "B", 8)
    col_w = [pdf.epw * 0.42, pdf.epw * 0.29, pdf.epw * 0.29]
    reset_x(pdf)
    pdf.set_fill_color(230, 236, 245)
    for i, h in enumerate(["Sector", "Allocation", "Actual spend"]):
        pdf.cell(col_w[i], 6, h, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for name, alloc, actual in SECTOR_DATA:
        reset_x(pdf)
        bold = name == "Total"
        if bold:
            pdf.set_font("Helvetica", "B", 8)
        pdf.cell(col_w[0], 5.5, name, border=1)
        pdf.cell(col_w[1], 5.5, f"{alloc:,}", border=1, align="R")
        pdf.cell(col_w[2], 5.5, f"{actual:,}", border=1, align="R")
        pdf.ln()
        pdf.set_font("Helvetica", "", 8)
    pdf.ln(1)


def make_diagrams() -> dict[str, Path]:
    DIAG.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    # 1) System architecture
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")
    boxes = [
        (0.3, 2.2, 2.2, 1.2, "#2563eb", "React Web\n(MapLibre + Charts\n+ Chat UI)"),
        (2.8, 2.2, 2.2, 1.2, "#0d9488", "FastAPI\nREST + /chat\nPipeline jobs"),
        (5.3, 2.2, 2.2, 1.2, "#7c3aed", "SQLite + GeoJSON\nDerived CSV\nManifest"),
        (7.8, 2.2, 1.9, 1.2, "#ea580c", "Local LLM\nAgent + Tools\n(Ollama / TG)"),
        (2.8, 0.4, 4.7, 1.2, "#64748b", "Pipeline: Classify -> Extract/OCR -> Normalize -> Load"),
    ]
    for x, y, w, h, color, label in boxes:
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05", fc=color, ec="white", lw=1.5))
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", color="white", fontsize=8, fontweight="bold")
    ax.annotate("", xy=(2.8, 2.8), xytext=(2.5, 2.8), arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5))
    ax.annotate("", xy=(5.3, 2.8), xytext=(5.0, 2.8), arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5))
    ax.annotate("", xy=(7.8, 2.8), xytext=(7.5, 2.8), arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5))
    ax.set_title("Figure 1: VikSetu three-tier system architecture", fontsize=10, fontweight="bold", pad=8)
    p1 = DIAG / "fig1_architecture.png"
    fig.savefig(p1, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    paths["arch"] = p1

    # 2) Pipeline
    fig, ax = plt.subplots(figsize=(8, 2.8))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 3)
    ax.axis("off")
    steps = [
        "Ingest", "Classify", "Text/OCR", "Tables", "Normalize",
        "Region", "Geocode", "Store", "Insights", "API",
    ]
    for i, s in enumerate(steps):
        x = 0.2 + i * 1.55
        ax.add_patch(mpatches.FancyBboxPatch((x, 1.1), 1.35, 0.9, boxstyle="round,pad=0.03", fc="#1e40af", ec="white"))
        ax.text(x + 0.67, 1.55, s, ha="center", va="center", color="white", fontsize=7, fontweight="bold")
        if i < len(steps) - 1:
            ax.annotate("", xy=(x + 1.38, 1.55), xytext=(x + 1.35, 1.55), arrowprops=dict(arrowstyle="->", color="#475569"))
    ax.text(8, 0.35, "Drag-and-drop workspace triggers N0-N10  |  v1: fixed chain with progress stepper", ha="center", fontsize=8, color="#334155")
    ax.set_title("Figure 2: Multi-AI data processing pipeline", fontsize=10, fontweight="bold")
    p2 = DIAG / "fig2_pipeline.png"
    fig.savefig(p2, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    paths["pipeline"] = p2

    # 3) Dashboard wireframe
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")
    ax.add_patch(mpatches.Rectangle((0.2, 5.1), 9.6, 0.7, fc="#1e293b", ec="none"))
    ax.text(5, 5.45, "VikSetu Dashboard  |  FY  Filters  |  Upload", color="white", ha="center", fontsize=9, fontweight="bold")
    ax.add_patch(mpatches.Rectangle((0.2, 0.5), 5.8, 4.4, fc="#dbeafe", ec="#64748b", lw=1.5))
    ax.text(3.1, 4.5, "MAP (Palghar talukas + layers)", ha="center", fontsize=9, fontweight="bold", color="#1e3a8a")
    ax.add_patch(mpatches.Rectangle((6.2, 2.5), 3.6, 2.4, fc="#fef3c7", ec="#64748b"))
    ax.text(7.9, 3.7, "Charts + KPI", ha="center", fontsize=8)
    ax.add_patch(mpatches.Rectangle((6.2, 0.5), 3.6, 1.8, fc="#dcfce7", ec="#64748b"))
    ax.text(7.9, 1.4, "Scheme table", ha="center", fontsize=8)
    ax.add_patch(mpatches.Rectangle((0.2, 0.05), 9.6, 0.35, fc="#f1f5f9", ec="#94a3b8"))
    ax.text(5, 0.22, "Chat panel  ->  ui_patch updates map / filters / charts", ha="center", fontsize=7.5)
    ax.set_title("Figure 3: Map-first web dashboard layout", fontsize=10, fontweight="bold")
    p3 = DIAG / "fig3_dashboard.png"
    fig.savefig(p3, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    paths["dashboard"] = p3

    # 4) Spend bar chart
    labels = [s[0] for s in SECTOR_DATA[:-1]]
    actuals = [s[2] for s in SECTOR_DATA[:-1]]
    fig, ax = plt.subplots(figsize=(8, 3))
    colors = ["#16a34a" if v > 0 else "#94a3b8" for v in actuals]
    ax.barh(labels, actuals, color=colors)
    ax.set_xlabel("Actual spend (Rs)")
    ax.set_title("Figure 4: Sector spend from PS report FY 2024-25 (pilot data)", fontsize=10, fontweight="bold")
    ax.tick_params(axis="both", labelsize=7)
    fig.tight_layout()
    p4 = DIAG / "fig4_spend_chart.png"
    fig.savefig(p4, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    paths["chart"] = p4

    # 5) Agent + UI flow
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 4)
    ax.axis("off")
    flow = [
        (0.5, 2, "User\n(EN/HI/MR)"),
        (2.5, 2, "Chat\nAPI"),
        (4.5, 2, "ReAct\nAgent"),
        (6.5, 2, "Tools\nSQL / UI"),
        (8.5, 2, "SQLite\nGeoJSON"),
        (10.2, 2, "React\nDashboard"),
    ]
    for x, y, t in flow:
        ax.add_patch(mpatches.Circle((x, y), 0.55, fc="#0369a1", ec="white", lw=1.2))
        ax.text(x, y, t, ha="center", va="center", color="white", fontsize=7, fontweight="bold")
    for i in range(len(flow) - 1):
        ax.annotate("", xy=(flow[i + 1][0] - 0.6, 2), xytext=(flow[i][0] + 0.6, 2),
                    arrowprops=dict(arrowstyle="->", color="#334155", lw=1.2))
    ax.text(6.5, 0.6, "ui_patch: filters, map_focus, set_layers, set_chart", ha="center", fontsize=8, style="italic")
    ax.set_title("Figure 5: Site-connected chatbot control flow", fontsize=10, fontweight="bold")
    p5 = DIAG / "fig5_agent_flow.png"
    fig.savefig(p5, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    paths["agent"] = p5

    return paths


def build() -> None:
    imgs = make_diagrams()
    pdf = Doc()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(MARGIN, MARGIN, MARGIN)

    # ================= PAGE 1 =================
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(15, 45, 75)
    reset_x(pdf)
    pdf.cell(pdf.epw, 10, "VikSetu", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(40, 40, 40)
    reset_x(pdf)
    pdf.multi_cell(
        pdf.epw, 5.5,
        "Civic Data Intelligence Platform: ingest, analyze, map, and AI-assisted exploration of government open data.",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.ln(1)
    pdf.set_font("Helvetica", "I", 9)
    para(pdf, "Big Data project | Multi-language documents (English, Hindi, Marathi) | Pilot: Palghar FY 2024-25")

    heading(pdf, "1. Introduction")
    para(
        pdf,
        "Local governance produces budgets, annual reports, scheme lists, and facility registries, but these "
        "sources use different formats: digital PDFs, scanned Marathi documents, web pages, and portal exports. "
        "VikSetu automates organization, extraction, and analysis, then presents results on an interactive map "
        "with charts and a chat assistant that controls the interface through validated tools.",
    )
    heading(pdf, "2. Problem Statement")
    para(
        pdf,
        "Citizens and administrators struggle to obtain a single view of allocation versus expenditure by sector "
        "and region, to locate facilities relative to tribal and rural population, and to trace figures back to "
        "official documents. Manual spreadsheet work does not scale and is error-prone for Devanagari tables.",
    )
    heading(pdf, "3. Objectives")
    bullets(pdf, [
        "Ingest heterogeneous civic files via a workspace with automatic classification.",
        "Extract fiscal and scheme tables into SQLite with full provenance metadata.",
        "Visualize Palghar on a MapLibre dashboard with linked KPIs and charts.",
        "Deploy a local-first ReAct agent; optional cloud LLM for OCR/table repair only.",
        "Provide audit-friendly traces for viva and project evaluation.",
    ])
    figure(pdf, imgs["arch"], "Figure 1: High-level architecture (see Page 2 for detail).", height_mm=52)

    # ================= PAGE 2 =================
    pdf.add_page()
    heading(pdf, "4. System Architecture")
    figure(pdf, imgs["arch"], None, height_mm=58)
    para(
        pdf,
        "The frontend is a React single-page application. MapLibre renders taluka polygons and optional facility "
        "pins. ECharts or Recharts render sector bars and status donuts. A shared filter state synchronizes map, "
        "table, and charts. The FastAPI backend serves GeoJSON layers, spend aggregates, upload endpoints, and "
        "the chat route. Python hosts the pipeline and extends the training ReAct agent with VikSetu-specific tools.",
    )
    heading(pdf, "5. AI and Language Strategy")
    para(
        pdf,
        "One multilingual orchestrator LLM (local Ollama or text-generation-webui) handles chat in English, Hindi, "
        "or Marathi, document classification, and JSON tool calls. Tesseract OCR handles bulk scanned text "
        "(mar+eng+hin). Optional Gemini Flash acts as backup for difficult table pages. Numeric answers always "
        "originate from SQL on SQLite views, not from free-form generation. Lightweight RAG may explain narrative "
        "sections but does not compute totals.",
    )
    figure(pdf, imgs["agent"], None, height_mm=48)
    heading(pdf, "6. Why Not RAG-Only?")
    para(
        pdf,
        "Retrieval-augmented generation splits tables across chunks and hallucinates amounts. VikSetu uses "
        "structured ETL plus tool calling, which aligns with Big Data learning outcomes: preprocessing, storage, "
        "analysis, visualization, and optional prediction on derived series.",
    )

    # ================= PAGE 3 =================
    pdf.add_page()
    heading(pdf, "7. Data Processing Pipeline")
    figure(pdf, imgs["pipeline"], None, height_mm=42)
    bullets(pdf, [
        "N0 Ingest: copy uploads to inbox/; compute hash; append manifest.json.",
        "N1 Classify: doc type, language, region (Palghar keywords), needs_ocr flag.",
        "N2/N3 Extract: PyMuPDF text path or Tesseract OCR for scanned ZP budget PDF.",
        "N4/N5: Table recovery and normalize to spend_lines / works schema.",
        "N6-N8: Region bind, village/taluka geocode, load SQLite and geo/ exports.",
        "N9-N10: Precompute insights.json; expose via REST for dashboard and agent.",
    ])
    heading(pdf, "8. Data Sources (Pilot)")
    bullets(pdf, [
        "Zilla Parishad Palghar budget 2024-25 (scanned, ~10 MB) and schemes web pages.",
        "Panchayat Samiti Palghar annual administration report 2024-25 (text PDF, validated).",
        "Maharashtra DES indicators; MGNREGA MIS; eGramSwaraj; MRSAC Health GIS; OSM POIs.",
    ])
    spend_table(pdf)
    figure(pdf, imgs["chart"], None, height_mm=50)

    # ================= PAGE 4 =================
    pdf.add_page()
    heading(pdf, "9. Geospatial and Dashboard Design")
    figure(pdf, imgs["dashboard"], None, height_mm=55)
    bullets(pdf, [
        "Layers: 8 talukas (choropleth spend or utilization), health/school pins, works by status color.",
        "Filters: financial year, taluka, sector, status (completed / in progress / planned / no spend).",
        "Linked views: selecting a chart category highlights map features; table sorts by amount.",
        "Chat ui_patch applies the same filter object as manual UI controls for consistent demos.",
    ])
    heading(pdf, "10. Agent Tools (Autonomous Behaviors)")
    bullets(pdf, [
        "query_spend, list_works: read-only SQL with document citations.",
        "set_filters, map_focus, set_layers, set_chart: dashboard control without DOM hacking.",
        "show_source: open provenance panel for examiners.",
        "Pipeline on upload: classify region, route OCR, reload derived tables.",
    ])
    heading(pdf, "11. Five-Day Build Plan")
    bullets(pdf, [
        "Day 1: SQLite + API + taluka GeoJSON.",
        "Day 2: React map and charts with filter state.",
        "Day 3: Agent /chat and ui_patch; scripted demo questions.",
        "Day 4: Upload stepper and pipeline demo; facility layer if time permits.",
        "Day 5: Documentation, PDF, video, README.",
    ])

    # ================= PAGE 5 =================
    pdf.add_page()
    heading(pdf, "12. Limitations and Ethics")
    bullets(pdf, [
        "Pilot uses authentic PS extract; full ZP OCR may be partial within deadline.",
        "Geocoding may remain taluka-level until village gazetteer matching is complete.",
        "Public data only; helper tool, not statutory audit or RTI replacement.",
    ])
    heading(pdf, "13. Success Metrics")
    bullets(pdf, [
        "Real FY 2024-25 totals displayed from database, not hard-coded in UI.",
        "Map renders Palghar talukas; chat changes filters and map focus live.",
        "Upload runs classify/extract with logged trace.",
    ])
    heading(pdf, "14. Deliverables")
    bullets(pdf, [
        "viksetu-api, viksetu-web, pipeline scripts, agent tools, data/ folder.",
        "This document, implementation notes, demonstration recording.",
    ])
    heading(pdf, "15. Conclusion")
    para(
        pdf,
        "VikSetu bridges fragmented government records and actionable spatial analytics. The Palghar pilot "
        "demonstrates real expenditure patterns (for example works and water spending with zero education/health "
        "spend in the PS consolidated extract). The architecture scales to additional districts by repeating ingest "
        "and region binding without redesigning the agent or dashboard core.",
    )
    heading(pdf, "16. References")
    bullets(pdf, [
        "zppalghar.gov.in; Panchayat Samiti Palghar annual report PDF.",
        "mahades.maharashtra.gov.in; nregastrep.nic.in; egramswaraj.gov.in.",
        "MRSAC Health GIS; Open Budgets India; Datameet / OSM boundaries.",
        "Training modules: agent.py, tools.py, llm.py (ReAct pattern).",
    ])
    pdf.set_font("Helvetica", "I", 8)
    para(pdf, "Generated for academic submission. Team may add names and guide on cover before printing.")

    pdf.output(str(OUT))
    n = pdf.page_no()
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes, {n} pages)")
    print(f"Diagrams in {DIAG}")


if __name__ == "__main__":
    build()
