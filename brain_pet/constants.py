from __future__ import annotations

BRAIN_REGIONS = {
    "PFC_LEFT":   "pfc_left",
    "PFC_RIGHT":  "pfc_right",
    "PARIETAL":   "parietal",
    "BROCA":      "broca",
    "TEMPORAL":   "temporal",
    "OCCIPITAL":  "occipital",
    "LIMBIC":     "limbic",
    "CEREBELLUM": "cerebellum",
    "BRAINSTEM":  "brainstem",
}

ALL_REGION_IDS = list(BRAIN_REGIONS.values())

# Characteristic hue per region — used as fallback / reference color
REGION_COLORS: dict[str, str] = {
    'pfc_left':   '#3498DB',
    'pfc_right':  '#3498DB',
    'parietal':   '#17A589',
    'broca':      '#1ABC9C',
    'temporal':   '#D68910',
    'occipital':  '#CA6F1E',
    'limbic':     '#C0392B',
    'cerebellum': '#27AE60',
    'brainstem':  '#922B21',
}

THRESHOLDS = {
    "FOCUS_MINUTES": 20,
    "SHORT_REST_MINUTES": 5,
    "DEEP_AWAY_MINUTES": 30,
    "FLOW_MINUTES": 45,
    "OVERLOAD_WINDOWS": 10,
    "OVERLOAD_SWITCHES": 15,
    "VIDEO_CONFIRM_SECONDS": 10,
    "PROCRASTINATION_SWITCHES": 10,
    "PROCRASTINATION_WINDOW_MIN": 30,
}

TIME_WINDOWS = {
    "MORNING_START": 6,
    "MORNING_END": 9,
    "PEAK_START": 9,
    "PEAK_END": 12,
    "AFTERNOON_DIP_START": 12,
    "AFTERNOON_DIP_END": 14,
    "AFTERNOON_START": 14,
    "AFTERNOON_END": 17,
    "EVENING_START": 17,
    "EVENING_END": 19,
    "NIGHT_EARLY_START": 19,
    "NIGHT_EARLY_END": 22,
    "NIGHT_START": 22,
    "NIGHT_END": 24,
}

WINDOW_SIZES = {
    "S": 220,
    "M": 290,
    "L": 360,
}

# Manual state IDs (user-triggered, override auto-detection)
MANUAL_STATES = frozenset({'EXERCISE', 'EATING', 'SLEEPING', 'WALKING', 'CREATIVE'})

APP_CATEGORIES: dict[str, list[str]] = {
    'WORK': [
        'code', 'cursor', 'vscode', 'webstorm', 'idea', 'xcode', 'sublime',
        'word', 'excel', 'powerpoint', 'notion', 'obsidian', 'terminal',
        'windowsterminal', 'cmd', 'powershell', 'vim', 'nvim', 'figma', 'sketch',
        'claude', 'chatgpt',
        # Additional productivity / design tools
        'postman', 'insomnia', 'tableplus', 'dbeaver', 'datagrip',
        'sourcetree', 'gitkraken', 'fork', 'tower',
        'xmind', 'miro', 'zeplin', 'invision',
    ],
    'VIDEO': ['vlc', 'mpv', 'potplayer', 'plex', 'infuse', 'kmplayer', 'mpc-hc'],
    'BROWSER_VIDEO': ['youtube', 'netflix', 'bilibili', 'twitch', 'iqiyi', 'youku',
                      'primevideo', 'disneyplus', 'hulu', 'hbomax', 'tiktok', 'douyin'],
    'MUSIC': ['spotify', 'music', 'foobar', 'netease', 'qqmusic', 'kugou', 'kuwo'],
    'COMMUNICATION': ['zoom', 'teams', 'slack', 'discord', 'skype', 'wechat', 'feishu',
                      'telegram', 'lark', '钉钉', 'dingtalk', 'qq'],
    'SOCIAL': ['twitter', 'instagram', 'weibo', 'xiaohongshu', 'reddit', 'facebook',
               'snapchat', 'pinterest'],
    'GAME': [
        'steam', 'epicgameslauncher', 'gog', 'origin', 'battlenet',
        'minecraft', 'leagueoflegends', 'valorant', 'csgo', 'cs2', 'dota2',
        'overwatch', 'genshinimpact',
    ],
}

IDE_PROCESSES = [
    'code', 'cursor', 'webstorm', 'idea', 'devenv', 'rider',
    'pycharm', 'clion', 'goland', 'rubymine', 'phpstorm', 'xcode',
    'androidstudio', 'eclipse', 'netbeans', 'emacs', 'neovim',
]

WRITING_APPS = ['word', 'notion', 'obsidian', 'typora', 'logseq', 'bear', 'ulysses',
                'scrivener', 'marktext', 'joplin']

# AI assistant apps — detected by process name or window title
AI_PROCESSES = ['claude', 'chatgpt', 'cursor']

AI_TITLE_KEYWORDS = [
    'claude.ai', 'chatgpt.com', 'chat.openai', 'gemini',
    'claude', 'copilot', 'perplexity', 'poe.com',
    'character.ai', 'you.com',
]

# Browser tab title keywords that indicate work/productivity web tools.
# These are plain substring matches (case-insensitive) against the full title string,
# so they should be distinctive enough not to false-positive on common words.
WORK_TITLE_KEYWORDS: list[str] = [
    # Code hosting & review
    'github.com', 'gitlab.com', 'bitbucket.org',
    # Issue tracking / project management
    'jira', 'linear.app', 'asana.com', 'trello.com', 'clickup.com',
    'notion.so', 'basecamp.com', 'monday.com',
    # Docs / wikis
    'confluence', 'docs.google.com', 'sheets.google.com', 'slides.google.com',
    'sharepoint', 'onenote',
    # Design / prototyping
    'figma.com', 'zeplin.io', 'invisionapp.com',
    # CI/CD / DevOps
    'jenkins', 'circleci.com', 'travis-ci', 'github actions',
    'vercel.com', 'netlify.com', 'heroku',
    # Local dev (localhost / loopback)
    'localhost', '127.0.0.1',
    # Q&A / reference
    'stackoverflow.com', 'developer.mozilla.org',
    # Communication (web versions)
    'mail.google.com', 'outlook.live.com',
]

GAME_PROCESSES: list[str] = [
    # Launchers
    'steam', 'steamwebhelper', 'epicgameslauncher', 'gog', 'gogalaxy',
    'origin', 'eadesktop', 'battlenet', 'ubisoft', 'upc', 'riotclient',
    'xboxapp', 'gamepass',
    # Popular game executables (lowercase, no .exe)
    'minecraft', 'javaw',       # Minecraft Java
    'leagueoflegends', 'league of legends',
    'valorant', 'valorant-win64-shipping',
    'csgo', 'cs2',
    'dota2',
    'overwatch', 'overwatch2',
    'genshinimpact', 'yuanshen',
    'fortnite', 'fortniteclient-win64-shipping',
    'apexlegends', 'r5apex',
    'pubg', 'tslgame',
    'rainbowsix', 'rainbowsixgame',
    'rocketleague',
    'hearthstone',
    'worldofwarcraft', 'wow',
    'starcraft2', 'sc2',
    'diablo4', 'd4',
    'cyberpunk2077',
    'eldenring', 'sekiro', 'darksouls',
    'gtav', 'gta5',
    'rdr2', 'rdr',
    'thesims4', 'sims4',
    '2kgame', 'nba2k',
    'fifa', 'eafc',
    'unity',   # Unity editor can also open games
    'unreal',  # Unreal Editor
]

GAME_TITLE_KEYWORDS: list[str] = [
    'steam', '游戏', 'game', 'gaming',
    # Common game title suffixes
    '- steam', 'powered by steam',
]

# Window class names that reliably identify game windows (lowercase)
GAME_WINDOW_CLASSES: list[str] = [
    'SDL_app',           # SDL2-based games
    'sdl_app',
    'unrealwindow',      # Unreal Engine
    'GLFW30',            # GLFW (OpenGL/Vulkan games)
    'glfw30',
    'allegro',           # Allegro game library
    'gameoverlayuiapp',  # Steam overlay
    'd3dwindow',
    'chromaSDK',         # Razer Chroma (gaming peripherals)
    'FrostEngine',       # EA Frostbite
]

# Entertainment categories for mixed-state detection
ENTERTAINMENT_CATEGORIES = frozenset({'VIDEO', 'BROWSER_VIDEO', 'SOCIAL', 'GAME', 'MUSIC'})
