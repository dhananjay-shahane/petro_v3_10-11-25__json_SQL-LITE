# Design Guidelines: Dockable Window Manager Application

## Design Approach
**System-Based Approach**: Professional productivity tool design inspired by modern IDEs (VS Code, Figma) and dock managers, utilizing established UI patterns for complex window management while maintaining the teal/cyan aesthetic from the reference design.

## Color Palette

### Dark Mode (Primary)
- **Background Base**: 220 15% 12% (deep slate background)
- **Surface Elevated**: 220 15% 16% (panel backgrounds)
- **Border/Divider**: 220 10% 25% (subtle panel borders)
- **Primary (Teal/Cyan)**: 180 65% 45% (window headers, active states, accents)
- **Primary Hover**: 180 65% 55%
- **Text Primary**: 0 0% 95%
- **Text Secondary**: 220 10% 70%
- **Text Muted**: 220 10% 50%

### Accent Colors
- **Success**: 142 70% 45% (active indicators)
- **Warning**: 38 92% 50% (alerts)
- **Error**: 0 70% 50% (critical states)
- **Info**: 210 80% 55% (informational)

## Typography
- **Font Family**: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif
- **Monospace**: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace (for data/code displays)

### Type Scale
- **Window Titles**: 14px, font-semibold (panel headers)
- **Tab Labels**: 13px, font-medium (tab navigation)
- **Body Text**: 13px, font-normal (content)
- **Data/Table**: 12px, font-mono (tabular data)
- **Helper Text**: 11px, font-normal, text-muted

## Layout System

### Spacing Primitives
**Consistent spacing using**: 1, 2, 3, 4, 6, 8 (Tailwind units)
- Panel padding: p-3 to p-4
- Header padding: px-3 py-2
- Tab spacing: px-3 py-1.5
- Gap between elements: gap-2 to gap-4
- Border radius: rounded (4px) for panels, rounded-sm (2px) for tabs

### Window Manager Grid
- **Minimum Panel Width**: 280px
- **Default Panel Width**: 320px-400px
- **Resize Handle**: 4px active zone, 1px visible divider
- **Floating Window**: Drop shadow lg, min-width 320px

## Component Library

### Window Pane Structure
- **Header Bar**: bg-surface, border-b, h-10
  - Drag handle (full header area)
  - Title (left-aligned, truncate)
  - Action buttons (right-aligned: minimize, maximize, close)
- **Tab Bar** (when applicable): bg-surface, h-9, border-b
  - Active tab: bg-base, border-t-2 border-primary
  - Inactive tab: hover:bg-surface-elevated
- **Content Area**: p-3 to p-4, overflow-auto
- **Resize Handles**: 1px border, hover:bg-primary/20, cursor-resize

### Navigation & Controls
- **Window Control Buttons**: 
  - Size: 24px × 24px
  - Icon size: 14px
  - Hover state: bg-white/10
  - Spacing: gap-1
- **Tab Navigation**:
  - Height: 36px
  - Active indicator: 2px top border in primary color
  - Close button on hover (× icon, 16px)
- **Toolbars**: h-8, bg-surface-elevated, border-b

### Data Display Components
- **Tree View** (Project/Wells sections):
  - Indent: pl-4 per level
  - Expand/collapse icons: 16px chevrons
  - Item height: h-7
  - Hover: bg-white/5
- **Data Grid/Table**:
  - Header: bg-surface-elevated, h-8, sticky
  - Row height: h-9
  - Zebra striping: even:bg-white/[0.02]
  - Cell padding: px-3 py-2
- **List Items**:
  - Height: h-8 to h-10
  - Hover state: bg-white/5
  - Selected: bg-primary/10, border-l-2 border-primary

### Form Elements
- **Input Fields**: h-8, bg-base, border border-divider, rounded, px-3
- **Dropdowns**: Same as inputs, with chevron-down icon
- **Checkboxes**: 16px, rounded-sm, border-2
- **Radio Buttons**: 16px, rounded-full

### Interactive States
- **Dragging**: opacity-50, cursor-grabbing
- **Docking Preview**: bg-primary/20, border-2 border-primary, dashed
- **Resize Active**: cursor changes (ew-resize, ns-resize, nwse-resize)
- **Panel Focus**: border-l-2 border-primary (subtle indicator)

## Dock Manager Behavior

### Docking Zones
- **4 Cardinal Directions**: Top, Right, Bottom, Left (full-height/width zones)
- **Center Tab Merge**: Overlay zone in panel centers
- **Preview Overlay**: 30% opacity, primary color, animated on hover

### Window States
- **Docked**: Integrated in grid layout
- **Floating**: Absolute positioned, z-index layering, draggable
- **Minimized**: Icon in taskbar/dock (bottom of screen)
- **Maximized**: Full viewport coverage

### Layout Persistence
- Save layout state to localStorage
- Include: panel positions, sizes, dock arrangement, tab orders, floating window positions

## Iconography
**Use Heroicons (outline style)** via CDN:
- Window controls: XMarkIcon, MinusIcon, Square2StackIcon
- Navigation: ChevronDownIcon, ChevronRightIcon
- Actions: Squares2X2Icon, FolderIcon, DocumentIcon
- Size: 16px standard, 20px for primary actions

## Accessibility
- **Keyboard Navigation**: Tab through panels, arrow keys for tree/list navigation
- **Focus Indicators**: ring-2 ring-primary ring-offset-2 ring-offset-base
- **ARIA Labels**: Proper labeling for all interactive elements
- **Screen Reader**: Announce panel states (docked, floating, minimized)

## Animations (Minimal, Purposeful)
- **Panel Transitions**: duration-200, ease-in-out
- **Tab Switches**: No animation (instant)
- **Resize**: Real-time, no transition
- **Floating Window Drag**: transform updates only, no transitions during drag
- **Docking**: 150ms ease-out for snap-to-grid

## Special Considerations
- **Multi-Monitor Support**: Allow floating windows to move across screens
- **Context Menus**: Right-click on headers for panel actions (float, close, etc.)
- **Splitter Behavior**: Double-click resize handles to reset to default sizes
- **Panel Templates**: Pre-configured layouts (e.g., "Data Analysis", "Well Review")