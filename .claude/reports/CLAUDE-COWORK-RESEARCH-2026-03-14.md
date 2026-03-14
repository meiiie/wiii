# Claude Cowork — Báo cáo nghiên cứu toàn diện
**Date:** 2026-03-14
**Auditor:** Claude Opus 4.6 (AI Lead)
**Mục đích:** Hiểu kiến trúc, tính năng, và cách áp dụng cho Wiii AI

---

## 1. Claude Cowork là gì?

Claude Cowork = **"Claude Code cho knowledge work"** — biến Claude từ chatbot thành **đồng nghiệp AI** có khả năng tự chủ thực hiện công việc phức tạp trên máy tính người dùng.

**Ra mắt:** 30/01/2026 (research preview)
**Platform:** macOS (ban đầu), Windows (10/02/2026)
**Pricing:** Có sẵn trong tất cả paid plans (Pro, Max, Team, Enterprise)

---

## 2. Kiến trúc kỹ thuật

### 2.1 Agentic Loop (cốt lõi)
```
User giao task → Claude lên kế hoạch → Chia thành subtasks
    → Thực thi song song (sub-agents) → Kiểm tra kết quả
    → Hỏi user nếu gặp roadblock → Bàn giao deliverables
```

**Khác chatbot truyền thống:**
- Chatbot: User hỏi → AI trả lời → User hỏi tiếp
- Cowork: User giao việc → AI tự làm → Cập nhật progress → Bàn giao

### 2.2 Sandbox Architecture
```
┌─────────────────────────────────┐
│         Claude Desktop          │
│  ┌───────────────────────────┐  │
│  │   Isolated Virtual Machine │  │
│  │  ┌─────────────────────┐  │  │
│  │  │   Claude Agent      │  │  │
│  │  │   (Opus 4.6, 1M)    │  │  │
│  │  └──────┬──────────────┘  │  │
│  │         │                 │  │
│  │    ┌────┴────┐            │  │
│  │    │ Folder  │            │  │
│  │    │ Access  │            │  │
│  │    │ (scoped)│            │  │
│  │    └─────────┘            │  │
│  └───────────────────────────┘  │
│              │                  │
│    ┌─────────┴─────────┐       │
│    │  MCP Connectors   │       │
│    │  (Google, Slack,   │       │
│    │   Salesforce...)   │       │
│    └───────────────────┘       │
└─────────────────────────────────┘
```

**Security model:**
- **VM-first sandboxing**: Chạy trong VM cách ly
- **Folder-scoped permissions**: Chỉ truy cập thư mục user cho phép
- **Explicit permission**: Hỏi trước khi xóa file hoặc hành động quan trọng
- **No memory across sessions**: Không lưu context giữa các phiên

### 2.3 Sub-Agent Coordination
```
Main Agent (nhận task từ user)
    ├── Sub-agent 1: Research (web search, file reading)
    ├── Sub-agent 2: Data processing (Excel, analysis)
    ├── Sub-agent 3: Writing (documents, presentations)
    └── Coordinator: Aggregate results → Quality check → Deliver
```

- Claude chia task phức tạp thành subtasks
- Spawn nhiều Claude instances chạy song song
- Coordinator tổng hợp kết quả

---

## 3. Plugin System (kiến trúc mở rộng)

### 3.1 Plugin Structure (file-based, không cần code)
```
my-plugin/
├── plugin.json          # Metadata (name, description, version)
├── skills/
│   ├── research.md      # Procedural knowledge (what to do, how)
│   └── analysis.md      # Domain-specific methodology
├── connectors/
│   └── crm.json         # MCP connector config
├── commands/
│   └── /prospect.md     # Slash command definition
└── sub-agents/
    └── data-analyst.md  # Specialized sub-agent role
```

### 3.2 Bốn thành phần Plugin

| Component | Format | Mô tả |
|-----------|--------|--------|
| **Skills** | Markdown | "Brain" của plugin — quy trình, methodology, best practices |
| **Connectors** | JSON (MCP) | Kết nối external tools (Google Drive, Salesforce, FactSet) |
| **Slash Commands** | Markdown | Quick actions cho user (/prospect, /schedule) |
| **Sub-agents** | Markdown | Specialized Claude instances cho task cụ thể |

### 3.3 MCP Connectors có sẵn (March 2026)
- Google Workspace (Calendar, Drive, Gmail)
- Slack, Salesforce, DocuSign
- Apollo, Clay, Outreach (sales)
- FactSet, MSCI, S&P Global (finance)
- LegalZoom, Harvey (legal)
- WordPress, Similarweb
- Common Room (community)

### 3.4 Pre-built Plugins (11 plugins)
1. Productivity
2. Enterprise Search
3. Sales
4. Finance
5. Data Analysis
6. Legal Document Review
7. Marketing
8. Customer Support
9. Product Management
10. Biology Research
11. Plugin Creation Tools

**Open source:** https://github.com/anthropics/knowledge-work-plugins

---

## 4. Enterprise Features

### 4.1 Private Plugin Marketplace
- Admin tạo marketplace riêng cho tổ chức
- Per-user provisioning + auto-install
- Private GitHub repos làm nguồn plugins
- Kiểm soát plugin nào team nào dùng

### 4.2 Customize (Admin Dashboard)
- Quản lý plugins, skills, connectors tập trung
- Template cho từng department (HR, Sales, Engineering...)
- Claude guided setup: hỏi admin → tự tạo plugin config

### 4.3 Department-specific Plugins
- HR, Design, Engineering, Operations
- Financial Analysis, Investment Banking
- Equity Research, Private Equity, Wealth Management
- Mỗi plugin thiết kế cùng chuyên gia ngành

### 4.4 Governance
- **OpenTelemetry**: Track usage, costs, tool activity
- **Connector admin**: Quản lý MCP connections tập trung
- **Lưu ý**: Cowork CHƯA có Audit Logs, Compliance API, Data Exports

---

## 5. Tính năng nổi bật

### 5.1 Local File Access
- Đọc, chỉnh sửa, tạo file trong thư mục user chọn
- Hỗ trợ: Excel (formulas, formatting), PowerPoint, Word, PDF, code files
- Không cần upload/download thủ công

### 5.2 Scheduled Tasks
- `/schedule` command hoặc sidebar management
- Chạy tự động theo lịch (khi máy mở + app đang chạy)
- Ví dụ: "Mỗi sáng thứ 2, tổng hợp email tuần trước thành report"

### 5.3 Cross-App Workflows
- Excel → PowerPoint (research → presentation)
- Claude for Chrome → Cowork (web data → local file)
- MCP connectors → Local files (CRM data → report)

### 5.4 Folder/Global Instructions
- **Global**: Preferences áp dụng mọi session (tone, format, role)
- **Folder**: Context specific cho từng thư mục/project
- Claude tự cập nhật folder instructions khi cần

---

## 6. So sánh: Claude Cowork vs Microsoft Copilot Cowork

| Tiêu chí | Claude Cowork | Microsoft Copilot Cowork |
|----------|---------------|-------------------------|
| **Ra mắt** | 30/01/2026 | 09/03/2026 |
| **Chạy ở đâu** | Local (Desktop app + VM) | Cloud (Microsoft 365) |
| **File access** | Local folders (sandbox) | Microsoft Graph (cloud files) |
| **AI Model** | Claude Opus 4.6 (1M context) | Claude Opus 4.6 (via Anthropic) |
| **Ecosystem** | MCP connectors (open) | Microsoft 365 (closed) |
| **Plugin system** | File-based (MD + JSON) | Microsoft Agent 365 |
| **Giá** | $20/tháng (Pro) | $25/tháng (M365 Copilot) |
| **Target** | Power users, developers | Enterprise teams, M365 users |
| **Điểm mạnh** | Flexibility, open MCP, local control | M365 integration depth, Work IQ |

**Key insight:** Microsoft chọn Claude Opus 4.6 làm model cho Copilot Cowork — chứng minh Claude là model tốt nhất cho agentic work.

---

## 7. Bài học cho Wiii AI

### 7.1 Kiến trúc tương tự đã có
Wiii đã có nhiều thành phần giống Cowork:
- **Multi-agent system** (Supervisor → RAG/Tutor/Memory/Direct) ≈ Sub-agent coordination
- **Tool registry** (40+ tools) ≈ Plugins/Skills
- **MCP client/server** (Sprint 56, 194) ≈ MCP Connectors
- **Agentic loop** (Sprint 57) ≈ Agentic Loop
- **Living Agent** (Soul AGI) ≈ Autonomous personality

### 7.2 Những gì Wiii CÓ THỂ học từ Cowork

| Cowork Feature | Wiii Equivalent | Gap |
|----------------|-----------------|-----|
| File-based plugins (MD+JSON) | domain.yaml + SKILL.md | Rất gần — cần standardize |
| Slash commands | Chưa có trong chat | Thêm /command system |
| Scheduled tasks | Chưa có | Thêm recurring tasks |
| Folder instructions | Chưa có | Thêm project context |
| Sub-agent parallelism | Có (LangGraph) | Cần expose UI |
| Plugin marketplace | Chưa có | Tạo domain plugin store |
| Cross-app workflows | LMS integration (Sprint 220) | Mở rộng connectors |
| Progress indicators | Thinking blocks | Đã có — polish UX |

### 7.3 Roadmap đề xuất

**Phase 1 — Slash Commands (2 ngày)**
- `/search` — web search
- `/compare` — visual comparison
- `/quiz` — tạo quiz
- `/explain` — giải thích chi tiết
- Implement trong ChatInput component

**Phase 2 — Task System (1 tuần)**
- Background tasks (AI chạy nền)
- Progress tracking UI
- Task history

**Phase 3 — Plugin Marketplace (2 tuần)**
- Standardize domain plugins (YAML+MD)
- Plugin install/uninstall UI
- Community plugins (open source)

**Phase 4 — Scheduled Tasks (1 tuần)**
- Cron-based recurring tasks
- Daily/weekly reports
- Auto-study reminders

---

## 8. Tham khảo

- [Introducing Cowork](https://claude.com/blog/cowork-research-preview) — Anthropic official blog
- [Cowork Product Page](https://claude.com/product/cowork) — Claude.com
- [Cowork Plugins](https://claude.com/blog/cowork-plugins) — Plugin architecture
- [Enterprise Plugins](https://claude.com/blog/cowork-plugins-across-enterprise) — Private marketplaces
- [Get Started with Cowork](https://support.claude.com/en/articles/13345190-get-started-with-cowork) — Help Center
- [Cowork Architecture (Medium)](https://medium.com/@Micheal-Lanham/claude-cowork-architecture-how-anthropic-built-a-desktop-agent-that-actually-respects-your-files-cf601325df86) — Technical deep dive
- [Knowledge Work Plugins (GitHub)](https://github.com/anthropics/knowledge-work-plugins) — Open source
- [Claude Cowork vs Copilot](https://datasciencedojo.com/blog/claude-cowork-vs-copilot-cowork/) — Comparison
- [Copilot Cowork (Microsoft)](https://www.microsoft.com/en-us/microsoft-365/blog/2026/03/09/copilot-cowork-a-new-way-of-getting-work-done/) — Microsoft announcement
- [Claude Cowork Enterprise Guide](https://almcorp.com/blog/claude-cowork-plugins-enterprise-guide/) — ALM Corp analysis
