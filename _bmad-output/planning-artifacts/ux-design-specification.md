---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
inputDocuments:
  - docs/prd/prd-summary.md
  - docs/prd/executive-summary.md
  - docs/project-context.md
  - src/work_data_hub/gui/eqc_query/app.py
  - src/work_data_hub/gui/eqc_query/controller.py
workflowType: 'ux-design'
lastStep: 14
project_name: 'WorkDataHub'
user_name: 'Link'
date: '2026-01-03'
---

# UX Design Specification: EQC Query GUI

**Author:** Link
**Date:** 2026-01-03
**Version:** 1.0

---

## Executive Summary

### Project Vision

EQC Query GUI is a desktop utility tool within the WorkDataHub ecosystem, enabling internal data analysts to quickly look up enterprise information via the EQC (企查查) API. The tool transforms what would be manual API calls into a streamlined, one-click experience with persistent caching to the corporate database.

**Design Philosophy:** Efficiency-first, minimal friction, professional tool aesthetic.

### Target Users

| User Type | Description | Usage Pattern |
|-----------|-------------|---------------|
| **Primary** | Internal data analysts (Link and future team members) | High-frequency daily queries, batch lookups |
| **Context** | Desktop Windows environment | Single monitor, keyboard + mouse |
| **Expertise** | Intermediate technical skill | Comfortable with data tools, expects efficiency |

**User Goals:**
- Query company information as fast as possible
- Copy results to clipboard for use in other tools
- Save verified results to database for ETL pipeline consumption
- Monitor API quota to avoid interruption

### Key Design Challenges

| ID | Challenge | Impact |
|----|-----------|--------|
| **C1** | **Efficiency-First Interface** | Every interaction must minimize clicks; users may query 50+ companies in a session |
| **C2** | **Visual Fatigue Prevention** | High-frequency use demands comfortable contrast and optional dark mode |
| **C3** | **Status Visibility** | Auth state, API quota, and operation feedback must be clear but non-intrusive |
| **C4** | **Desktop-Native Experience** | Must feel like a polished Windows application, not a web wrapper |

### Design Opportunities

| ID | Opportunity | Potential Solution |
|----|-------------|-------------------|
| **O1** | **Modern Visual Upgrade** | Fluent Design with acrylic materials, rounded corners, subtle shadows |
| **O2** | **Information Density Optimization** | Card-based results with inline action buttons |
| **O3** | **Dark Mode Support** | Native theme switching for extended use comfort |
| **O4** | **Keyboard Shortcuts** | Power user efficiency (Enter to search, Ctrl+C to copy, etc.) |

### Technology Strategy

**Dual-Version Approach:**

| Version | Framework | Purpose | Location |
|---------|-----------|---------|----------|
| **Tkinter (Optimized)** | Tkinter + ttk | Universal compatibility, minimal dependencies | `gui/eqc_query/` |
| **Fluent (Redesign)** | PyQt-Fluent-Widgets | Modern UX, dark mode, polished experience | `gui/eqc_query_fluent/` |

**Recommended Design System:** Microsoft Fluent Design
- Native Windows aesthetic
- Built-in dark/light mode support
- Rich component library (PyQt-Fluent-Widgets)
- Production-ready with active community

---

## Core User Experience

### Defining Experience

The core experience of EQC Query GUI is a **rapid query-copy-continue loop**:

1. User types company name
2. User presses Enter
3. Results appear instantly
4. User copies Company ID with one click
5. User continues to next query

**Core Metric:** Time from query input to copied result < 3 seconds

### Platform Strategy

| Dimension | Decision | Rationale |
|-----------|----------|-----------|
| Platform | Windows Desktop Only | Fixed target environment |
| Input Mode | Keyboard-First | Professional efficiency |
| Offline | Token persistence for auto-login | Minimize authentication friction |
| Window Mode | Single instance | Utility tool pattern |

### Effortless Interactions

| Interaction | Design Goal |
|-------------|-------------|
| Authentication | Auto-login with persisted token, zero user action |
| Search Submission | Enter key triggers search, focus stays in input |
| Result Copy | Single click with immediate Toast feedback |
| Next Query | Input auto-clears after copy, focus returns |
| Theme | Follows system preference or one-click toggle |

### Critical Success Moments

1. **App Launch** - Under 1 second to usable state
2. **Auto-Login** - "Already logged in" visible immediately
3. **Search Response** - Results appear without loading spinner feel
4. **Information Clarity** - Company ID visually prominent
5. **Copy Confirmation** - Toast notification confirms success
6. **Query Loop** - Seamless transition to next query

### Experience Principles

| ID | Principle | Design Implication |
|----|-----------|-------------------|
| **P1** | Keyboard is King | All core actions accessible via keyboard shortcuts |
| **P2** | Instant Feedback | Every action produces visible response |
| **P3** | Information Hierarchy | Company ID has highest visual weight |
| **P4** | Zero Interruption | Errors don't block; warnings are inline |
| **P5** | Professional Aesthetic | Fluent Design, restrained colors, polished details |

---

## Desired Emotional Response

### Primary Emotional Goals

| Emotion | Description | Design Trigger |
|---------|-------------|----------------|
| **Competent** | "I'm getting things done efficiently" | Fast response times, keyboard shortcuts |
| **Confident** | "I trust this tool's results" | Clear status indicators, data validation |
| **Calm** | "This tool doesn't stress me out" | Clean visuals, no jarring animations |

### Emotional Journey Mapping

```
User Journey Emotional States:
─────────────────────────────────────────────────────────────
Launch ──▶ Auto-Login ──▶ First Query ──▶ Result ──▶ Copy ──▶ Continue
  😌         😊           🎯          ✅        👍        🔄
Relief    Pleasant     Focused     Satisfied  Confirmed  Efficient
 (fast)  (no action)   (typing)    (found!)   (copied!)  (next one)
─────────────────────────────────────────────────────────────
```

### Micro-Emotions

| State | Target | Design Approach |
|-------|--------|-----------------|
| Confidence vs. Confusion | Confidence | Clear labels, obvious actions |
| Trust vs. Skepticism | Trust | Show data sources, confidence scores |
| Accomplishment vs. Frustration | Accomplishment | Visual success states, progress feedback |

### Emotional Design Principles

1. **Reduce Cognitive Load** - Fewer decisions = less stress
2. **Celebrate Success Quietly** - Toast notifications, not modal dialogs
3. **Handle Errors Gracefully** - Inline messages, not blocking popups
4. **Maintain Flow State** - Never break the query rhythm

---

## UX Pattern Analysis & Inspiration

### Inspiring Products Analysis

| Product | What They Do Well | Applicable Pattern |
|---------|------------------|-------------------|
| **Windows Terminal** | Fluent Design, dark mode, tabs | Visual style, theme system |
| **VS Code Command Palette** | Keyboard-first, instant search | Search interaction pattern |
| **Raycast (macOS)** | Lightning fast, minimal UI | Speed and efficiency focus |
| **Notion** | Clean typography, card layouts | Information presentation |

### Transferable UX Patterns

**Navigation Patterns:**
- Single-page utility (no navigation needed)
- Keyboard shortcuts for all actions

**Interaction Patterns:**
- Search-as-you-type with debounce
- Enter to submit, Escape to clear
- Inline action buttons on hover

**Visual Patterns:**
- Card-based result display
- Semantic color coding (success/error)
- Toast notifications for feedback

### Anti-Patterns to Avoid

| Anti-Pattern | Why to Avoid |
|--------------|--------------|
| Modal dialogs for errors | Breaks flow, requires extra click |
| Loading spinners > 200ms | Creates perception of slowness |
| Confirmation dialogs for copy | Unnecessary friction |
| Auto-hiding status messages | User might miss feedback |

### Design Inspiration Strategy

**Adopt:**
- Fluent Design visual language
- Toast notification pattern
- Keyboard-first interaction model

**Adapt:**
- VS Code's command palette → simplified search bar
- Windows Terminal's theme system → light/dark toggle

**Avoid:**
- Complex navigation structures
- Wizard-style multi-step flows
- Heavy animations that slow perception

---

## Design System Foundation

### Design System Choice

**Primary:** Microsoft Fluent Design 2 via PyQt-Fluent-Widgets

**Rationale:**
1. Native Windows aesthetic matches target environment
2. Built-in dark/light mode with system preference detection
3. Rich component library (buttons, inputs, cards, toasts)
4. Active maintenance and community support
5. PyQt5/6 provides robust desktop application foundation

### Implementation Approach

```
PyQt-Fluent-Widgets Component Mapping:
─────────────────────────────────────────────────────────
Current Tkinter          →    Fluent Widget
─────────────────────────────────────────────────────────
tk.Entry                 →    SearchLineEdit
tk.Button                →    PrimaryPushButton / PushButton
tk.Text                  →    TextEdit / CardWidget
tk.Radiobutton           →    RadioButton
tk.Label                 →    BodyLabel / SubtitleLabel
tk.Frame (card)          →    CardWidget
messagebox               →    InfoBar / StateToolTip
─────────────────────────────────────────────────────────
```

### Customization Strategy

| Element | Customization |
|---------|---------------|
| Primary Color | Ping An Orange (#FF6400) as accent |
| Typography | System default (Segoe UI on Windows) |
| Spacing | 8px base unit grid |
| Border Radius | Fluent default (4px) |
| Shadows | Fluent elevation system |

---

## Visual Design Foundation

### Color System

#### Light Theme

| Token | Hex | Usage |
|-------|-----|-------|
| `--primary` | `#FF6400` | Primary buttons, highlights, brand |
| `--primary-hover` | `#E65C00` | Button hover state |
| `--bg-window` | `#F5F5F5` | Window background |
| `--bg-card` | `#FFFFFF` | Card surfaces |
| `--text-primary` | `#1F1F1F` | Main text |
| `--text-secondary` | `#616161` | Secondary text |
| `--border` | `#E0E0E0` | Borders, dividers |
| `--success` | `#0F7B0F` | Success states |
| `--error` | `#C42B1C` | Error states |
| `--warning` | `#9D5D00` | Warning states |

#### Dark Theme

| Token | Hex | Usage |
|-------|-----|-------|
| `--primary` | `#FF8533` | Primary (lighter for dark bg) |
| `--bg-window` | `#202020` | Window background |
| `--bg-card` | `#2D2D2D` | Card surfaces |
| `--text-primary` | `#FFFFFF` | Main text |
| `--text-secondary` | `#A0A0A0` | Secondary text |
| `--border` | `#404040` | Borders, dividers |

### Typography System

| Level | Font | Size | Weight | Usage |
|-------|------|------|--------|-------|
| H1 | Segoe UI | 20px | Semibold | Window title |
| H2 | Segoe UI | 16px | Semibold | Section headers |
| Body | Segoe UI | 14px | Regular | Primary content |
| Caption | Segoe UI | 12px | Regular | Secondary info, status |
| Mono | Consolas | 14px | Regular | Company ID, codes |

### Spacing & Layout Foundation

**Base Unit:** 8px

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | 4px | Tight spacing |
| `--space-sm` | 8px | Default element gap |
| `--space-md` | 16px | Section padding |
| `--space-lg` | 24px | Card padding |
| `--space-xl` | 32px | Major section gaps |

**Layout Grid:**
- Window padding: 24px
- Card gap: 16px
- Form element gap: 12px

### Accessibility Considerations

| Requirement | Implementation |
|-------------|----------------|
| Contrast Ratio | Minimum 4.5:1 for text |
| Focus Indicators | Visible focus ring on all interactive elements |
| Keyboard Navigation | Tab order follows visual hierarchy |
| Screen Reader | Proper ARIA labels on buttons |

---

## User Interface Specification

### Window Layout

```
┌─────────────────────────────────────────────────────────────┐
│  ┌─ Header Bar ──────────────────────────────────────────┐  │
│  │ 🔍 EQC 快速查询                    [☀️/🌙] [⚙️]      │  │
│  │    企业数据一键检索                ● 已登录  8/10    │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌─ Search Card ──────────────────────────────────────────┐  │
│  │                                                         │  │
│  │   ◉ 企业名称    ○ Company ID                           │  │
│  │                                                         │  │
│  │   🔍 [____________________________________] [查询]     │  │
│  │                                                         │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌─ Result Card ──────────────────────────────────────────┐  │
│  │                                                         │  │
│  │   ✅ 查询成功                                          │  │
│  │                                                         │  │
│  │   ┌─ Info Row ──────────────────────────────────────┐  │  │
│  │   │ 公司全称                                         │  │
│  │   │ 深圳市平安银行股份有限公司              [📋]     │  │
│  │   └──────────────────────────────────────────────────┘  │  │
│  │                                                         │  │
│  │   ┌─ Info Row (Highlighted) ────────────────────────┐  │  │
│  │   │ Company ID                                       │  │
│  │   │ 12345678                                 [📋]    │  │
│  │   └──────────────────────────────────────────────────┘  │  │
│  │                                                         │  │
│  │   ┌─ Info Row ──────────────────────────────────────┐  │  │
│  │   │ 统一信用代码                                     │  │
│  │   │ 91440300XXXXXXXXXX                       [📋]    │  │
│  │   └──────────────────────────────────────────────────┘  │  │
│  │                                                         │  │
│  │   置信度: 1.00  |  匹配类型: 全称精确匹配              │  │
│  │                                                         │  │
│  │   ┌────────────────────────────────────────────────┐   │  │
│  │   │         [💾 保存到数据库]                       │   │  │
│  │   └────────────────────────────────────────────────┘   │  │
│  │                                                         │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### Component Specifications

#### Header Bar

| Element | Specification |
|---------|---------------|
| Title | H1, Primary color |
| Subtitle | Caption, Secondary color |
| Theme Toggle | IconButton, sun/moon icon |
| Settings | IconButton, gear icon |
| Auth Status | Dot indicator + text |
| Quota Badge | Pill badge "8/10" |

#### Search Card

| Element | Specification |
|---------|---------------|
| Mode Selector | RadioButton group, horizontal |
| Search Input | SearchLineEdit with icon |
| Search Button | PrimaryPushButton |
| Placeholder | "输入企业名称或关键词..." |

#### Result Card

| Element | Specification |
|---------|---------------|
| Status Banner | InfoBar (success/error variant) |
| Info Rows | Label + Value + CopyButton |
| Company ID | Mono font, Primary color, larger size |
| Copy Button | TransparentToolButton with icon |
| Save Button | PrimaryPushButton, full width |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Submit search |
| `Escape` | Clear search input |
| `Ctrl+1` | Copy Company ID |
| `Ctrl+2` | Copy Company Name |
| `Ctrl+S` | Save to database |
| `Ctrl+L` | Focus search input |
| `Ctrl+D` | Toggle dark mode |

### Interaction States

#### Search Button States

| State | Visual |
|-------|--------|
| Default | Primary color, "查询" |
| Hover | Darker primary |
| Loading | Spinner + "查询中..." |
| Disabled | Grayed out |

#### Copy Button States

| State | Visual |
|-------|--------|
| Default | Transparent with icon |
| Hover | Subtle background |
| Clicked | Checkmark icon + "已复制" toast |

### Toast Notifications

| Type | Duration | Position |
|------|----------|----------|
| Success | 2s | Bottom-right |
| Error | 4s | Bottom-right |
| Info | 3s | Bottom-right |

**Examples:**
- "已复制 Company ID"
- "已保存至数据库"
- "查询失败: API 配额已用完"

---

## Responsive Behavior

### Window Sizing

| Size | Dimensions | Behavior |
|------|------------|----------|
| Minimum | 500 x 600 | All elements visible |
| Default | 600 x 720 | Optimal spacing |
| Maximum | No limit | Content stays centered |

### Resize Behavior

- Cards stretch horizontally
- Result card expands vertically if needed
- Minimum widths prevent text truncation

---

## Implementation Roadmap

### Phase 1: Tkinter Optimization (Current Version)

**Scope:** Improve existing Tkinter version without framework change

| Task | Priority |
|------|----------|
| Add Toast notifications (using toplevel) | P0 |
| Improve color contrast | P0 |
| Add keyboard shortcuts | P1 |
| Refine spacing and typography | P1 |
| Add simple theme toggle (light/dark) | P2 |

### Phase 2: Fluent Version (New Development)

**Scope:** Full redesign using PyQt-Fluent-Widgets

| Task | Priority |
|------|----------|
| Set up PyQt + Fluent Widgets environment | P0 |
| Create window structure with FluentWindow | P0 |
| Implement Search Card with SearchLineEdit | P0 |
| Implement Result Card with CardWidget | P0 |
| Add theme support (system preference) | P1 |
| Add Toast notifications (InfoBar) | P1 |
| Implement keyboard shortcuts | P1 |
| Add settings panel | P2 |
| Add QR code display in-app | P2 |

### Dependency Requirements

```toml
# For Fluent version (pyproject.toml)
[project.optional-dependencies]
gui-fluent = [
    "PyQt5>=5.15.0",
    "PyQt-Fluent-Widgets>=1.4.0",
]
```

---

## Appendix

### File Structure

```
src/work_data_hub/gui/
├── eqc_query/                 # Tkinter version (existing)
│   ├── __init__.py
│   ├── app.py                 # Main application
│   └── controller.py          # Business logic
│
└── eqc_query_fluent/          # Fluent version (new)
    ├── __init__.py
    ├── app.py                 # FluentWindow application
    ├── views/
    │   ├── __init__.py
    │   ├── search_card.py     # Search interface
    │   └── result_card.py     # Result display
    ├── components/
    │   ├── __init__.py
    │   └── copy_row.py        # Copyable info row
    └── controller.py          # Shared with Tkinter (reuse)
```

### Design Assets

- Color theme HTML visualizer: `docs/ux-color-themes.html` (to be generated)
- Design direction mockups: `docs/ux-design-directions.html` (to be generated)

### References

- [PyQt-Fluent-Widgets Documentation](https://qfluentwidgets.com/)
- [Microsoft Fluent Design System](https://fluent2.microsoft.design/)
- [Windows 11 Design Principles](https://docs.microsoft.com/en-us/windows/apps/design/)

---

**Document Status:** ✅ Complete
**Next Steps:** Implementation Phase 1 (Tkinter Optimization) or Phase 2 (Fluent Development)
