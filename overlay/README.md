# SystemOverlay

```
CPU  34% | GPU  12% | RAM  9.2/16GB | NET ↓  2.1 ↑  0.4 MB/s | DSK ↓ 12.0 ↑  3.0 MB/s | TMP  62°
```

Always on top · click-through · drag pour déplacer · clic droit pour quitter

---

## Première fois

Double-clic sur **INSTALL_ET_LANCER.bat**
→ installe psutil + pynvml, lance l'overlay.

## Fois suivantes

Double-clic sur **LANCER.bat**

---

## Personnalisation (overlay.py, lignes 20-30)

| Variable  | Valeur défaut | Options            |
|-----------|---------------|--------------------|
| `CORNER`  | `"TR"`        | TL / TR / BL / BR  |
| `ALPHA`   | `0.88`        | 0.0 → 1.0          |
| `REFRESH_MS` | `500`      | ms                 |
| `WARN`    | cpu=80 ram=85 temp=80 | ajustable   |
| `CRIT`    | cpu=90 ram=92 temp=90 | ajustable   |

## Contrôles

| Action          | Geste              |
|-----------------|--------------------|
| Déplacer        | Clic gauche + drag |
| Quitter         | Clic droit         |

## Notes

- GPU/TEMP : NVIDIA uniquement via pynvml (driver NVIDIA requis)
- Sans GPU NVIDIA : affiche `TMP n/a`, tout le reste fonctionne
- Pas d'accès admin requis
