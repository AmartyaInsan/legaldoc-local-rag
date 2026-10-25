import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# Set up figure with 16:9 widescreen ratio (1920x1080 at 160 DPI)
fig = plt.figure(figsize=(19.2, 10.8), facecolor='#0B0F19', dpi=160)
ax = fig.add_axes([0, 0, 1, 1], facecolor='#0B0F19')
ax.set_xlim(0, 1920)
ax.set_ylim(0, 1080)
ax.axis('off')

# Font settings with Segoe UI and DejaVu Sans fallback
plt.rcParams['font.sans-serif'] = ['Segoe UI', 'DejaVu Sans', 'Arial']

font_family = 'sans-serif'

# Helper: Draw Card with subtle glow and sharp border
def draw_card(ax, x, y, w, h, bg_color='#151D2A', border_color='#2D3B4F', border_width=1.5, radius=14, alpha=1.0):
    # Outer ambient shadow
    shadow = FancyBboxPatch((x - 1, y - 2), w + 2, h + 2,
                            boxstyle=f"round,pad=0,rounding_size={radius}",
                            facecolor='#000000', edgecolor='none', alpha=0.4, zorder=2)
    ax.add_patch(shadow)
    # Main Box
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle=f"round,pad=0,rounding_size={radius}",
                         facecolor=bg_color, edgecolor=border_color, linewidth=border_width,
                         alpha=alpha, zorder=3)
    ax.add_patch(box)
    return box

# Helper: Draw Pill Badge
def draw_badge(ax, x, y, text, bg_color='#1E293B', text_color='#93C5FD', border_color='#3B82F6', font_size=11, pad_x=14):
    char_w = 7.8 if font_size <= 11 else 8.5
    w = len(text) * char_w + (pad_x * 2)
    h = 28
    box = FancyBboxPatch((x, y), w, h,
                         boxstyle="round,pad=0,rounding_size=14",
                         facecolor=bg_color, edgecolor=border_color, linewidth=1.2, zorder=5)
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text, color=text_color, fontsize=font_size,
            fontweight='bold', ha='center', va='center', zorder=6, fontfamily=font_family)
    return w

# Helper: Draw smooth directed arrow
def draw_arrow(ax, start, end, color='#3B82F6', width=2.4, style='->', label='', label_pos=(0, 0), label_color='#94A3B8'):
    arrow = FancyArrowPatch(start, end, arrowstyle=style, mutation_scale=16,
                            color=color, linewidth=width, zorder=4,
                            connectionstyle="arc3,rad=0.0")
    ax.add_patch(arrow)
    if label:
        ax.text(label_pos[0], label_pos[1], label, color=label_color, fontsize=10,
                ha='center', va='center', fontweight='bold', zorder=6,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#0B0F19', edgecolor=color, linewidth=0.8, alpha=0.95))

# ==================== 1. HEADER SECTION ====================
ax.text(90, 1025, "ARSITEKTUR AGENTIC RAG & ALUR SISTEM KERJA", 
        color='#FFFFFF', fontsize=26, fontweight='bold', ha='left', va='top', fontfamily=font_family)
ax.text(90, 990, "Solusi Dokumen Hukum 100% On-Premise / Close-Environment dengan Hybrid Retrieval, Multi-Sub-Agent, dan Strict Grounding",
        color='#94A3B8', fontsize=13, fontweight='normal', ha='left', va='top', fontfamily=font_family)

# Header Feature Badges
bx = 1080
bx += draw_badge(ax, bx, 995, "[LOCAL] 100% Offline Privacy", '#0C4A6E', '#38BDF8', '#0284C7', font_size=10.5) + 12
bx += draw_badge(ax, bx, 995, "[GUARDRAIL] Zero-Hallucination", '#064E3B', '#34D399', '#10B981', font_size=10.5) + 12
bx += draw_badge(ax, bx, 995, "[BILINGUAL] ID <-> EN Cross-Lingual", '#4C1D95', '#C084FC', '#8B5CF6', font_size=10.5)

# ==================== 2. TAHAP 1: DATA INGESTION & INDEXING ====================
# Background Lane Container
draw_card(ax, 70, 580, 1780, 370, bg_color='#0F172A', border_color='#1E293B', radius=18, alpha=0.95)
draw_badge(ax, 95, 915, "TAHAP 1: DATA INGESTION & INDEXING PIPELINE (OFFLINE / PREPARATION)", '#1E293B', '#38BDF8', '#0284C7', font_size=11)

# Step 1.1: Document Ingestion Card
c1_x, c1_y, c1_w, c1_h = 95, 605, 335, 290
draw_card(ax, c1_x, c1_y, c1_w, c1_h, bg_color='#162032', border_color='#334155')
ax.text(c1_x + 20, c1_y + 255, "1. Multi-Format Ingestion", color='#38BDF8', fontsize=15, fontweight='bold')
ax.text(c1_x + 20, c1_y + 230, "Knowledge Base Interface", color='#94A3B8', fontsize=11.5)

# Format badges
formats = [("PDF", "#EF4444"), ("DOCX", "#3B82F6"), ("PPTX", "#F97316"), ("XLSX", "#10B981"), ("CSV", "#06B6D4")]
for i, (fmt, col) in enumerate(formats):
    fx = c1_x + 18 + i * 59
    fy = c1_y + 180
    ax.add_patch(FancyBboxPatch((fx, fy), 52, 26, boxstyle="round,pad=0,rounding_size=6",
                                facecolor='#0B0F19', edgecolor=col, linewidth=1.2, zorder=5))
    ax.text(fx + 26, fy + 13, fmt, color=col, fontsize=9.5, fontweight='bold', ha='center', va='center', zorder=6)

ax.text(c1_x + 20, c1_y + 145, 
        "- Validasi tipe ekstensi & sanitasi file\n"
        "- Deteksi duplikasi berkas via SHA-256\n"
        "- Ekstraksi teks multi-kolom & tabel\n"
        "- Real-time progress upload status",
        color='#CBD5E1', fontsize=10.5, va='top', linespacing=1.65)

# Arrow 1 -> 2
draw_arrow(ax, (c1_x + c1_w, c1_y + 145), (c1_x + c1_w + 75, c1_y + 145), color='#0284C7', width=2.6, label="File Stream", label_pos=(c1_x + c1_w + 37, c1_y + 170))

# Step 1.2: Chunking & Deduplication Card
c2_x, c2_y, c2_w, c2_h = 505, 605, 345, 290
draw_card(ax, c2_x, c2_y, c2_w, c2_h, bg_color='#162032', border_color='#334155')
ax.text(c2_x + 20, c2_y + 255, "2. Parsing & Chunking", color='#38BDF8', fontsize=15, fontweight='bold')
ax.text(c2_x + 20, c2_y + 230, "Granular Document Processing", color='#94A3B8', fontsize=11.5)

ax.add_patch(FancyBboxPatch((c2_x + 18, c2_y + 175), 305, 36, boxstyle="round,pad=0,rounding_size=8",
                            facecolor='#0B0F19', edgecolor='#0284C7', linewidth=1.2, zorder=5))
ax.text(c2_x + 170, c2_y + 193, "Recursive Character Splitter (800 chars)", color='#38BDF8', fontsize=10.5, fontweight='bold', ha='center', va='center', zorder=6)

ax.text(c2_x + 20, c2_y + 145,
        "- Sliding window overlap (100 chars)\n"
        "- Mempertahankan integritas pasal / bab\n"
        "- Ekstraksi metadata: Nomor Halaman &\n"
        "  Nama File untuk sitasi klik interaktif",
        color='#CBD5E1', fontsize=10.5, va='top', linespacing=1.65)

# Arrow 2 -> 3
draw_arrow(ax, (c2_x + c2_w, c2_y + 145), (c2_x + c2_w + 75, c2_y + 145), color='#0284C7', width=2.6, label="Text Chunks", label_pos=(c2_x + c2_w + 37, c2_y + 170))

# Step 1.3: Local Embedding Engine Card
c3_x, c3_y, c3_w, c3_h = 925, 605, 365, 290
draw_card(ax, c3_x, c3_y, c3_w, c3_h, bg_color='#162032', border_color='#38BDF8')
ax.text(c3_x + 20, c3_y + 255, "3. Ollama Embedding Engine", color='#38BDF8', fontsize=15, fontweight='bold')
ax.text(c3_x + 20, c3_y + 230, "Local Vector Representation", color='#94A3B8', fontsize=11.5)

ax.add_patch(FancyBboxPatch((c3_x + 18, c3_y + 172), 325, 42, boxstyle="round,pad=0,rounding_size=8",
                            facecolor='#0C4A6E', edgecolor='#38BDF8', linewidth=1.2, zorder=5))
ax.text(c3_x + 180, c3_y + 193, "Model: nomic-embed-text (768-dim)", color='#FFFFFF', fontsize=11, fontweight='bold', ha='center', va='center', zorder=6)

ax.text(c3_x + 20, c3_y + 145,
        "- 100% Komputasi di Mesin Lokal (CPU/GPU)\n"
        "- Representasi semantik lintas bahasa (ID/EN)\n"
        "- Nol token data dikirim ke server luar\n"
        "- Batch embedding teroptimasi dengan Ollama",
        color='#CBD5E1', fontsize=10.5, va='top', linespacing=1.65)

# Arrow 3 -> 4
draw_arrow(ax, (c3_x + c3_w, c3_y + 145), (c3_x + c3_w + 75, c3_y + 145), color='#0284C7', width=2.6, label="Store Vectors", label_pos=(c3_x + c3_w + 37, c3_y + 170))

# Step 1.4: Hybrid Local Storage Card
c4_x, c4_y, c4_w, c4_h = 1365, 605, 455, 290
draw_card(ax, c4_x, c4_y, c4_w, c4_h, bg_color='#162032', border_color='#10B981')
ax.text(c4_x + 20, c4_y + 255, "4. Hybrid Local Storage", color='#34D399', fontsize=15, fontweight='bold')
ax.text(c4_x + 20, c4_y + 230, "Dual Engine Indexing (Dense + Sparse)", color='#94A3B8', fontsize=11.5)

# Sub-box ChromaDB
ax.add_patch(FancyBboxPatch((c4_x + 18, c4_y + 135), 200, 75, boxstyle="round,pad=0,rounding_size=8",
                            facecolor='#064E3B', edgecolor='#10B981', linewidth=1.2, zorder=5))
ax.text(c4_x + 118, c4_y + 180, "ChromaDB (Vector)", color='#A7F3D0', fontsize=11.5, fontweight='bold', ha='center', va='center', zorder=6)
ax.text(c4_x + 118, c4_y + 155, "Dense HNSW Cosine Index\nPencarian Konseptual", color='#E2E8F0', fontsize=9, ha='center', va='center', zorder=6)

# Sub-box SQLite
ax.add_patch(FancyBboxPatch((c4_x + 232, c4_y + 135), 200, 75, boxstyle="round,pad=0,rounding_size=8",
                            facecolor='#1E293B', edgecolor='#94A3B8', linewidth=1.2, zorder=5))
ax.text(c4_x + 332, c4_y + 180, "SQLite (BM25 + FTS)", color='#E2E8F0', fontsize=11.5, fontweight='bold', ha='center', va='center', zorder=6)
ax.text(c4_x + 332, c4_y + 155, "Pencarian Kata Kunci / Pasal\n& Metadata Dokumen", color='#94A3B8', fontsize=9, ha='center', va='center', zorder=6)

ax.text(c4_x + 20, c4_y + 110,
        "- Isolasi Dokumen Workspace via Checkbox ID\n"
        "- Metadata filtering: doc_id, filename, page, sha256",
        color='#CBD5E1', fontsize=10.5, va='top', linespacing=1.55)


# ==================== 3. TAHAP 2: AGENTIC RETRIEVAL & GENERATION ====================
# Background Lane Container
draw_card(ax, 70, 50, 1780, 485, bg_color='#0F172A', border_color='#1E293B', radius=18, alpha=0.95)
draw_badge(ax, 95, 495, "TAHAP 2: AGENTIC ROUTING, HYBRID RETRIEVAL & GENERATION (RUNTIME)", '#312E81', '#A5B4FC', '#6366F1', font_size=11)

# Step 2.1: User Interface & Query Input
u_x, u_y, u_w, u_h = 95, 75, 335, 395
draw_card(ax, u_x, u_y, u_w, u_h, bg_color='#162032', border_color='#3B82F6')
ax.text(u_x + 20, u_y + 360, "1. User Input & Workspace", color='#60A5FA', fontsize=15, fontweight='bold')
ax.text(u_x + 20, u_y + 335, "React + Vite Chat UI", color='#94A3B8', fontsize=11.5)

# Prompt preview box
ax.add_patch(FancyBboxPatch((u_x + 18, u_y + 225), 295, 85, boxstyle="round,pad=0,rounding_size=8",
                            facecolor='#0B0F19', edgecolor='#3B82F6', linewidth=1, zorder=5))
ax.text(u_x + 28, u_y + 285, "[Prompt User]", color='#93C5FD', fontsize=10.5, fontweight='bold', zorder=6)
ax.text(u_x + 28, u_y + 262, '"Bandingkan klausul terminasi Dokumen A & B"', color='#E2E8F0', fontsize=9.5, style='italic', zorder=6)
ax.text(u_x + 28, u_y + 242, '"What are the liability caps under Section 4?"', color='#93C5FD', fontsize=9.5, style='italic', zorder=6)

# Checkbox badge
ax.text(u_x + 20, u_y + 195, "Workspace Filtering (Centang Dokumen):", color='#CBD5E1', fontsize=10.5, fontweight='bold')
ax.add_patch(FancyBboxPatch((u_x + 18, u_y + 150), 295, 36, boxstyle="round,pad=0,rounding_size=6",
                            facecolor='#1E293B', edgecolor='#10B981', linewidth=1, zorder=5))
ax.text(u_x + 165, u_y + 168, "[X] Perjanjian_A.pdf    [X] Addendum_B.docx", color='#34D399', fontsize=9.5, fontweight='bold', ha='center', va='center', zorder=6)

ax.text(u_x + 20, u_y + 125,
        "- Multi-Document Checkbox Selection\n"
        "- Toggle Web Search (Opt-in DuckDuckGo)\n"
        "- Riwayat Chat: Rename, Pin, & Delete\n"
        "- Model Switcher (Main & Sub-Agent)",
        color='#94A3B8', fontsize=10, va='top', linespacing=1.55)

# Arrow User -> Agent Core
draw_arrow(ax, (u_x + u_w, u_y + 260), (u_x + u_w + 65, u_y + 260), color='#60A5FA', width=2.6, label="Prompt + Scope", label_pos=(u_x + u_w + 32, u_y + 285))

# Step 2.2: Agent Router Core
r_x, r_y, r_w, r_h = 495, 75, 345, 395
draw_card(ax, r_x, r_y, r_w, r_h, bg_color='#1E1B4B', border_color='#818CF8')
ax.text(r_x + 20, r_y + 360, "2. Agent Decision Core", color='#A5B4FC', fontsize=15, fontweight='bold')
ax.text(r_x + 20, r_y + 335, "Intent Planning & Tool Dispatcher", color='#C7D2FE', fontsize=11.5)

ax.add_patch(FancyBboxPatch((r_x + 18, r_y + 215), 305, 95, boxstyle="round,pad=0,rounding_size=8",
                            facecolor='#0B0F19', edgecolor='#6366F1', linewidth=1.2, zorder=5))
ax.text(r_x + 28, r_y + 285, "Query & Intent Analysis:", color='#C7D2FE', fontsize=10.5, fontweight='bold', zorder=6)
ax.text(r_x + 28, r_y + 262, "1. Deteksi Bahasa (ID <-> EN Cross-Lingual)", color='#E0E7FF', fontsize=9.5, zorder=6)
ax.text(r_x + 28, r_y + 244, "2. Verifikasi Cakupan Dokumen Aktif", color='#E0E7FF', fontsize=9.5, zorder=6)
ax.text(r_x + 28, r_y + 226, "3. Penentuan Tool & Peran Sub-Agent", color='#E0E7FF', fontsize=9.5, zorder=6)

ax.text(r_x + 20, r_y + 180, "Pola Eksekusi Terpilih:", color='#CBD5E1', fontsize=10.5, fontweight='bold')
ax.text(r_x + 20, r_y + 155,
        "- Tanya Dokumen Tunggal -> Tool Hybrid Search\n"
        "- Komparasi Multi-Dokumen -> Panggil Sub-Agent\n"
        "- Perhitungan / Data Tabel -> Tool Text-to-SQL\n"
        "- Referensi Luar -> Tool Web Search DuckDuckGo",
        color='#E2E8F0', fontsize=10, va='top', linespacing=1.6)

# Arrow Router -> Tools
draw_arrow(ax, (r_x + r_w, r_y + 260), (r_x + r_w + 65, r_y + 260), color='#818CF8', width=2.6, label="Dispatch", label_pos=(r_x + r_w + 32, r_y + 285))

# Step 2.3: Dynamic Execution Tools
t_x, t_y, t_w, t_h = 905, 75, 470, 395
draw_card(ax, t_x, t_y, t_w, t_h, bg_color='#162032', border_color='#38BDF8')
ax.text(t_x + 20, t_y + 360, "3. Execution Tools & Sub-Agents", color='#38BDF8', fontsize=15, fontweight='bold')
ax.text(t_x + 20, t_y + 335, "Spesialisasi Berdasarkan Pola Pertanyaan", color='#94A3B8', fontsize=11.5)

# Tool A: Hybrid Search
ax.add_patch(FancyBboxPatch((t_x + 18, t_y + 235), 430, 80, boxstyle="round,pad=0,rounding_size=8",
                            facecolor='#0B0F19', edgecolor='#3B82F6', linewidth=1.2, zorder=5))
ax.text(t_x + 30, t_y + 292, "[Tool A] Hybrid Search (Vector + BM25 + Re-Ranker)", color='#60A5FA', fontsize=10.5, fontweight='bold', zorder=6)
ax.text(t_x + 30, t_y + 272, "- Gabungkan Dense Semantic (ChromaDB) + Sparse Lexical (SQLite)", color='#CBD5E1', fontsize=9, zorder=6)
ax.text(t_x + 30, t_y + 254, "- Algoritma RRF (Reciprocal Rank Fusion) untuk scoring relevansi terbaik", color='#94A3B8', fontsize=9, zorder=6)

# Tool B: Sub-Agent Comparison
ax.add_patch(FancyBboxPatch((t_x + 18, t_y + 140), 430, 82, boxstyle="round,pad=0,rounding_size=8",
                            facecolor='#0B0F19', edgecolor='#8B5CF6', linewidth=1.2, zorder=5))
ax.text(t_x + 30, t_y + 198, "[Tool B] Sub-Agent Multi-Doc Comparison", color='#C084FC', fontsize=10.5, fontweight='bold', zorder=6)
ax.text(t_x + 30, t_y + 178, "- Membaca & menganalisis N-dokumen secara independen", color='#CBD5E1', fontsize=9, zorder=6)
ax.text(t_x + 30, t_y + 160, "- Sintesis tabel perbandingan poin-per-poin & ringkasan perbedaan", color='#94A3B8', fontsize=9, zorder=6)

# Tool C & D
ax.add_patch(FancyBboxPatch((t_x + 18, t_y + 40), 205, 85, boxstyle="round,pad=0,rounding_size=8",
                            facecolor='#0B0F19', edgecolor='#10B981', linewidth=1, zorder=5))
ax.text(t_x + 28, t_y + 102, "[Tool C] Text-to-SQL", color='#34D399', fontsize=10, fontweight='bold', zorder=6)
ax.text(t_x + 28, t_y + 78, "Query otomatis ke tabel\nCSV & SQLite terstruktur", color='#94A3B8', fontsize=8.5, linespacing=1.35, zorder=6)

ax.add_patch(FancyBboxPatch((t_x + 240, t_y + 40), 205, 85, boxstyle="round,pad=0,rounding_size=8",
                            facecolor='#0B0F19', edgecolor='#F59E0B', linewidth=1, zorder=5))
ax.text(t_x + 250, t_y + 102, "[Tool D] Web Search", color='#FBBF24', fontsize=10, fontweight='bold', zorder=6)
ax.text(t_x + 250, t_y + 78, "DuckDuckGo API\n(Eksternal & hanya bila diminta)", color='#94A3B8', fontsize=8.5, linespacing=1.35, zorder=6)

# Arrow Tools -> Generation
draw_arrow(ax, (t_x + t_w, r_y + 260), (t_x + t_w + 65, r_y + 260), color='#10B981', width=2.6, label="Context Chunks", label_pos=(t_x + t_w + 32, r_y + 285))

# Step 2.4: LLM Generation & Strict Grounding
g_x, g_y, g_w, g_h = 1440, 75, 380, 395
draw_card(ax, g_x, g_y, g_w, g_h, bg_color='#162032', border_color='#10B981')
ax.text(g_x + 20, g_y + 360, "4. Generation & Grounding", color='#34D399', fontsize=15, fontweight='bold')
ax.text(g_x + 20, g_y + 335, "Ollama LLM Engine (qwen2.5:7b)", color='#94A3B8', fontsize=11.5)

# Guardrail Box
ax.add_patch(FancyBboxPatch((g_x + 18, g_y + 225), 340, 85, boxstyle="round,pad=0,rounding_size=8",
                            facecolor='#064E3B', edgecolor='#10B981', linewidth=1.2, zorder=5))
ax.text(g_x + 28, g_y + 285, "[GUARDRAIL] Strict Context Grounding", color='#A7F3D0', fontsize=10, fontweight='bold', zorder=6)
ax.text(g_x + 28, g_y + 262, '"Jawab HANYA dari konteks dokumen aktif.', color='#ECFDF5', fontsize=9, style='italic', zorder=6)
ax.text(g_x + 28, g_y + 242, 'Jika informasi tidak ada, tolak dengan jujur."', color='#ECFDF5', fontsize=9, style='italic', zorder=6)

# Response features box
ax.add_patch(FancyBboxPatch((g_x + 18, g_y + 40), 340, 168, boxstyle="round,pad=0,rounding_size=8",
                            facecolor='#0B0F19', edgecolor='#38BDF8', linewidth=1.2, zorder=5))
ax.text(g_x + 28, g_y + 185, "Hasil Akhir (Frontend UI):", color='#38BDF8', fontsize=10.5, fontweight='bold', zorder=6)
ax.text(g_x + 28, g_y + 158, "- SSE Streaming Response (Markdown real-time)\n"
                            "- Sitasi Interaktif [1], [2] (Klik tinjau kutipan)\n"
                            "- Tabel Matriks Komparasi yang terstruktur rapi\n"
                            "- Terjemahan cerdas otomatis (Cross-Lingual)\n"
                            "- Tautan sumber eksternal jika web search aktif",
        color='#CBD5E1', fontsize=9.2, va='top', linespacing=1.65, zorder=6)

# ==================== 4. CONNECTOR BETWEEN STORAGE AND RETRIEVAL ====================
draw_arrow(ax, (1580, 605), (1140, 470), color='#0284C7', width=2.4, style='<->', label="Vector & Keyword Retrieval", label_pos=(1370, 545))

# Save image with optimal margins
output_png = "architecture_diagram.png"
output_svg = "architecture_diagram.svg"

plt.savefig(output_png, dpi=160, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight', pad_inches=0.4)
plt.savefig(output_svg, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight', pad_inches=0.4)
print(f"Generated successfully: {output_png} and {output_svg}")
