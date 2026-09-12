# Discovery Audit — `C:\Users\rolev\Documents`

- Scanned at: 2026-07-31T19:55:00.549491+00:00
- Duration: 0.797s
- Max depth: 2
- Folders discovered: 29
- Paths skipped (permission/reparse): 3
- Errors: 0

## Summary

- Folders scanned: 29
- Projects detected: 7
- Git repositories: 5
- Static websites: 0
- Python projects: 2
- Node projects: 3
- Unknown folders: 0
- Safe to move: 24
- Needs review: 5
- High risk: 1

## Summary by classification

| Classification | Count |
|---|---|
| Software Project | 2 |
| Mixed Project | 5 |
| Non-project | 22 |

## Projects

| Project | Type | Git | Health | Move Risk | Recommendation |
|---|---|---|---|---|---|
| ACID Pro 7.0 Projects | Non-project | - | 12 | low | Leave where it is |
| ACID Pro Suite Projects | Non-project | - | 12 | low | Archive |
| AGUA-AZUL-APP | Software Project | - | 37 | medium | Rename |
| Audacity | Non-project | - | 12 | low | Archive |
| AVerMedia CamEngine | Non-project | - | 12 | low | Archive |
| BarTender | Non-project | - | 12 | low | Archive |
| charcos-site | Mixed Project | main@f53f85f | 37 | medium | Requires manual review |
| ConnectWiseControl | Non-project | - | 12 | low | Archive |
| CURP | Non-project | - | 12 | low | Archive |
| Custom Office Templates | Non-project | - | 12 | low | Archive |
| desierto-creativo-site | Mixed Project | main@9a49909 | 46 | low | Requires manual review |
| FeedbackHub | Non-project | - | 12 | low | Archive |
| INE | Non-project | - | 12 | low | Leave where it is |
| MAGIX | Non-project | - | 12 | low | Archive |
| ManyCam Projects | Non-project | - | 12 | low | Archive |
| My Shapes | Non-project | - | 12 | low | Archive |
| OneNote Notebooks | Non-project | - | 12 | low | Archive |
| Plantillas personalizadas de Office | Non-project | - | 12 | low | Archive |
| PowerToys | Non-project | - | 12 | low | Archive |
| role-content-factory | Mixed Project | master@b8376a7 | 85 | medium | Move into IA PROJECTS |
| rolevaldez.com | Mixed Project | main@8e87767 | 21 | medium | Requires manual review |
| SAN FRANCISCO | Non-project | - | 12 | low | Archive |
| ScreenConnect | Non-project | - | 12 | low | Leave where it is |
| Simple Macro Recorder | Non-project | - | 12 | low | Archive |
| SUPER-FACIL | Mixed Project | - | 50 | high | Requires manual review |
| Tito  - TEC | Non-project | - | 12 | low | Archive |
| Wondershare | Non-project | - | 12 | low | Archive |
| Zoom | Non-project | - | 12 | low | Archive |
| agua-azul-app | Software Project | main@49601c9 | 37 | low | Requires manual review |

## Recommendations

- **ACID Pro 7.0 Projects** -> Leave where it is: classified Non-project -- not something the Discovery Engine should manage
- **ACID Pro Suite Projects** -> Archive: classified Non-project, stale, and only 3 file(s) -- looks like an empty or abandoned folder
- **AGUA-AZUL-APP** -> Rename: this folder's only nested project ('agua-azul-app') has the same name -- it looks like a redundant wrapper folder; consider flattening 'agua-azul-app' up one level instead of keeping both
- **Audacity** -> Archive: classified Non-project, stale, and only 1 file(s) -- looks like an empty or abandoned folder
- **AVerMedia CamEngine** -> Archive: classified Non-project, stale, and only 1 file(s) -- looks like an empty or abandoned folder
- **BarTender** -> Archive: classified Non-project, stale, and only 0 file(s) -- looks like an empty or abandoned folder
- **charcos-site** -> Requires manual review: mixed project but health score 37 is below the confidence threshold for an automatic move
- **ConnectWiseControl** -> Archive: classified Non-project, stale, and only 0 file(s) -- looks like an empty or abandoned folder
- **CURP** -> Archive: classified Non-project, stale, and only 1 file(s) -- looks like an empty or abandoned folder
- **Custom Office Templates** -> Archive: classified Non-project, stale, and only 1 file(s) -- looks like an empty or abandoned folder
- **desierto-creativo-site** -> Requires manual review: mixed project but health score 46 is below the confidence threshold for an automatic move
- **FeedbackHub** -> Archive: classified Non-project, stale, and only 0 file(s) -- looks like an empty or abandoned folder
- **INE** -> Leave where it is: classified Non-project -- not something the Discovery Engine should manage
- **MAGIX** -> Archive: classified Non-project, stale, and only 0 file(s) -- looks like an empty or abandoned folder
- **ManyCam Projects** -> Archive: classified Non-project, stale, and only 0 file(s) -- looks like an empty or abandoned folder
- **My Shapes** -> Archive: classified Non-project, stale, and only 3 file(s) -- looks like an empty or abandoned folder
- **OneNote Notebooks** -> Archive: classified Non-project, stale, and only 0 file(s) -- looks like an empty or abandoned folder
- **Plantillas personalizadas de Office** -> Archive: classified Non-project, stale, and only 0 file(s) -- looks like an empty or abandoned folder
- **PowerToys** -> Archive: classified Non-project, stale, and only 0 file(s) -- looks like an empty or abandoned folder
- **role-content-factory** -> Move into IA PROJECTS: mixed project with health score 85 and medium move risk -- safe to consolidate into IA PROJECTS
- **rolevaldez.com** -> Requires manual review: mixed project but health score 21 is below the confidence threshold for an automatic move
- **SAN FRANCISCO** -> Archive: classified Non-project, stale, and only 1 file(s) -- looks like an empty or abandoned folder
- **ScreenConnect** -> Leave where it is: classified Non-project -- not something the Discovery Engine should manage
- **Simple Macro Recorder** -> Archive: classified Non-project, stale, and only 1 file(s) -- looks like an empty or abandoned folder
- **SUPER-FACIL** -> Requires manual review: move risk is high (6 hardcoded absolute-path references found) -- fix hardcoded paths/config before relocating
- **Tito  - TEC** -> Archive: classified Non-project, stale, and only 4 file(s) -- looks like an empty or abandoned folder
- **Wondershare** -> Archive: classified Non-project, stale, and only 0 file(s) -- looks like an empty or abandoned folder
- **Zoom** -> Archive: classified Non-project, stale, and only 0 file(s) -- looks like an empty or abandoned folder
- **agua-azul-app** -> Requires manual review: software project but health score 37 is below the confidence threshold for an automatic move

## Move-risk findings (high)

### SUPER-FACIL (`C:\Users\rolev\Documents\SUPER-FACIL`)
- 6 hardcoded absolute-path references found

## Skipped paths

- C:\Users\rolev\Documents\My Music
- C:\Users\rolev\Documents\My Pictures
- C:\Users\rolev\Documents\My Videos
