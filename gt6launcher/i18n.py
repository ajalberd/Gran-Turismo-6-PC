"""Internationalization and localization support for GT6 Launcher."""
from __future__ import annotations

from typing import Optional

from .i18n_fr import STRINGS as _FR
from .i18n_ja import STRINGS as _JA

# List of supported languages: (code, display_label, english_name)
LANGUAGES: list[tuple[str, str, str]] = [
    ("en", "🇬🇧 English", "English"),
    ("zh_CN", "🇨🇳 简体中文", "Simplified Chinese"),
    ("fr", "🇫🇷 Français", "French"),
    ("ja", "🇯🇵 日本語", "Japanese"),
]

_CURRENT_LANG: str = "en"


def get_current_language() -> str:
    return _CURRENT_LANG


def set_current_language(code: str) -> None:
    global _CURRENT_LANG
    valid_codes = [c for c, _, _ in LANGUAGES]
    if code in valid_codes:
        _CURRENT_LANG = code
    else:
        _CURRENT_LANG = "en"


def next_language(current_code: str) -> tuple[str, str]:
    """Cycles to the next available language, returning (code, display_label)."""
    codes = [c for c, _, _ in LANGUAGES]
    try:
        idx = (codes.index(current_code) + 1) % len(codes)
    except ValueError:
        idx = 0
    return LANGUAGES[idx][0], LANGUAGES[idx][1]


def get_switch_button_label(current_code: str) -> str:
    """Returns the label of the NEXT language so users know where to click to switch."""
    next_code, next_label = next_language(current_code)
    return next_label


def get_language_label(code: str) -> str:
    for c, label, _ in LANGUAGES:
        if c == code:
            return label
    return LANGUAGES[0][1]


def tr(text: str, lang: Optional[str] = None) -> str:
    """Translates a string into the target language (defaults to current)."""
    if not text:
        return text
    target = lang or _CURRENT_LANG
    if target == "en":
        return text
    table = TRANSLATIONS.get(target, {})
    return table.get(text, text)


# Translation tables for supported non-English languages
TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh_CN": {
        # Tab headers
        "Setup": "安装设置",
        "Graphics": "画面图像",
        "Patches": "游戏补丁",
        "Mods": "模组扩展",
        "LAN": "局域联机",
        "Advanced": "高级选项",
        "Log": "Log",

        # Left panel
        "PC edition  ·  v": "PC 移植版  ·  v",
        "PLAY": "开始游戏",
        "RUNNING": "运行中",
        "Cancel": "取消",
        "LAN mode (secret lanmode)": "局域网模式 (隐藏联机功能)",
        "No game added yet.": "尚未添加游戏镜像。",
        "Add your Gran Turismo 6 disc image in Setup.": "请在“安装设置”页面添加《GT赛车6》ISO 镜像。",
        "Preparing the emulator component...": "正在准备模拟器组件...",
        "Emulator component missing - reinstall the launcher.": "模拟器组件缺失，请重新安装启动器。",
        "Starting RPCS3...": "正在启动 RPCS3...",
        "Installing firmware...": "正在安装 PS3 固件...",
        "Installing update...": "正在安装游戏更新包...",
        "Applying patches...": "正在应用补丁...",

        # GroupBoxes
        "1. PS3 firmware": "1. PS3 系统固件",
        "2. Game disc": "2. 游戏光盘镜像",
        "3. Controllers": "3. 控制器与方向盘",
        "4. Game updates": "4. 游戏更新补丁",
        "Image quality": "画面画质优化",
        "Frame rate && display": "帧率与显示设置",
        "Camera (Extended FOV patch, 0 = stock)": "视角调整 (FOV 扩展补丁，0 为默认)",
        "Emulation": "模拟器核心参数",
        "GT6 Career Mod (+ Spec II mod)": "GT6 生涯模组 (+ Spec II Mod)",
        "Cheats (single player)": "单人作弊选项",
        "Mod readme": "模组说明文档",
        "LAN mode": "局域网对战模式",
        "Online (community server, EU disc 1.22 only)": "线上联机 (RPCN 社区服，仅限欧版 1.22)",
        "How to race over LAN": "如何进行局域网联机对战",
        "Firewall": "防火墙设置",
        "Tools": "常用工具",
        "Danger zone": "危险区域",
        "Troubleshooting": "故障排查指南",
        "About": "关于启动器",

        # Setup Tab Buttons & Text
        "Install firmware": "安装固件",
        "Reinstall firmware": "重新安装固件",
        "Choose PS3UPDAT.PUP...": "选择 PS3UPDAT.PUP 文件...",
        "If no PUP file is found locally it is downloaded from Sony's update server.": "若本地未找到 PUP 文件，将自动从索尼官方服务器下载。",
        "Installed": "已安装",
        "Not installed": "未安装",
        "Add ISO...": "添加 ISO 镜像...",
        "Add folder...": "添加文件夹...",
        "Scan for ISOs": "扫描 ISO 镜像...",
        "Add disc image (ISO)...": "添加光盘镜像 (ISO)...",
        "Scan for discs...": "扫描光盘镜像...",
        "Refresh": "刷新",
        "Select your decrypted GT6 ISO file.": "请选择已解密的《GT赛车6》ISO 镜像文件。",
        "Target version": "目标版本",
        "Download & install updates": "下载并安装更新",
        "Download && install updates": "下载并安装更新",
        "Gamepad mode": "手柄输入模式",
        "Automatic (first connected gamepad)": "自动 (首选已连接手柄)",
        "Automatic (first gamepad, else keyboard)": "自动 (首选手柄，否则键盘)",
        "Keyboard only": "仅键盘操作",
        "Keyboard": "键盘",
        "Manual (configured in RPCS3)": "手动 (在 RPCS3 中配置)",
        "Racing wheel": "力回馈方向盘",
        "Use racing wheel": "使用力回馈方向盘",
        "Enable wheel (emulates Logitech G27)": "启用方向盘 (模拟罗技 G27)",
        "Set up wheel...": "配置方向盘...",
        "Configure wheel...": "配置方向盘向导...",
        "Not set up yet.": "尚未配置。",
        "No gamepad connected.": "未检测到连接的手柄。",
        "No gamepad connected. Connect it (8BitDo: X-input mode) and click Refresh.": "未检测到手柄。请连接手柄（8BitDo 请设为 X-input 模式）并点击刷新。",
        "Gamepad detection unavailable (SDL3 library not found).": "手柄检测不可用（未找到 SDL3 运行库）。",
        "Connected:": "已连接：",
        "Player 1": "1P 玩家控制器",
        "Console language": "游戏主机语言",
        "Automatic (from the disc region)": "自动 (根据光盘区域决定)",
        "Parallel downloads": "并行下载线程数",
        "Delete update packages after installing (saves ~10 GB)": "安装完成后自动删除更新包 (节省约 10 GB 空间)",

        # Setup Descriptions
        "The emulated PS3's region always matches the disc (EU disc = European console), so the game starts with the right defaults. The language also sets the game text on the multi-language EU disc. In-game settings worth changing once (stored in your save): Options -> Display -> Display Size (HD) = 100 removes the black border; Options -> Global -> Units for km/h / mph.":
            "模拟的 PS3 主机区域始终与光盘版本匹配（欧版光盘对应欧洲主机），游戏启动时会自动采用正确的默认设置。此设置同时决定多语言欧版光盘的文本语言。游戏中推荐修改一次的设置（保存在存档中）：选项 -> 显示 -> 显示尺寸 (HD) 设为 100 可消除黑边；选项 -> 全局 -> 单位 可切换 km/h 与 mph。",
        "Automatic uses the first detected gamepad (Xbox, PlayStation, 8BitDo, Switch Pro ...) with standard button mapping; if none is detected, the current RPCS3 input setting is kept. Choose Keyboard explicitly to switch to keyboard input. Racing-game style triggers (RT accelerate, LT brake): in the game, Options -> Wireless Controller.":
            "自动模式会优先使用检测到的首个手柄（Xbox、PlayStation、8BitDo、Switch Pro 等）并应用标准键位映射；若未检测到手柄，则保持 RPCS3 当前输入配置。明确选择“键盘”可强制切换为键盘操作。赛车游戏主流扳机键（RT 油门、LT 刹车）：可在游戏内“选项 -> 无线控制器”中设置。",
        "Any wheel (Logitech, Thrustmaster, Fanatec, Moza ...) works: the game sees it as a Logitech G27, which GT6 supports natively, including force feedback. The set-up asks you to turn the wheel and press each pedal/button once.":
            "支持各类力回馈方向盘（罗技、图马思特、Fanatec、魔爪等）：游戏原生将其识别为罗技 G27 并完美支持力回馈。配置向导仅需约 30 秒（转动方向盘并依次踩下踏板与按键即可完成校准）。",
        "Updates are installed in order (1.02 -> 1.22, 1.01 is skipped), downloads resume and every package is SHA-1 checked. After installing, start the game once so it can unpack its update data - only then install mods.":
            "游戏更新包将按序安装（1.02 -> 1.22，跳过 1.01），支持断点续传且每个安装包均经过 SHA-1 校验。安装完成后，请先启动一次游戏以便其解压更新数据——之后再安装模组。",

        # Graphics Tab Buttons & Controls
        "Resolution": "内部渲染分辨率",
        "Output resolution": "输出分辨率",
        "Resolution scale": "内部渲染倍率",
        "Anti-aliasing": "抗锯齿模式",
        "Output scaling": "输出缩放模式",
        "FSR sharpening": "FSR 锐化强度",
        "Anisotropic filter": "各向异性过滤",
        "Aspect ratio": "画面显示比例",
        "PS3 output": "PS3 输出分辨率",
        "Shadows": "阴影质量",
        "Motion blur": "动态模糊效果",
        "Depth of field": "景深虚化效果",
        "Lamp glare (1 = stock)": "路灯眩光倍率 (1 为原生)",
        "Frame rate": "目标帧率与垂直同步",
        "FidelityFX CAS sharpening": "FidelityFX CAS 画面锐化",
        "Anti-aliasing (MLAA)": "抗锯齿 (MLAA)",
        "Shadow quality": "阴影画质",
        "Street lamp glare": "路灯眩光",
        "Fullscreen": "全屏模式运行",
        "Show RPCS3 performance overlay": "显示 RPCS3 性能与帧率浮层",
        "60 FPS in Gallery / new-car screens (Unlock FPS patch)": "展厅/购车界面 60 FPS (Unlock FPS 补丁)",
        "Bumper vertical FOV": "保险杠视角垂直 FOV",
        "Cockpit vertical FOV": "驾驶舱视角垂直 FOV",
        "Roof/Hood vertical FOV": "车顶/车盖视角垂直 FOV",
        "Chase vertical FOV": "第三人称追尾垂直 FOV",
        "Reset to recommended": "恢复默认推荐设置",
        "Restore previous graphics settings": "恢复之前的画面设置",
        "Handheld 800p preset (Steam Deck / 1280x800)": "掌机 800p 预设 (Steam Deck / 1280x800)",
        "Apply the 800p handheld graphics preset. Press again to restore the graphics settings you had before.":
            "应用 800p 掌机画面预设。再次点击可恢复之前的画面设置。",
        "GT6 runs its simulation at 60 Hz, so above 60 FPS the game would run too fast. 60 FPS that holds steady matters more for racing.":
            "《GT赛车6》物理模拟固定为 60 Hz，超过 60 FPS 游戏会异常加速。对于赛车游戏而言，稳定不掉帧的 60 FPS 至关重要。",

        # Advanced Tab
        "GPU": "显卡 (GPU)",
        "Automatic (RPCS3 default)": "自动 (RPCS3 默认)",
        "Audio output": "音频输出声道",
        "Stereo (2.0)": "立体声 (2.0)",
        "Surround 5.1": "5.1 环绕声",
        "Render path": "渲染路径",
        "SPU block size": "SPU 块大小",
        "Thread scheduler": "线程调度器",
        "Operating System": "操作系统默认 (OS)",
        "RPCS3 Scheduler": "RPCS3 专属调度器",
        "Performance overlay": "性能监控浮层",
        "Disable ZCull occlusion queries": "禁用 ZCull 遮挡查询",
        "Accurate RSX reservation access": "精确 RSX 预留访问",
        "Multithreaded RSX": "多线程 RSX",
        "Handle RSX memory tiling": "处理 RSX 平铺显存",
        "Asynchronous texture streaming": "异步纹理流式加载",
        "Audio time stretching": "音频时间拉伸",
        "Feral GameMode": "Feral GameMode 游戏加速",
        "MangoHud overlay": "MangoHud 硬件监控浮层",
        "Reset RPCS3 to recommended": "重置 RPCS3 为推荐设置",
        "Fixes reward-screen slowdowns and Garage car-image softlocks; may crackle audio in bumper cam.":
            "修复结算奖励画面卡顿和车库缩略图卡死问题；保险杠视角下可能偶尔有杂音。",
        "Fewer RSX desyncs (recommended).": "减少 RSX 显卡不同步现象（推荐开启）。",
        "Causes vertex explosions on cars in GT6 - keep off.": "会导致 GT6 车辆出现尖锐黑色破面多边形爆炸——请保持关闭。",
        "Fixes coloured noise over driver names / HUD text in races (recommended).": "修复比赛中车手名字及仪表 HUD 文本上的彩色花屏杂点（推荐开启）。",
        "Smoother audio when the game slows down.": "在游戏发生短期掉帧时让音频播放更平滑。",

        # Tools & Danger Zone Buttons
        "Open launcher data folder": "打开启动器数据目录",
        "Open emulator log (for bug reports)": "打开模拟器日志 (用于反馈问题)",
        "Reset game data (removes installed updates and mods, keeps saves)": "重置游戏数据 (清除已安装更新及模组，保留存档)",
        "Open RPCS3 directory": "打开 RPCS3 所在目录",
        "Open RPCS3 GUI": "打开 RPCS3 主界面",
        "Open GT6 save folder": "打开 GT6 存档文件夹",
        "Open shaders cache": "打开着色器缓存目录",
        "Clear shaders cache": "清空着色器缓存",
        "- Stuck at the Sony Computer Entertainment logo: delete GT6's save data (RPCS3 -> Manage -> Save Data).\n- Black 3D world on 1.06+: Render path must use color buffers (Automatic does this).\n- Garage softlock while updating car pictures: keep 'Disable ZCull occlusion queries' on.\n- Spiky black car bodies: turn Multithreaded RSX off.\n- First start of a version takes minutes (PPU/SPU caches compile) - later starts are fast.":
            "- 卡在索尼电脑娱乐 (SCE) 标志界面：请删除 GT6 存档数据 (RPCS3 -> Manage -> Save Data)。\n- 1.06+ 版本 3D 画面全黑：渲染路径必须开启颜色缓冲 (自动模式已默认开启)。\n- 更新车辆照片时车库死锁卡住：保持“禁用 ZCull 遮挡查询”开启。\n- 车辆模型出现尖刺黑块爆炸：请关闭“多线程 RSX”。\n- 每次新版本首次启动需要编译 PPU/SPU 缓存（约数分钟），后续启动将非常迅速。",

        # Mods Tab
        "Download from GTPlanet": "前往 GTPlanet 网页下载",
        "Import archive...": "导入模组压缩包...",
        "Install Spec II + Career mod": "安装 Spec II + 生涯模组",
        "Uninstall all mods (restore original)": "卸载全部模组 (还原纯净版)",
        "By Lunard, based on Spec II Beta 7 (Nenkai, TheAdmiester), with features from Strato mod (Emivebe) and Performance mod (Plunke). Requires game version 1.22.":
            "作者 Lunard，基于 Spec II Beta 7（Nenkai、TheAdmiester 开发），融合 Strato 模组与性能模组特性。需要游戏版本为 1.22。",
        "Every file a mod overwrites is backed up, so uninstalling restores the game exactly. Start a new save when you first use the Career mod.":
            "模组替换的所有原版文件均会自动备份，卸载时将无损精准还原。首次使用生涯模组时请务必开启全新游戏存档。",
        "Enable GT6's developer menu (credits, cars) - game version 1.22":
            "启用 GT6 原生开发者菜单 (刷钱、刷车) - 需游戏版本 1.22",
        "In the game, at My Home: hold R1 and press SELECT (your pad: hold RB, press the View/Back button; keyboard: hold E, then hold Space ~1 s).\n- Cashier: move the slider to the amount you want (steps of Cr. 100,000) and press Exec - this SETS your credits to that amount.\n- Garage: add cars at random.\nSave afterwards. Never use Misc -> Delete Save Data in that menu. Not for online play.\nWhile on, the race pause menu also shows the developer-only 'Force finish' button; its label reads 'caption_FORCE_FINISH' because the game has no text for it.":
            "在游戏主界面“我的家 (My Home)”中：按住 R1 并按 SELECT（Xbox 手柄：按住 RB 并按 View/Back 键；键盘：按住 E 并按住空格约 1 秒）。\n- Cashier (收银台)：滑动滑块选择想要的金额（以 100,000 Cr. 为步长）并按 Exec 执行——直接将资金设为该金额。\n- Garage (车库)：随机添加车辆到车库。\n修改后请保存游戏。切勿点击该菜单内的 Misc -> Delete Save Data。不可用于线上联机。\n开启后，比赛暂停菜单还会出现开发者专用的“强制完赛”按钮（显示为 caption_FORCE_FINISH）。",

        # LAN Tab
        "Enable LAN play (boots with 'lanmode', no PSN needed)": "启用局域网联机对战 (附带 lanmode 参数启动，无需 PSN)",
        "Status": "联机状态",
        "Player name": "玩家昵称",
        "New PSID": "生成新 PSID",
        "Console PSID": "控制台 PSID",
        "Bind address": "绑定网卡地址",
        "This PC": "本机 IP 地址",
        "Enable online via the community GT6 server (irekej patch)": "启用线上联机 (通过 irekej 社区服务器补丁)",
        "Uses the community 'irekej' GT6 server through the RPCN network. Enter your RPCN account below (stored like RPCS3 does: the password is only kept as a hash). LAN mode takes priority when both are ticked.":
            "通过 RPCN 网络连接 irekej 社区 GT6 服务器。在下方输入您的 RPCN 账号（密码仅以哈希值加密存储）。两项同时勾选时局域网模式优先。",
        "RPCN user": "RPCN 用户名",
        "Password": "密码",
        "Token": "验证令牌 (Token)",
        "Save RPCN login": "保存 RPCN 登录凭据",
        "Ticked = applied at boot. Patches driven by the Graphics/LAN tabs are ticked automatically; ticking or unticking here overrides them.":
            "勾选项在游戏启动时自动生效。画面与局域网页面所选的补丁已自动勾选；在此手动更改将覆盖默认设置。",
        "Update patch databases": "更新补丁数据库",
        "Ready for": "就绪：",
        "Not available": "不可用：",

        # Log Tab
        "Save current logs": "导出并保存日志",
        "Open RPCS3 log": "打开 RPCS3 日志文件",
        "Copy log": "复制日志内容",
        "Clear log": "清空日志窗口",

        # Common
        "Close": "关闭",
        "Continue": "继续",
        "Hardware may struggle with GT6": "硬件配置提示",
        "This PC may struggle to run Gran Turismo 6 smoothly.": "当前电脑配置在运行《GT赛车6》时可能会遇到性能瓶颈。",
        "Switch language": "切换界面语言",

        # Auto-configuration
        "⚡ Auto-configure for my PC": "⚡ 根据本机配置自动优化",
        "Restore previous settings": "恢复之前的设置",
        "Presets": "预设方案",
        "Hardware Auto-Configuration": "硬件配置自动优化",
        "Optimal settings have been applied based on your detected hardware:\n\n": "已根据检测到的电脑硬件应用最佳性能设置：\n\n",
        "\n\n(You can click 'Restore previous settings' anytime to revert.)": "\n\n(您可以随时点击“恢复之前的设置”以还原。)",
        "Your previous settings have been restored.": "之前的设置已成功恢复。",
        "No previous settings backup was found.": "未找到之前的设置备份。",
        "Restore Settings": "恢复设置",

        # Wheel Controls & Review
        "Invert pedals": "反转踏板",
        "Invert throttle, brake, and clutch pedal polarity if they act as pressed when released.": "如果踏板在松开时表现为完全踩下，反转油门、刹车和离合器踏板的极性。",
        "No wheel mapping found. Please set up your wheel first.": "未找到方向盘配置。请先完成方向盘设置向导。",
        "No pedal axes found to invert.": "未找到可反转的踏板轴。",
        "Pedal polarity updated:\n\n": "踏板极性已更新：\n\n",
        "Inverted": "已反转",
        "Normal": "正常",
        "Controls Review & Test": "控制器检查与测试",
        "Test your steering and pedals below. If any pedal is pressed when released, check 'Invert'.": "请在下方测试您的方向盘与踏板。如果任何踏板在松开时显示为被踩下，请勾选“反转”。",
        "Save & Finish": "保存并完成",
        "Steering": "方向盘转向",
        "Input level:": "输入强度：",
        "Throttle": "油门",
        "Brake": "刹车",
        "Clutch": "离合器",
        "Invert": "反转",
        "Buttons: press any mapped button to test": "按键测试：按下任意已映射按键进行测试",
        "Pressed": "已按下",
        "Handheld": "掌机",
        "Handheld Controller": "掌机手柄",
        # Launcher update notice
        "New launcher": "新版启动器",
        "beta": "测试版",
        "release": "正式版",
        "available": "已发布",
        "Download": "下载",
        "You have": "当前版本",
        "Force CPU Blit: resolution scale above 100% causes a green edge band. Keep resolution scale at 100% and use FSR upscaling.": "强制 CPU Blit：分辨率缩放超过 100% 会导致屏幕边缘出现绿色色带。请将分辨率缩放保持为 100% 并使用 FSR 提升清晰度。",
        # Mods quick-exit prompt (#49)
        "Game closed right after starting": "游戏启动后立即关闭",
        "Gran Turismo 6 closed by itself right after starting.": "《GT赛车6》在启动后立即自行关闭。",
        "Mods are installed, and on some PCs the mods make the game close at start-up.\n\nUninstall all mods now? The original game files are restored exactly and your save data is not touched. You can install the mods again later from the Mods tab.": "当前已安装模组，在部分电脑上模组会导致游戏启动时关闭。\n\n现在卸载全部模组吗？原始游戏文件将被完整还原，存档数据不受影响。之后可以在“模组扩展”页面重新安装。",
        "Uninstall mods": "卸载模组",
        "Keep mods": "保留模组",
        "Experimental: these mods do not work on every PC. If the game closes by itself right after starting, click 'Uninstall all mods' - the launcher also offers this automatically.": "实验性功能：这些模组并非在所有电脑上都能正常运行。如果游戏启动后立即自行关闭，请点击“卸载全部模组”——启动器也会自动提示此操作。",
        # Hardware advisory popup
        "Current internal target: approximately {w}x{h} ({scale}%).": "当前内部渲染目标：约 {w}x{h} ({scale}%)。",
        "Current resolution scale: {scale}%.": "当前分辨率缩放：{scale}%。",
        "not identified in an RPCS3 log yet": "尚未在 RPCS3 日志中识别",
        "Detected Vulkan GPU: {gpu}": "检测到的 Vulkan 显卡：{gpu}",
        "Lowering the output resolution or internal resolution scale may help. This is an advisory only; you can continue if you want to try.": "降低输出分辨率或内部分辨率缩放可能会有所帮助。这只是一条提示，您仍可以继续尝试。",
        # Hardware warnings
        "Only {n} logical CPU thread(s) detected; GT6 needs at least a 4-core-class CPU.": "仅检测到 {n} 个逻辑 CPU 线程；《GT赛车6》至少需要四核级别的 CPU。",
        "{ram} GiB RAM detected; 16 GiB is recommended to reduce memory pressure.": "检测到 {ram} GiB 内存；建议 16 GiB 以减轻内存压力。",
        "Integrated GPU detected (shared VRAM). A dedicated GPU with 6+ GB VRAM is recommended for GT6 to avoid stuttering.": "检测到集成显卡（共享显存）。建议使用 6 GB 以上显存的独立显卡运行《GT赛车6》，以避免卡顿。",
        "Low VRAM GPU detected ({gb} GB). 6+ GB VRAM is recommended for GT6. Higher resolutions (1080p+ / 1440p) may stutter or run out of memory.": "检测到低显存显卡（{gb} GB）。建议《GT赛车6》使用 6 GB 以上显存。较高分辨率（1080p 以上 / 1440p）可能会卡顿或显存不足。",
        "Low VRAM GPU detected (< 6 GB). 6+ GB VRAM is recommended for GT6. Keep resolution scale at 100% (720p/1080p) to avoid stuttering.": "检测到低显存显卡（< 6 GB）。建议《GT赛车6》使用 6 GB 以上显存。请将分辨率缩放保持为 100%（720p/1080p）以避免卡顿。",
        "Recommended - keep this on. Fixes 1-5 fps on the car delivery and part install screens and Garage car-image softlocks. Unticking it does not stop cars flickering on tracks like London. May crackle audio in bumper cam.": "推荐 - 请保持开启。修复交车画面和零件安装画面仅 1-5 FPS 的问题，以及车库车辆图片更新时卡死的问题。取消勾选并不能解决伦敦等赛道上车辆闪烁的问题。在保险杠视角下可能会出现音频爆音。",
        # Keyboard key table (#48)
        "Keyboard keys": "键盘按键",
        "Player 1 is set to Keyboard.": "玩家 1 当前使用键盘。",
        "Player 1 is a gamepad now. These keys work when Player 1 is set to Keyboard (or Automatic finds no gamepad).": "玩家 1 当前使用手柄。将玩家 1 设为“键盘”（或“自动”未检测到手柄）时，这些按键才会生效。",
        "Key": "按键",
        "PS3 button": "PS3 按键",
        "In GT6": "游戏内功能",
        "Letter keys need a Latin keyboard layout (e.g. English). With a Cyrillic or Greek layout active, switch to English while playing.": "字母键需要使用拉丁键盘布局（例如英语）。如果当前为西里尔或希腊语布局，游戏时请切换为英语。",
        "Confirm / accelerate": "确认 / 加速",
        "Back": "返回",
        "Pause / start race": "暂停 / 开始比赛",
        "Steer left": "向左转向",
        "Steer right": "向右转向",
        "Menu up": "菜单上移",
        "Menu down": "菜单下移",
        "Menu left": "菜单左移",
        "Menu right": "菜单右移",
    }
}

TRANSLATIONS["fr"] = _FR
TRANSLATIONS["ja"] = _JA
