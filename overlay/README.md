# SystemOverlay

Indicateur d'état système Windows — ligne unique, always on top, click-through.

```
CPU  5% | RAM  9.2/32GB | GPU 23% | VRAM 4.2/8GB | NET ↓  2.1 ↑  0.4 | DSK ↓ 12.0 ↑  3.0 MB/s | TMP  62° | UP 02:14:33
```

---

## Installation

**Première fois** — double-clic sur `INSTALL_ET_LANCER.bat`
Installe les dépendances et lance l'overlay.

**Fois suivantes** — double-clic sur `LANCER.bat`

### Dépendances installées automatiquement
```
psutil        CPU / RAM / NET / DISK
pynvml        GPU % / VRAM / TEMP (NVIDIA uniquement)
pystray       icône system tray (quitter)
pillow        icône tray
screeninfo    détection multi-écran
```

---

## Contrôles

| Action | Geste |
|---|---|
| Déplacer | Clic gauche + drag |
| Quitter | Clic droit sur l'icône tray (barre des tâches) |
| Passer sous l'overlay | Survoler → disparaît, quitter la zone → réapparaît |

---

## Configuration

Tout se modifie dans le bloc `CONFIG` en tête de `overlay.py`.

### Affichage

| Paramètre | Défaut | Description |
|---|---|---|
| `REFRESH_MS` | `200` | Intervalle de collecte et d'affichage (ms), plus lent 500ms |
| `SMOOTH_N` | `3` | Lissage moving average — nombre de samples. `1` = brut, `5` = très lissé |
| `FONT` | `Consolas 12 bold` | Police, taille, style |

### Fond

| Paramètre | Défaut | Description |
|---|---|---|
| `BG_VISIBLE` | `False` | `True` = bandeau sombre · `False` = typo seule, fond transparent |
| `BG_COLOR` | `#111111` | Couleur du bandeau (si `BG_VISIBLE = True`) |

### Typo

| Paramètre | Défaut | Description |
|---|---|---|
| `TEXT_COLOR` | `#FFFFFF` | Couleur de base de toute la typo |
| `UP_COLOR` | `#FF0000` | Couleur spécifique du compteur UP (uptime) |
| `TEXT_ALPHA` | `1.0` | Opacité simulée de la typo (mélange avec `BG_COLOR`) |

### Fenêtre

| Paramètre | Défaut | Description |
|---|---|---|
| `ALPHA` | `0.80` | Opacité globale de la fenêtre (fond + typo simultanément) |
| `ALPHA_HOVER` | `0.0` | Opacité au survol souris (`0.0` = invisible) |
| `CORNER` | `"TR"` | Position : `TL` `TC` `TR` `BL` `BC` `BR` |
| `MARGIN` | `-2` | Marge bord écran (px, négatif = bord collé) |
| `SCREEN` | `0` | Écran cible : `0` = principal, `1` = second, `2` = troisième... |

### Bandeau

| Paramètre | Défaut | Description |
|---|---|---|
| `BAND_PADX` | `6` | Marge intérieure gauche/droite (px) |
| `BAND_PADY` | `0` | Marge intérieure haut/bas (px) |

### Seuils warn / critique

```python
WARN = dict(cpu=80, ram=85, temp=80)   # → texte orange
CRIT = dict(cpu=90, ram=92, temp=90)   # → texte rouge
```

### Flash

| Paramètre | Défaut | Description |
|---|---|---|
| `FLASH_COLOR` | `#C00000` | Couleur du flash au changement de valeur |
| `FLASH_HOLD_MS` | `120` | Durée du flash (ms) |
| `FLASH_THRESHOLD_PCT` | `1.0` | Seuil déclenchement flash CPU/GPU/RAM (%) |
| `FLASH_THRESHOLD_MBS` | `0.15` | Seuil déclenchement flash NET/DSK (MB/s) |
| `FLASH_THRESHOLD_TEMP` | `1.0` | Seuil déclenchement flash TMP (°C) |

### Modules optionnels

| Paramètre | Défaut | Description |
|---|---|---|
| `VRAM_SHOW` | `True` | Affiche VRAM used/total GB (NVIDIA uniquement) |

---

## Ordre des segments

L'ordre d'affichage est défini par la liste `fixed` dans `Overlay.__init__` :

```python
fixed = ['cpu', 'ram']
if GPU_OK: fixed += ['gpu']
if GPU_OK and VRAM_SHOW: fixed += ['vram']
fixed += ['sep_net', 'nd', 'nu', 'sep_dsk', 'dr', 'dw', 'mbps', 'tmp', 'uptime']
```

Déplacer un nom dans la liste = déplacer le segment à l'écran.
Chaque segment commence par `" | "` dans son texte — à retirer si placé en premier.

| Nom | Affiché |
|---|---|
| `cpu` | `CPU 34%` |
| `ram` | `\| RAM 9.2/32GB` |
| `gpu` | `\| GPU 12%` |
| `vram` | `\| VRAM 4.2/8GB` |
| `sep_net` | `\| NET ` |
| `nd` | `↓ 2.1` |
| `nu` | `↑ 0.4` |
| `sep_dsk` | `\| DSK ` |
| `dr` | `↓ 5.2` |
| `dw` | `↑ 1.1` |
| `mbps` | `MB/s` |
| `tmp` | `\| TMP 62°` |
| `uptime` | `\| UP 02:14:33` |

---

## Multi-écran

```python
SCREEN = 0   # écran principal
SCREEN = 1   # second écran (trié par position X, de gauche à droite)
SCREEN = 2   # troisième écran
```

`CORNER` s'applique identiquement sur l'écran cible.
Fallback automatique sur l'écran principal si l'index est invalide.

---

## Notes techniques

- GPU / VRAM / TMP : NVIDIA uniquement via `pynvml` (driver NVIDIA requis, pas d'admin)
- Sans GPU NVIDIA : `GPU`, `VRAM`, `TMP` masqués ou affichés `n/a`
- `BG_VISIBLE = False` utilise `-transparentcolor black` (Win32) — fond réellement transparent
- `ALPHA` est la seule vraie transparence tkinter/Windows — affecte fond + typo ensemble
- Click-through via `WS_EX_TRANSPARENT | WS_EX_LAYERED` (Win32) — les clics passent sous l'overlay
- Hover invisible via polling `after(50ms)` — `<Leave>` inutilisable quand `ALPHA_HOVER = 0`
