// The themes: preview.html shows them; apply.py writes the Ghostty, herdr and starship settings from them.
// Color sources: Ghostty's theme files, herdr 0.9.5's palettes (src/app/state.rs) and VS Code's Dark Modern theme.
// THEMES must stay plain JSON, except that a long string may be split into parts joined by + (apply.py joins them).
const THEMES = [
 {
  "id": "catppuccin",
  "name": "Catppuccin Mocha",
  "tag": "purplish",
  "ghostty": {
   "theme": "Catppuccin Mocha",
   "set": [
    {
     "note": "Darker pane interiors than the theme default (\"base\" #1e1e2e): the Mocha \"crust\" shade, so the " +
       "panes stand apart from the sidebars",
     "key": "background",
     "value": "#11111b"
    },
    {
     "note": "Plain text is a muted gray (Mocha overlay2) — this makes the colored elements look more vivid",
     "key": "foreground",
     "value": "#9399b2"
    },
    {
     "note": "Magenta in program output is purple (mauve); faint secondary text is overlay0",
     "key": "palette",
     "value": "5=#cba6f7"
    },
    {
     "note": null,
     "key": "palette",
     "value": "8=#6c7086"
    }
   ]
  },
  "herdr": {
   "theme": "catppuccin",
   "note": "Catppuccin Mocha shades for the sidebars and the frame (Ghostty paints the pane interiors)",
   "custom": {
    "accent": "#cba6f7",
    "panel_bg": "#1e1e2e",
    "sidebar_bg": "#181825",
    "active_row_bg": "#4a4060",
    "selection_bg": "#434657"
   }
  },
  "prompt": {
   "path": "#cba6f7",
   "branch": "#9399b2",
   "status": "#f38ba8"
  },
  "colors": {
   "background": "#11111b",
   "foreground": "#9399b2",
   "cursor": "#f5e0dc",
   "palette": [
    "#45475a",
    "#f38ba8",
    "#a6e3a1",
    "#f9e2af",
    "#89b4fa",
    "#cba6f7",
    "#94e2d5",
    "#a6adc8",
    "#6c7086",
    "#f37799",
    "#89d88b",
    "#ebd391",
    "#74a8fc",
    "#f2aede",
    "#6bd7ca",
    "#bac2de"
   ],
   "herdr": {
    "accent": "#cba6f7",
    "panel_bg": "#1e1e2e",
    "sidebar_bg": "#181825",
    "active_row_bg": "#4a4060",
    "surface0": "#313244",
    "surface_dim": "#1e1e2e",
    "overlay0": "#6c7086",
    "overlay1": "#7f849c",
    "text": "#cdd6f4",
    "subtext0": "#a6adc8",
    "green": "#a6e3a1",
    "yellow": "#f9e2af",
    "red": "#f38ba8",
    "blue": "#89b4fa",
    "teal": "#94e2d5",
    "peach": "#fab387"
   }
  }
 },
 {
  "id": "vscode",
  "name": "VS Code (Dark Modern)",
  "tag": "near-black · the VS Code terminal",
  "ghostty": {
   "theme": "Dark+",
   "set": [
    {
     "note": "The VS Code (Dark Modern) terminal: the panel background, VS Code's text color, cursor and selection; " +
       "the palette is VS Code's default terminal colors (= Dark+)",
     "key": "background",
     "value": "#181818"
    },
    {
     "note": null,
     "key": "foreground",
     "value": "#cccccc"
    },
    {
     "note": null,
     "key": "cursor-color",
     "value": "#cccccc"
    },
    {
     "note": null,
     "key": "selection-background",
     "value": "#264f78"
    }
   ]
  },
  "herdr": {
   "theme": "terminal",
   "note": "The VS Code (Dark Modern) frame: tab bar and sidebar #181818, accent in VS Code blue",
   "custom": {
    "accent": "#0078d4",
    "panel_bg": "#181818",
    "sidebar_bg": "#181818",
    "active_row_bg": "#0e4067",
    "selection_bg": "#434343",
    "surface0": "#2b2b2b",
    "surface1": "#313131",
    "surface_dim": "#2b2b2b",
    "overlay0": "#6e7681",
    "overlay1": "#9d9d9d",
    "text": "#cccccc",
    "subtext0": "#9d9d9d",
    "mauve": "#c586c0",
    "green": "#0dbc79",
    "yellow": "#cca700",
    "red": "#f14c4c",
    "blue": "#3b8eea",
    "teal": "#29b8db",
    "peach": "#ce9178"
   }
  },
  "prompt": {
   "path": "#3b8eea",
   "branch": "#9d9d9d",
   "status": "#cd3131"
  },
  "colors": {
   "background": "#181818",
   "foreground": "#cccccc",
   "cursor": "#cccccc",
   "palette": [
    "#000000",
    "#cd3131",
    "#0dbc79",
    "#e5e510",
    "#2472c8",
    "#bc3fbc",
    "#11a8cd",
    "#e5e5e5",
    "#666666",
    "#f14c4c",
    "#23d18b",
    "#f5f543",
    "#3b8eea",
    "#d670d6",
    "#29b8db",
    "#e5e5e5"
   ],
   "herdr": {
    "accent": "#0078d4",
    "panel_bg": "#181818",
    "sidebar_bg": "#181818",
    "active_row_bg": "#0e4067",
    "surface0": "#2b2b2b",
    "surface_dim": "#2b2b2b",
    "overlay0": "#6e7681",
    "overlay1": "#9d9d9d",
    "text": "#cccccc",
    "subtext0": "#9d9d9d",
    "green": "#0dbc79",
    "yellow": "#cca700",
    "red": "#f14c4c",
    "blue": "#3b8eea",
    "teal": "#29b8db",
    "peach": "#ce9178"
   }
  }
 },
 {
  "id": "vesper",
  "name": "Vesper",
  "tag": "black",
  "ghostty": {
   "theme": "Vesper",
   "set": []
  },
  "herdr": {
   "theme": "vesper",
   "custom": {
    "active_row_bg": "#534336",
    "selection_bg": "#494949"
   }
  },
  "prompt": {
   "path": "#ffc799",
   "branch": "#a0a0a0",
   "status": "#f5a191"
  },
  "colors": {
   "background": "#101010",
   "foreground": "#ffffff",
   "cursor": "#acb1ab",
   "palette": [
    "#101010",
    "#f5a191",
    "#90b99f",
    "#e6b99d",
    "#aca1cf",
    "#e29eca",
    "#ea83a5",
    "#a0a0a0",
    "#7e7e7e",
    "#ff8080",
    "#99ffe4",
    "#ffc799",
    "#b9aeda",
    "#ecaad6",
    "#f591b2",
    "#ffffff"
   ],
   "herdr": {
    "accent": "#ffc799",
    "panel_bg": "#1a1a1a",
    "sidebar_bg": "#101010",
    "active_row_bg": "#534336",
    "surface0": "#232323",
    "surface_dim": "#101010",
    "overlay0": "#5c5c5c",
    "overlay1": "#7e7e7e",
    "text": "#ffffff",
    "subtext0": "#a0a0a0",
    "green": "#99ffe4",
    "yellow": "#ffc799",
    "red": "#ff8080",
    "blue": "#b0b0b0",
    "teal": "#66ddcc",
    "peach": "#ffc799"
   }
  }
 },
 {
  "id": "github-dark",
  "name": "GitHub Dark",
  "tag": "black, slightly bluish",
  "ghostty": {
   "theme": "GitHub Dark Default",
   "set": []
  },
  "herdr": {
   "theme": "terminal",
   "custom": {
    "active_row_bg": "#223b58",
    "selection_bg": "#41464c"
   }
  },
  "prompt": {
   "path": "#58a6ff",
   "branch": "#b1bac4",
   "status": "#ff7b72"
  },
  "colors": {
   "background": "#0d1117",
   "foreground": "#e6edf3",
   "cursor": "#2f81f7",
   "palette": [
    "#484f58",
    "#ff7b72",
    "#3fb950",
    "#d29922",
    "#58a6ff",
    "#bc8cff",
    "#39c5cf",
    "#b1bac4",
    "#6e7681",
    "#ffa198",
    "#56d364",
    "#e3b341",
    "#79c0ff",
    "#d2a8ff",
    "#56d4dd",
    "#ffffff"
   ],
   "herdr": {
    "accent": "#58a6ff",
    "panel_bg": "#0d1117",
    "sidebar_bg": "#0d1117",
    "active_row_bg": "#223b58",
    "surface0": "#0d1117",
    "surface_dim": "#6e7681",
    "overlay0": "#b1bac4",
    "overlay1": "#ffffff",
    "text": "#e6edf3",
    "subtext0": "#b1bac4",
    "green": "#3fb950",
    "yellow": "#d29922",
    "red": "#ffa198",
    "blue": "#58a6ff",
    "teal": "#39c5cf",
    "peach": "#d29922"
   }
  }
 },
 {
  "id": "tokyo-night",
  "name": "Tokyo Night",
  "tag": "dark blue",
  "ghostty": {
   "theme": "TokyoNight",
   "set": []
  },
  "herdr": {
   "theme": "tokyo-night",
   "custom": {
    "active_row_bg": "#354161",
    "selection_bg": "#424558"
   }
  },
  "prompt": {
   "path": "#7aa2f7",
   "branch": "#a9b1d6",
   "status": "#f7768e"
  },
  "colors": {
   "background": "#1a1b26",
   "foreground": "#c0caf5",
   "cursor": "#c0caf5",
   "palette": [
    "#15161e",
    "#f7768e",
    "#9ece6a",
    "#e0af68",
    "#7aa2f7",
    "#bb9af7",
    "#7dcfff",
    "#a9b1d6",
    "#414868",
    "#f7768e",
    "#9ece6a",
    "#e0af68",
    "#7aa2f7",
    "#bb9af7",
    "#7dcfff",
    "#c0caf5"
   ],
   "herdr": {
    "accent": "#7aa2f7",
    "panel_bg": "#1a1b26",
    "sidebar_bg": "#1a1b26",
    "active_row_bg": "#354161",
    "surface0": "#24283b",
    "surface_dim": "#1a1b26",
    "overlay0": "#565f89",
    "overlay1": "#697196",
    "text": "#c0caf5",
    "subtext0": "#a9b1d6",
    "green": "#9ece6a",
    "yellow": "#e0af68",
    "red": "#f7768e",
    "blue": "#7aa2f7",
    "teal": "#7dcfff",
    "peach": "#ff9e64"
   }
  }
 },
 {
  "id": "kanagawa",
  "name": "Kanagawa",
  "tag": "dark, ink blue",
  "ghostty": {
   "theme": "Kanagawa Wave",
   "set": []
  },
  "herdr": {
   "theme": "kanagawa",
   "custom": {
    "active_row_bg": "#3a4259",
    "selection_bg": "#4c4b4b"
   }
  },
  "prompt": {
   "path": "#7e9cd8",
   "branch": "#c8c3aa",
   "status": "#c34043"
  },
  "colors": {
   "background": "#1f1f28",
   "foreground": "#dcd7ba",
   "cursor": "#dcd7ba",
   "palette": [
    "#090618",
    "#c34043",
    "#76946a",
    "#c0a36e",
    "#7e9cd8",
    "#957fb8",
    "#6a9589",
    "#c8c093",
    "#727169",
    "#e82424",
    "#98bb6c",
    "#e6c384",
    "#7fb4ca",
    "#938aa9",
    "#7aa89f",
    "#dcd7ba"
   ],
   "herdr": {
    "accent": "#7e9cd8",
    "panel_bg": "#1f1f28",
    "sidebar_bg": "#1f1f28",
    "active_row_bg": "#3a4259",
    "surface0": "#2a2a37",
    "surface_dim": "#1f1f28",
    "overlay0": "#727169",
    "overlay1": "#87867d",
    "text": "#dcd7ba",
    "subtext0": "#c8c3aa",
    "green": "#76946a",
    "yellow": "#c0a36e",
    "red": "#c34043",
    "blue": "#7e9cd8",
    "teal": "#7fb4ca",
    "peach": "#ffa066"
   }
  }
 },
 {
  "id": "rose-pine",
  "name": "Rosé Pine",
  "tag": "dark, mauve",
  "ghostty": {
   "theme": "Rose Pine",
   "set": []
  },
  "herdr": {
   "theme": "rose-pine",
   "custom": {
    "active_row_bg": "#493f5b",
    "selection_bg": "#494756"
   }
  },
  "prompt": {
   "path": "#c4a7e7",
   "branch": "#c8c5dc",
   "status": "#eb6f92"
  },
  "colors": {
   "background": "#191724",
   "foreground": "#e0def4",
   "cursor": "#e0def4",
   "palette": [
    "#26233a",
    "#eb6f92",
    "#31748f",
    "#f6c177",
    "#9ccfd8",
    "#c4a7e7",
    "#ebbcba",
    "#e0def4",
    "#6e6a86",
    "#eb6f92",
    "#31748f",
    "#f6c177",
    "#9ccfd8",
    "#c4a7e7",
    "#ebbcba",
    "#e0def4"
   ],
   "herdr": {
    "accent": "#c4a7e7",
    "panel_bg": "#191724",
    "sidebar_bg": "#191724",
    "active_row_bg": "#493f5b",
    "surface0": "#1f1d2e",
    "surface_dim": "#26233a",
    "overlay0": "#6e6a86",
    "overlay1": "#908caa",
    "text": "#e0def4",
    "subtext0": "#c8c5dc",
    "green": "#31748f",
    "yellow": "#f6c177",
    "red": "#eb6f92",
    "blue": "#31748f",
    "teal": "#9ccfd8",
    "peach": "#ea9a97"
   }
  }
 },
 {
  "id": "one-dark",
  "name": "One Dark",
  "tag": "dark gray · the Atom theme",
  "ghostty": {
   "theme": "Atom One Dark",
   "set": []
  },
  "herdr": {
   "theme": "one-dark",
   "custom": {
    "active_row_bg": "#334c62",
    "selection_bg": "#42474f"
   }
  },
  "prompt": {
   "path": "#61afef",
   "branch": "#969ca8",
   "status": "#e06c75"
  },
  "colors": {
   "background": "#21252b",
   "foreground": "#abb2bf",
   "cursor": "#abb2bf",
   "palette": [
    "#21252b",
    "#e06c75",
    "#98c379",
    "#e5c07b",
    "#61afef",
    "#c678dd",
    "#56b6c2",
    "#abb2bf",
    "#767676",
    "#e06c75",
    "#98c379",
    "#e5c07b",
    "#61afef",
    "#c678dd",
    "#56b6c2",
    "#abb2bf"
   ],
   "herdr": {
    "accent": "#61afef",
    "panel_bg": "#282c34",
    "sidebar_bg": "#21252b",
    "active_row_bg": "#334c62",
    "surface0": "#2c313a",
    "surface_dim": "#282c34",
    "overlay0": "#5c6370",
    "overlay1": "#737a87",
    "text": "#abb2bf",
    "subtext0": "#969ca8",
    "green": "#98c379",
    "yellow": "#e5c07b",
    "red": "#e06c75",
    "blue": "#61afef",
    "teal": "#56b6c2",
    "peach": "#d19a66"
   }
  }
 },
 {
  "id": "dracula",
  "name": "Dracula",
  "tag": "dark, purplish gray",
  "ghostty": {
   "theme": "Dracula",
   "set": []
  },
  "herdr": {
   "theme": "dracula",
   "custom": {
    "active_row_bg": "#52476d",
    "selection_bg": "#5a5b63"
   }
  },
  "prompt": {
   "path": "#bd93f9",
   "branch": "#d2d2dc",
   "status": "#ff5555"
  },
  "colors": {
   "background": "#282a36",
   "foreground": "#f8f8f2",
   "cursor": "#f8f8f2",
   "palette": [
    "#21222c",
    "#ff5555",
    "#50fa7b",
    "#f1fa8c",
    "#bd93f9",
    "#ff79c6",
    "#8be9fd",
    "#f8f8f2",
    "#6272a4",
    "#ff6e6e",
    "#69ff94",
    "#ffffa5",
    "#d6acff",
    "#ff92df",
    "#a4ffff",
    "#ffffff"
   ],
   "herdr": {
    "accent": "#bd93f9",
    "panel_bg": "#282a36",
    "sidebar_bg": "#282a36",
    "active_row_bg": "#52476d",
    "surface0": "#44475a",
    "surface_dim": "#282a36",
    "overlay0": "#6272a4",
    "overlay1": "#828cb4",
    "text": "#f8f8f2",
    "subtext0": "#d2d2dc",
    "green": "#50fa7b",
    "yellow": "#f1fa8c",
    "red": "#ff5555",
    "blue": "#8be9fd",
    "teal": "#8be9fd",
    "peach": "#ffb86c"
   }
  }
 },
 {
  "id": "gruvbox",
  "name": "Gruvbox",
  "tag": "warm, brownish",
  "ghostty": {
   "theme": "Gruvbox Dark",
   "set": []
  },
  "herdr": {
   "theme": "gruvbox",
   "custom": {
    "active_row_bg": "#594826",
    "selection_bg": "#575349"
   }
  },
  "prompt": {
   "path": "#d79921",
   "branch": "#d5c4a1",
   "status": "#cc241d"
  },
  "colors": {
   "background": "#282828",
   "foreground": "#ebdbb2",
   "cursor": "#ebdbb2",
   "palette": [
    "#282828",
    "#cc241d",
    "#98971a",
    "#d79921",
    "#458588",
    "#b16286",
    "#689d6a",
    "#a89984",
    "#928374",
    "#fb4934",
    "#b8bb26",
    "#fabd2f",
    "#83a598",
    "#d3869b",
    "#8ec07c",
    "#ebdbb2"
   ],
   "herdr": {
    "accent": "#d79921",
    "panel_bg": "#282828",
    "sidebar_bg": "#282828",
    "active_row_bg": "#594826",
    "surface0": "#3c3836",
    "surface_dim": "#282828",
    "overlay0": "#928374",
    "overlay1": "#a89984",
    "text": "#ebdbb2",
    "subtext0": "#d5c4a1",
    "green": "#b8bb26",
    "yellow": "#fabd2f",
    "red": "#fb4934",
    "blue": "#83a598",
    "teal": "#8ec07c",
    "peach": "#fe8019"
   }
  }
 },
 {
  "id": "nord",
  "name": "Nord",
  "tag": "bluish gray",
  "ghostty": {
   "theme": "Nord",
   "set": []
  },
  "herdr": {
   "theme": "nord",
   "custom": {
    "active_row_bg": "#475b68",
    "selection_bg": "#5c616b"
   }
  },
  "prompt": {
   "path": "#88c0d0",
   "branch": "#d8dee9",
   "status": "#bf616a"
  },
  "colors": {
   "background": "#2e3440",
   "foreground": "#d8dee9",
   "cursor": "#eceff4",
   "palette": [
    "#3b4252",
    "#bf616a",
    "#a3be8c",
    "#ebcb8b",
    "#81a1c1",
    "#b48ead",
    "#88c0d0",
    "#e5e9f0",
    "#596377",
    "#bf616a",
    "#a3be8c",
    "#ebcb8b",
    "#81a1c1",
    "#b48ead",
    "#8fbcbb",
    "#eceff4"
   ],
   "herdr": {
    "accent": "#88c0d0",
    "panel_bg": "#2e3440",
    "sidebar_bg": "#2e3440",
    "active_row_bg": "#475b68",
    "surface0": "#3b4252",
    "surface_dim": "#2e3440",
    "overlay0": "#4c566a",
    "overlay1": "#646e82",
    "text": "#eceff4",
    "subtext0": "#d8dee9",
    "green": "#a3be8c",
    "yellow": "#ebcb8b",
    "red": "#bf616a",
    "blue": "#81a1c1",
    "teal": "#8fbcbb",
    "peach": "#d08770"
   }
  }
 },
 {
  "id": "solarized",
  "name": "Solarized",
  "tag": "dark petrol blue",
  "ghostty": {
   "theme": "iTerm2 Solarized Dark",
   "set": []
  },
  "herdr": {
   "theme": "solarized",
   "custom": {
    "active_row_bg": "#0d4c6b",
    "selection_bg": "#294c54"
   }
  },
  "prompt": {
   "path": "#268bd2",
   "branch": "#839496",
   "status": "#dc322f"
  },
  "colors": {
   "background": "#002b36",
   "foreground": "#839496",
   "cursor": "#839496",
   "palette": [
    "#073642",
    "#dc322f",
    "#859900",
    "#b58900",
    "#268bd2",
    "#d33682",
    "#2aa198",
    "#eee8d5",
    "#335e69",
    "#cb4b16",
    "#586e75",
    "#657b83",
    "#839496",
    "#6c71c4",
    "#93a1a1",
    "#fdf6e3"
   ],
   "herdr": {
    "accent": "#268bd2",
    "panel_bg": "#002b36",
    "sidebar_bg": "#002b36",
    "active_row_bg": "#0d4c6b",
    "surface0": "#073642",
    "surface_dim": "#002b36",
    "overlay0": "#586e75",
    "overlay1": "#657b83",
    "text": "#93a1a1",
    "subtext0": "#839496",
    "green": "#859900",
    "yellow": "#b58900",
    "red": "#dc322f",
    "blue": "#268bd2",
    "teal": "#2aa198",
    "peach": "#cb4b16"
   }
  }
 }
];
