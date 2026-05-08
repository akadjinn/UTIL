"""
SystemOverlay — indicateur d'etat instantane Windows
Double-clic sur overlay.py pour lancer.
Dependances : pip install psutil pynvml pystray pillow
"""

import tkinter as tk
import psutil
import time
import ctypes
import sys
import threading
from collections import deque

# ── Tray icon ─────────────────────────────────────────────────────────────────
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_OK = True
except Exception:
    TRAY_OK = False

# ── GPU NVIDIA ────────────────────────────────────────────────────────────────
try:
    import pynvml
    pynvml.nvmlInit()
    _gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    GPU_OK = True
except Exception:
    GPU_OK = False

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════
REFRESH_MS           = 200          # intervalle collecte + UI (ms)
SMOOTH_N             = 3            # moving average samples
FONT                 = ("Consolas", 12, "bold")

# Fond
BG_VISIBLE           = False        # True = bandeau visible | False = typo seule sur fond transparent
BG_COLOR             = "#111111"    # couleur du bandeau
# Typo
TEXT_ALPHA           = 1.0          # opacite de la typo (0.0 → 1.0)
                                    # note: tkinter ne supporte pas l'alpha
                                    # par widget — TEXT_ALPHA simule via
                                    # melange avec BG_COLOR
TEXT_COLOR           = "#FFFFFF"    # couleur de base de la typo (ok/normal)
UP_COLOR             = "#FF0000"    # couleur du compteur UP (uptime session)

# Fenetre
ALPHA                = 0.80         # opacite globale fenetre (active)
                                    # contrôle SIMULTANEMENT fond + typo
                                    # c'est la seule vraie transparence tkinter/Windows
ALPHA_HOVER          = 0.0          # opacite au survol
CORNER               = "TR"         # TL | TC | TR | BL | BC | BR
MARGIN               = -2           # px bord ecran
SCREEN               = 1            # 0 = ecran principal | 1 = second ecran | 2 = troisieme...

# Bandeau
BAND_PADX            = 6            # marge gauche/droite interieure (px)
BAND_PADY            = 0            # marge haut/bas interieure (px)

# Seuils warn/crit
WARN  = dict(cpu=80, ram=85, temp=80)
CRIT  = dict(cpu=90, ram=92, temp=90)
COL   = dict(ok=TEXT_COLOR, warn="#FF8C00", crit="#FF3333")

# GPU VRAM (NVIDIA)
VRAM_SHOW            = True         # True = affiche VRAM used/total (GB)

# Flash
FLASH_COLOR          = "#C00000"    # rouge flash
FLASH_HOLD_MS        = 120
FLASH_THRESHOLD_PCT  = 1.0          # % CPU/GPU/RAM
FLASH_THRESHOLD_MBS  = 0.15         # MB/s NET/DSK
FLASH_THRESHOLD_TEMP = 1.0          # degres C
# ══════════════════════════════════════════════════════════════════════════════

def _blend_color(hex_fg: str, hex_bg: str, alpha: float) -> str:
    """Melange hex_fg sur hex_bg avec opacite alpha → retourne hex."""
    def parse(h):
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    fr, fg, fb = parse(hex_fg)
    br, bg_, bb = parse(hex_bg)
    r = int(fr * alpha + br * (1 - alpha))
    g = int(fg * alpha + bg_ * (1 - alpha))
    b = int(fb * alpha + bb * (1 - alpha))
    return f"#{r:02x}{g:02x}{b:02x}"

def _text_color(base_hex: str) -> str:
    """Applique TEXT_ALPHA sur base_hex en melangeant avec BG_COLOR."""
    if TEXT_ALPHA >= 1.0:
        return base_hex
    return _blend_color(base_hex, BG_COLOR, TEXT_ALPHA)

# Couleurs effectives typo (precalculees)
_COL_OK   = _text_color(COL['ok'])
_COL_WARN = _text_color(COL['warn'])
_COL_CRIT = _text_color(COL['crit'])
_COL_FLASH= _text_color(FLASH_COLOR)

def _gcol_eff(raw: str) -> str:
    if raw == COL['crit']: return _COL_CRIT
    if raw == COL['warn']: return _COL_WARN
    return _COL_OK

# ── Moving average ────────────────────────────────────────────────────────────
class MA:
    def __init__(self, n=SMOOTH_N):
        self._buf = deque(maxlen=n)
    def push(self, v):
        self._buf.append(v)
        return sum(self._buf) / len(self._buf)

# ── Uptime session Windows ────────────────────────────────────────────────────
def _session_uptime() -> str:
    ms   = ctypes.windll.kernel32.GetTickCount64()
    secs = int(ms / 1000)
    h, r = divmod(secs, 3600)
    m, s = divmod(r, 60)
    if h >= 24:
        d, h = divmod(h, 24)
        return f"{d}j{h:02d}:{m:02d}"
    return f"{h:02d}:{m:02d}:{s:02d}"

# ── Disk mapping ──────────────────────────────────────────────────────────────
# ── Disk global state ────────────────────────────────────────────────────────
try:
    _disk_prev_snap = psutil.disk_io_counters()
except Exception:
    _disk_prev_snap = None
_ma_dr = MA(); _ma_dw = MA()

# ── Collecte ──────────────────────────────────────────────────────────────────
_net_prev = psutil.net_io_counters()
_net_time = time.monotonic()
_ma_nd = MA(); _ma_nu = MA()

def collect():
    global _net_prev, _net_time
    now = time.monotonic()
    dt  = max(now - _net_time, 0.001)

    cpu      = psutil.cpu_percent(interval=None)
    vm       = psutil.virtual_memory()
    ram_used = vm.used  / 1_073_741_824
    ram_tot  = vm.total / 1_073_741_824
    ram_pct  = vm.percent

    # Disques — global
    global _disk_prev_snap
    try:
        cur_disk = psutil.disk_io_counters()
    except Exception:
        cur_disk = None
    if cur_disk and _disk_prev_snap:
        dr = max(0.0, (cur_disk.read_bytes  - _disk_prev_snap.read_bytes)  / dt / 1_048_576)
        dw = max(0.0, (cur_disk.write_bytes - _disk_prev_snap.write_bytes) / dt / 1_048_576)
    else:
        dr = dw = 0.0
    _disk_prev_snap = cur_disk
    dr = _ma_dr.push(dr)
    dw = _ma_dw.push(dw)

    # NET
    net = psutil.net_io_counters()
    nd  = _ma_nd.push(max(0.0, (net.bytes_recv - _net_prev.bytes_recv) / dt / 1_048_576))
    nu  = _ma_nu.push(max(0.0, (net.bytes_sent - _net_prev.bytes_sent) / dt / 1_048_576))
    _net_prev = net
    _net_time = now

    gpu = temp = 0.0
    vram_used = vram_tot = 0.0
    if GPU_OK:
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(_gpu_handle)
            gpu  = util.gpu
            temp = pynvml.nvmlDeviceGetTemperature(_gpu_handle, pynvml.NVML_TEMPERATURE_GPU)
        except Exception:
            pass
        if VRAM_SHOW:
            try:
                mem = pynvml.nvmlDeviceGetMemoryInfo(_gpu_handle)
                vram_used = mem.used  / 1_073_741_824
                vram_tot  = mem.total / 1_073_741_824
            except Exception:
                pass

    return dict(cpu=cpu, gpu=gpu,
                ram_used=ram_used, ram_tot=ram_tot, ram_pct=ram_pct,
                nd=nd, nu=nu, dr=dr, dw=dw, temp=temp,
                vram_used=vram_used, vram_tot=vram_tot)

def global_color(d):
    c, r, t = d['cpu'], d['ram_pct'], d['temp']
    if c >= CRIT['cpu'] or r >= CRIT['ram'] or t >= CRIT['temp']: return COL['crit']
    if c >= WARN['cpu'] or r >= WARN['ram'] or t >= WARN['temp']: return COL['warn']
    return COL['ok']

# ── Flasher ───────────────────────────────────────────────────────────────────
class Flasher:
    def __init__(self, lbl: tk.Label, root: tk.Tk):
        self._lbl   = lbl
        self._root  = root
        self._after = None
        self._base  = _COL_OK

    def set_base(self, c: str):
        self._base = _gcol_eff(c)

    def trigger(self):
        if self._after:
            self._root.after_cancel(self._after)
        self._lbl.config(fg=_COL_FLASH)
        self._after = self._root.after(FLASH_HOLD_MS, self._restore)

    def _restore(self):
        self._lbl.config(fg=self._base)
        self._after = None

    def set_color_if_idle(self, c: str):
        if self._after is None:
            self._lbl.config(fg=_gcol_eff(c))



# ── Multi-ecran ──────────────────────────────────────────────────────────────
try:
    from screeninfo import get_monitors
    _MONITORS = sorted(get_monitors(), key=lambda m: (m.x, m.y))
    SCREENINFO_OK = True
except Exception:
    SCREENINFO_OK = False

def _get_screen_rect(screen_index: int):
    """
    Retourne (offset_x, offset_y, width, height) de l'ecran demande.
    Fallback sur l'ecran principal si index invalide ou screeninfo absent.
    """
    if SCREENINFO_OK and screen_index < len(_MONITORS):
        m = _MONITORS[screen_index]
        return m.x, m.y, m.width, m.height
    # Fallback : ecran principal via tkinter
    import tkinter as _tk
    _r = _tk.Tk(); _r.withdraw()
    w = _r.winfo_screenwidth(); h = _r.winfo_screenheight()
    _r.destroy()
    return 0, 0, w, h

# ── UI ────────────────────────────────────────────────────────────────────────
class Overlay:
    def __init__(self):
        self.root = tk.Tk()
        r = self.root
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.attributes("-alpha", ALPHA)
        _bg = BG_COLOR if BG_VISIBLE else "black"
        r.configure(bg=_bg)
        if not BG_VISIBLE:
            r.wm_attributes("-transparentcolor", "black")
        r.resizable(False, False)
        self._set_clickthrough()

        self._frame = tk.Frame(r, bg=_bg)
        self._frame.pack(padx=BAND_PADX, pady=BAND_PADY)

        # Ordre : CPU RAM GPU VRAM NET DSK TMP UP
        fixed = ['cpu', 'ram']
        if GPU_OK: fixed += ['gpu']
        if GPU_OK and VRAM_SHOW: fixed += ['vram']
        fixed += ['sep_net', 'nd', 'nu', 'sep_dsk', 'dr', 'dw', 'mbps', 'tmp', 'uptime']

        self._seg = {}
        for name in fixed:
            lbl = tk.Label(self._frame, text="", font=FONT,
                           fg=_COL_OK, bg=_bg, padx=0, pady=0)
            lbl.pack(side=tk.LEFT)
            self._seg[name] = {'lbl': lbl, 'fl': Flasher(lbl, r), 'prev': None}



        for name in fixed:
            self._bind(self._seg[name]['lbl'])
        self._bind(r)
        self._bind(self._frame)

        psutil.cpu_percent(interval=None)
        time.sleep(0.1)
        self._position()
        self._tick()

    def _bind(self, w):
        w.bind("<ButtonPress-1>", self._drag_start)
        w.bind("<B1-Motion>",     self._drag_move)
        w.bind("<Button-3>",      lambda e: self.root.destroy())
        w.bind("<Enter>",         self._on_enter)

    def _on_enter(self, _e):
        self.root.attributes("-alpha", ALPHA_HOVER)
        self._poll_hover()

    def _poll_hover(self):
        try:
            x, y = self.root.winfo_pointerxy()
            rx1  = self.root.winfo_rootx()
            ry1  = self.root.winfo_rooty()
            rx2  = rx1 + self.root.winfo_width()
            ry2  = ry1 + self.root.winfo_height()
            if rx1 <= x <= rx2 and ry1 <= y <= ry2:
                self.root.after(50, self._poll_hover)
            else:
                self.root.attributes("-alpha", ALPHA)
        except Exception:
            pass



    def _upd(self, name, text, val, threshold, col=None):
        s  = self._seg[name]
        bc = col or self._gcol
        s['fl'].set_base(bc)
        s['lbl'].config(text=text)
        if s['prev'] is not None and abs(val - s['prev']) > threshold:
            s['fl'].trigger()
        else:
            s['fl'].set_color_if_idle(bc)
        s['prev'] = val

    def _tick(self):
        d          = collect()
        self._gcol = global_color(d)
        gc         = self._gcol
        gc_eff     = _gcol_eff(gc)

        self._seg['sep_net']['lbl'].config(text=" | NET ", fg=gc_eff)
        self._seg['sep_dsk']['lbl'].config(text=" | DSK ", fg=gc_eff)

        # Ordre affiché : CPU RAM GPU VRAM NET DSK TMP UP
        self._upd('cpu', f"CPU {d['cpu']:3.0f}%",         d['cpu'],    FLASH_THRESHOLD_PCT)
        self._upd('ram', f" | RAM {d['ram_used']:4.1f}/{d['ram_tot']:.0f}GB",
                                                           d['ram_pct'], FLASH_THRESHOLD_PCT)
        if GPU_OK:
            self._upd('gpu',  f" | GPU {d['gpu']:3.0f}%", d['gpu'],    FLASH_THRESHOLD_PCT)
        if GPU_OK and VRAM_SHOW:
            self._upd('vram', f" | VRAM {d['vram_used']:.1f}/{d['vram_tot']:.0f}GB",
                                                           d['vram_used'], 0.1)
        self._upd('nd', f"↓{d['nd']:5.1f}",               d['nd'],    FLASH_THRESHOLD_MBS)
        self._upd('nu', f" ↑{d['nu']:5.1f}",              d['nu'],    FLASH_THRESHOLD_MBS)
        self._upd('dr', f"↓{d['dr']:5.1f}",               d['dr'],    FLASH_THRESHOLD_MBS)
        self._upd('dw', f" ↑{d['dw']:5.1f}",              d['dw'],    FLASH_THRESHOLD_MBS)
        self._seg['mbps']['lbl'].config(text=" MB/s", fg=gc_eff)
        if GPU_OK:
            self._upd('tmp', f" | TMP {d['temp']:3.0f}°", d['temp'],  FLASH_THRESHOLD_TEMP)
        else:
            self._seg['tmp']['lbl'].config(text=" | TMP n/a", fg=gc_eff)
        # UP — couleur independante UP_COLOR
        _up_col = _text_color(UP_COLOR)
        self._seg['uptime']['lbl'].config(text=f" | UP {_session_uptime()}", fg=_up_col)

        self._reposition_if_needed()
        self.root.after(REFRESH_MS, self._tick)

    def _reposition_if_needed(self):
        self.root.update_idletasks()
        if CORNER in ("TR", "BR", "TC", "BC"):
            self._position()

    def _set_clickthrough(self):
        try:
            hwnd  = ctypes.windll.user32.GetParent(self.root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20,
                style | 0x00000020 | 0x00080000)
        except Exception:
            pass

    def _position(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()

        # Recupere les coordonnees de l'ecran cible
        ox, oy, sw, sh = _get_screen_rect(SCREEN)

        cx = ox + (sw - w) // 2
        pos = {
            "TL": (ox + MARGIN,          oy + MARGIN),
            "TC": (cx,                   oy + MARGIN),
            "TR": (ox + sw - w - MARGIN, oy + MARGIN),
            "BL": (ox + MARGIN,          oy + sh - h - MARGIN),
            "BC": (cx,                   oy + sh - h - MARGIN),
            "BR": (ox + sw - w - MARGIN, oy + sh - h - MARGIN),
        }
        x, y = pos.get(CORNER, (ox + MARGIN, oy + MARGIN))
        self.root.geometry(f"+{x}+{y}")

    def _drag_start(self, e):
        self._dx = e.x_root - self.root.winfo_x()
        self._dy = e.y_root - self.root.winfo_y()

    def _drag_move(self, e):
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def quit(self):
        if TRAY_OK and hasattr(self, '_tray'):
            self._tray.stop()
        self.root.after(0, self.root.destroy)

    def run(self):
        if TRAY_OK:
            self._start_tray()
        self.root.mainloop()

    def _make_tray_icon(self):
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        d   = ImageDraw.Draw(img)
        d.rectangle([2, 2, 29, 29], fill="#CE3C3C")
        d.text((9, 7), "S", fill="white")
        return img

    def _start_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("SystemOverlay", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quitter", lambda icon, item: self.quit()),
        )
        self._tray = pystray.Icon(
            "SystemOverlay",
            self._make_tray_icon(),
            "SystemOverlay — clic droit → Quitter",
            menu,
        )
        threading.Thread(target=self._tray.run, daemon=True).start()


if __name__ == "__main__":
    if sys.platform == "win32":
        ctypes.windll.user32.ShowWindow(
            ctypes.windll.kernel32.GetConsoleWindow(), 0)
    Overlay().run()
