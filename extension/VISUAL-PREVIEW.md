# 🎨 Extension Visual Preview - New Design

## Full Extension Layout

```
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   🍊 openFOODfacts              ✨ AI Search            ║
║                                                           ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  ┌─────────────────────────────────────────────────────┐ ║
║  │ 🔍  Ask me anything about food...          Search   │ ║
║  └─────────────────────────────────────────────────────┘ ║
║  💡 Try: "high protein vegan snack" or "céréales bio"    ║
║                                                           ║
║  Quick searches:                                          ║
║  ┌──────────────────┐ ┌──────────────────┐              ║
║  │ 🥗 high protein  │ │ 🥣 low sugar     │              ║
║  └──────────────────┘ └──────────────────┘              ║
║  ┌──────────────────┐ ┌──────────────────────────────┐  ║
║  │ 🌱 vegan         │ │ 🇫🇷 céréales faibles en sucre │  ║
║  └──────────────────┘ └──────────────────────────────┘  ║
║                                                           ║
╠═══════════════════════════════════════════════════════════╣
║  ┌─────────────────────────────────────────────────────┐ ║
║  │ 🧠 Understanding your query                          │ ║
║  │                                                       │ ║
║  │ • Category: snacks                                   │ ║
║  │ • Tags: vegan, low-sodium                            │ ║
║  │ • Constraints: protein ≥ 10g, calories ≤ 200        │ ║
║  │ • Language: en                                       │ ║
║  └─────────────────────────────────────────────────────┘ ║
║                                                           ║
║  📦 Found products                                        ║
║                                                           ║
║  ┌─────────────────────────────────────────────────────┐ ║
║  │  ┌───┐                                               │ ║
║  │  │ 🖼 │  Organic Protein Bar                         │ ║
║  │  │   │  [A↗] plant-based-foods                      │ ║
║  │  └───┘  ✓ High protein, Good nutritional quality    │ ║
║  └─────────────────────────────────────────────────────┘ ║
║                                                           ║
║  ┌─────────────────────────────────────────────────────┐ ║
║  │  ┌───┐                                               │ ║
║  │  │ 🖼 │  Vegan Energy Bites                          │ ║
║  │  │   │  [B↗] snacks                                 │ ║
║  │  └───┘  ✓ High fiber, Low sugar                     │ ║
║  └─────────────────────────────────────────────────────┘ ║
║                                                           ║
║  ┌─────────────────────────────────────────────────────┐ ║
║  │  ┌───┐                                               │ ║
║  │  │ 🖼 │  Plant-Based Snack Mix                       │ ║
║  │  │   │  [A↗] dried-fruits                           │ ║
║  │  └───┘  ✓ Minimally processed, High protein         │ ║
║  └─────────────────────────────────────────────────────┘ ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
```

## Color Palette Reference

### Primary Colors
```
🟠 OFF Orange     #ff8714  ████████
🟤 OFF Brown      #341100  ████████
🟨 Light Orange   #ffb85c  ████████
🟧 Dark Orange    #e67300  ████████
```

### NutriScore Colors
```
🟢 Grade A    #038141  ████████  (Excellent)
🟢 Grade B    #85bb2f  ████████  (Good)
🟡 Grade C    #fecb02  ████████  (Fair)
🟠 Grade D    #ee8100  ████████  (Poor)
🔴 Grade E    #e63e11  ████████  (Bad)
```

### UI Elements
```
⚪ White       #ffffff  ████████  (Background)
⬜ Light Gray  #f8f9fa  ████████  (Cards)
◽ Border      #e8e8e8  ████████  (Lines)
⬛ Text        #333333  ████████  (Primary)
◾ Muted       #666666  ████████  (Secondary)
```

## Component Breakdown

### 1. Header (OFF Branding)
```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  🍊 openFOODfacts              ✨ AI Search       │
│  ─┬─ ──┬── ───┬──                                  │
│   │    │      │                                     │
│   │    │      └─ "facts" in black                  │
│   │    └──────── "FOOD" in orange box              │
│   └───────────── "open" in black                   │
│                                                     │
│                  ┌─────────────┐                   │
│                  │ ✨ AI Search │ ← Animated badge │
│                  └─────────────┘                   │
└─────────────────────────────────────────────────────┘
```

### 2. AI Search Bar (OFF Style)
```
┌─────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────────┐   │
│  │ 🔍  [Ask me anything about food...]  Search │   │
│  │  ↑                                      ↑    │   │
│  │  │                                      │    │   │
│  │  Icon                            Dark button│   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Focus state: Orange glow around entire container  │
│                                                     │
│  💡 Try: "high protein vegan snack" or "céréales"  │
│      ↑                                              │
│      Helpful hint                                   │
└─────────────────────────────────────────────────────┘
```

### 3. Quick Search Tags
```
┌─────────────────────────────────────────────────────┐
│  QUICK SEARCHES:                                    │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐               │
│  │ 🥗 high      │  │ 🥣 low       │               │
│  │   protein    │  │   sugar      │               │
│  └──────────────┘  └──────────────┘               │
│         ↑                 ↑                         │
│    Emoji icon      Rounded pill                    │
│                                                     │
│  Hover effect: Lift + Orange accent                │
└─────────────────────────────────────────────────────┘
```

### 4. Query Interpretation Panel
```
┌─────────────────────────────────────────────────────┐
│ ┃                                                    │
│ ┃ 🧠 Understanding your query                       │
│ ┃                                                    │
│ ┃ • Category: snacks                                │
│ ┃ • Tags: vegan, low-sodium                         │
│ ┃ • Constraints: protein ≥ 10g, calories ≤ 200     │
│ ┃ • Language: en                                    │
│ ┃                                                    │
│ └ Orange left border                                │
│   Orange gradient background                        │
└─────────────────────────────────────────────────────┘
```

### 5. Product Card (Enhanced)
```
┌─────────────────────────────────────────────────────┐
│  ┌─────┐                                            │
│  │     │  Product Name Here                         │
│  │ IMG │  (Bold, 2-line ellipsis)                   │
│  │     │                                            │
│  │ 80px│  ┌───┐  plant-based                       │
│  └─────┘  │ A │  ← Gradient badge                  │
│            └───┘                                    │
│                                                     │
│            ✓ High protein, Low sugar                │
│            ↑ Checkmark indicator                    │
│                                                     │
│  Hover: Orange border + lift effect + shadow       │
└─────────────────────────────────────────────────────┘
```

### 6. Loading State
```
┌─────────────────────────────────────────────────────┐
│                                                     │
│                    ⟳                                │
│                  Orange                             │
│                  spinner                            │
│                                                     │
│           Analyzing your request...                 │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 7. Empty State
```
┌─────────────────────────────────────────────────────┐
│                                                     │
│                    🔍                               │
│                  (faded)                            │
│                                                     │
│        No products found matching your criteria     │
│                                                     │
│     Try a different search or broader terms         │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Animation Effects

### ✨ AI Badge Sparkle
```
Frame 1:  ✨ (Normal)
Frame 2:  ✦  (Slightly larger + faded)
Frame 3:  ✨ (Normal)
```
*2-second loop, smooth pulse*

### 🔍 Search Bar Focus
```
Normal:   ┌────────┐  Gray border
          │        │
          └────────┘

Focused:  ┌────────┐  Orange border + glow
          │ ◉ ◉ ◉  │  (Shadow halo)
          └────────┘
```

### 🃏 Product Card Hover
```
Rest:     ┌────────┐  
          │        │  Y position: 0
          └────────┘  Shadow: Small

Hover:    ┌────────┐  
          │  ↑↑↑   │  Y position: -2px
          └────────┘  Shadow: Large + Orange border
```

## Typography Scale

```
20px  🔸 Logo text (openFOODfacts)
16px  🔹 Section headers (📦 Found products)
14px  ⚫ Body text (Input, product names)
13px  ⚪ Labels (Results, interpretation titles)
12px  ◽ Small text (Example tags, summaries)
11px  ◾ Tiny text (Hints, NutriScore labels)
10px  ▫️ Micro text (Category badges)
```

## Spacing System

```
 4px  ▫️  Tight      (Badge padding)
 8px  ◽  Compact    (Tag gaps)
12px  ⚪  Normal     (Card gaps)
16px  ⚫  Medium     (Section padding)
20px  🔹  Large      (Main padding)
24px  🔸  XLarge     (Search section top)
```

## Usage Example

1. **Initial State**: Clean OFF-branded header + AI search bar
2. **User Types**: "high protein vegan snack"
3. **Submit**: Orange spinner appears with "Analyzing..."
4. **Interpretation**: 🧠 Panel shows parsed query
5. **Results**: Product cards slide in with gradient badges
6. **Hover**: Cards lift with orange highlight
7. **Click**: Opens product on OpenFoodFacts.org

---

**🎨 Design Philosophy:**
- **Authentic** - True to OFF brand identity
- **Modern** - Contemporary UI patterns
- **Accessible** - High contrast, clear hierarchy
- **Delightful** - Smooth animations, visual feedback
- **Professional** - Production-ready polish

**✅ Ready for demonstration!**
