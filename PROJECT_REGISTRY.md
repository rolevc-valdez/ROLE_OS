# Role Ecosystem — Project Registry

Last Updated: 2026-09-13 (Phase 2 backup completado: role-content-factory y RoleSocialFactory ahora en GitHub privado)
Registry Version: 0.1.1
Source: `C:\Users\rolev\Documents\PROJECT_AUDIT_2026-09-12.md` (auditoría de solo lectura, 2026-09-12) + verificación directa durante Phase 2 (2026-09-13)

Este registro es un índice. No duplica el contenido de los proyectos — cada entrada apunta a su ubicación real (Git+GitHub, Google Drive, o ambos). Información corporativa (Kontoor Brands / Unger / CRG) se registra solo como referencia — nunca se copia su contenido aquí.

---

## ACTIVE PROJECTS

### ROLE_OS

Type: Software / Role OS
Status: Active
Primary Location: `Drive/1 - IA PROJECTS/ROLE_OS`
Git: Yes (branch `main`)
GitHub: Private — `git@github.com:rolevc-valdez/ROLE_OS.git`
Backup Strategy: GIT + DRIVE
Last Known Activity: 2026-09-13 (commit `92504b0`)
Role OS Tracking: Self (this is Role OS)
Security Classification: NORMAL
Notes: Repo maestro. `var/*.db` (runtime SQLite) intencionalmente fuera de Git, respaldado solo por Drive — decisión aceptada. Un archivo modificado sin commitear (`dashboard/tests/conftest.py`) fuera del alcance de Phase 2, pendiente de revisión propia.

### ROLE Commerce Factory

Type: Software
Status: Active
Primary Location: `Drive/1 - IA PROJECTS/ROLE Commerce Factory`
Git: Yes (branch `main`, clean)
GitHub: Private — `git@github.com:rolevc-valdez/ROLE-Commerce-Factory.git`
Backup Strategy: GIT + DRIVE
Last Known Activity: 2026-08-21
Role OS Tracking: Registered
Security Classification: NORMAL
Notes: Último commit "milestone: Phase 3 local provider pipeline validated". No requiere acción.

### role-ecosystem

Type: Software / Documentation (estrategia, decisiones, roadmap)
Status: Active
Primary Location: `Drive/1 - IA PROJECTS/role-ecosystem`
Git: Yes (branch `main`)
GitHub: Private — `git@github.com:rolevc-valdez/role-ecosystem.git`
Backup Strategy: GIT + DRIVE
Last Known Activity: 2026-08-10
Role OS Tracking: Registered
Security Classification: NORMAL
Notes: 2 archivos dirty al momento de la auditoría — sin acción tomada (fuera de alcance de Phase 2).

### role-content-factory

Type: Software (Python)
Status: Active
Primary Location: `C:\Users\rolev\Documents\role-content-factory`
Git: Yes (branch `master`)
GitHub: Private — `https://github.com/rolevc-valdez/role-content-factory.git` (creado y verificado 2026-09-13)
Backup Strategy: REMOTE BACKED UP
Last Known Activity: 2026-08-13 (commit `23e0967`)
Role OS Tracking: Registered
Security Classification: NORMAL (preflight de seguridad completo: sin `.env` trackeado nunca, sin secretos en historial completo, sin datos corporativos)
Notes: Contiene `.env` real sin trackear en working tree (raíz y `OpenMontage/`) — ya cubierto por `.gitignore`, nunca comiteado. Repo pequeño (4.1M). Push verificado: HEAD local = HEAD remoto (`23e0967`), repo privado confirmado.

### RoleSocialFactory

Type: Software (desktop app, Python/PyInstaller)
Status: Active
Primary Location: `Drive/1 - IA PROJECTS/RoleSocialFactory` (copia canónica confirmada — su historial es superset estricto de la copia local `RoleSocialFactory-git-temp`, 14 vs 11 commits, más reciente: V2.0.1 vs V1.0)
Git: Yes (branch `master`, 9 archivos dirty — preexistentes, sin tocar)
GitHub: Private — `https://github.com/rolevc-valdez/RoleSocialFactory.git` (creado y verificado 2026-09-13)
Backup Strategy: REMOTE BACKED UP (remote `origin` = GitHub; remote `local-bundle` conservado como respaldo secundario, no eliminado)
Last Known Activity: 2026-09-06 (commit `3d554a1`)
Role OS Tracking: Registered
Security Classification: NORMAL (preflight completo: sin secretos en historial, sin `.env` trackeado, sin datos corporativos, 16M principalmente imágenes)
Notes: Copia secundaria `RoleSocialFactory-git-temp` (local, perfil) es más antigua/subconjunto — no se toca ni se borra en esta fase. Push verificado: HEAD local = HEAD remoto (`3d554a1`), repo privado confirmado. `RoleSocialFactory-history.bundle` sigue existiendo sin cambios.

### bolsa-de-trabajo

Type: Software (Next.js/TypeScript, Supabase)
Status: Active
Primary Location: `C:\Users\rolev\Documents\bolsa-de-trabajo`
Git: Yes (branch `main`, 1 dirty)
GitHub: Private — `git@github.com:rolevc-valdez/bolsa-de-trabajo.git`
Backup Strategy: GIT (remote backed up)
Last Known Activity: 2026-09-02
Role OS Tracking: Registered
Security Classification: SENSITIVE (`.env.local` presente en working tree, no trackeado)
Notes: Sin acción en Phase 2.

### agua-azul-app

Type: Software (multi-módulo: mobile/web-admin/web-supervisor, Supabase)
Status: Active
Primary Location: `C:\Users\rolev\Documents\AGUA-AZUL-APP\agua-azul-app`
Git: Yes (branch `main`, 4 dirty)
GitHub: `https://github.com/rolevc-valdez/agua-azul-app.git`
Backup Strategy: GIT (remote backed up)
Last Known Activity: 2026-07-14
Role OS Tracking: Registered
Security Classification: NORMAL
Notes: Solo un commit inicial — historial aún delgado.

### charcos-site

Type: Content / Static site
Status: Active
Primary Location: `C:\Users\rolev\Documents\charcos-site`
Git: Yes (branch `main`, clean)
GitHub: `https://github.com/rolevc-valdez/charcos-site.git`
Backup Strategy: GIT (remote backed up)
Last Known Activity: 2026-09-02
Role OS Tracking: Registered
Security Classification: NORMAL
Notes: 460M, mayormente media (img/video/patrocinadores) — candidato a excluir binarios pesados de Git en el futuro.

### desierto-creativo-site

Type: Content / Static site
Status: Active
Primary Location: `C:\Users\rolev\Documents\desierto-creativo-site`
Git: Yes (branch `main`, 6 dirty)
GitHub: `https://github.com/rolevc-valdez/desiertocreativo.git`
Backup Strategy: GIT (remote backed up)
Last Known Activity: 2026-09-12
Role OS Tracking: Registered
Security Classification: NORMAL
Notes: Existe snapshot local bare `desierto-creativo-site-BACKUP-20260912154731.git` — candidato a archivar/borrar en Phase 3 tras confirmar que el backup remoto está vigente.

### rolevaldez.com

Type: Personal / Content site
Status: Active
Primary Location: `C:\Users\rolev\Documents\rolevaldez.com`
Git: Yes (branch `main`, 14 dirty)
GitHub: `https://github.com/rolevc-valdez/rolevaldez.com.git`
Backup Strategy: GIT (remote backed up, PARTIAL — un mes de cambios sin commitear)
Last Known Activity: 2026-08-05
Role OS Tracking: Registered
Security Classification: SENSITIVE (`.env` presente en working tree, no trackeado)
Notes: Sin acción en Phase 2 — pendiente de que el usuario decida cuándo commitear.

---

## PARKED / INACTIVE

### RoleSocialFactory-git-temp

Type: Software (copia secundaria)
Status: Inactive (superset por la copia Drive)
Primary Location: `C:\Users\rolev\RoleSocialFactory-git-temp`
Git: Yes (branch `master`, clean)
GitHub: N/A (remote = `.bundle` local)
Backup Strategy: LOCAL ONLY
Last Known Activity: 2026-08-21
Role OS Tracking: Registered (referencia, no fuente de verdad)
Security Classification: NORMAL
Notes: Copia más antigua que la de Drive. No se modifica ni se elimina en esta fase.

### RoleSocialFactory-Build

Type: Build output (no es código fuente)
Status: Inactive
Primary Location: `Drive/1 - IA PROJECTS/RoleSocialFactory-Build`
Git: No
GitHub: N/A
Backup Strategy: ARCHIVE candidate (regenerable)
Last Known Activity: Unknown
Role OS Tracking: Registered
Security Classification: NORMAL

### desierto-creativo-site-BACKUP-20260912154731.git

Type: Bare git snapshot
Status: Inactive
Primary Location: `C:\Users\rolev\Documents\desierto-creativo-site-BACKUP-20260912154731.git`
Git: Yes (bare)
GitHub: N/A
Backup Strategy: LOCAL ONLY
Last Known Activity: 2026-09-12
Role OS Tracking: Registered
Security Classification: NORMAL
Notes: Candidato a archivar en Phase 3 tras confirmar backup remoto vigente de `desierto-creativo-site`.

### Codex

Type: Archivo de sesiones CLI (Codex/OpenAI)
Status: Inactive
Primary Location: `C:\Users\rolev\Documents\Codex`
Git: No
GitHub: N/A
Backup Strategy: LOCAL ONLY
Last Known Activity: Unknown
Role OS Tracking: Registered
Security Classification: NORMAL
Notes: 1.3G — no es un proyecto coherente, son carpetas de sesión fechadas.

### ROLE DB

Type: Placeholder
Status: Inactive (vacío)
Primary Location: `Drive/1 - IA PROJECTS/ROLE DB`
Git: No
GitHub: N/A
Backup Strategy: N/A
Last Known Activity: N/A
Role OS Tracking: Registered
Security Classification: NORMAL

---

## CREATIVE / MEDIA

### ROLE MASTER

Type: Brand / Prompt knowledge base
Status: Active
Primary Location: `Drive/1 - IA PROJECTS/ROLE MASTER`
Git: No
GitHub: N/A
Backup Strategy: DRIVE ONLY
Last Known Activity: Unknown
Role OS Tracking: Registered
Security Classification: NORMAL
Notes: Candidato futuro a GIT + DRIVE (fuera de alcance de Phase 2).

### ROLE_CONTENT_FACTORY

Type: Content decision layer (wrapping OpenMontage)
Status: Active
Primary Location: `Drive/1 - IA PROJECTS/ROLE_CONTENT_FACTORY`
Git: No
GitHub: N/A
Backup Strategy: DRIVE ONLY
Last Known Activity: Reciente
Role OS Tracking: Registered
Security Classification: NORMAL
Notes: Pequeño (~1.8M), buen candidato futuro a `git init`. No confundir con `role-content-factory` (local, con Git) — son proyectos distintos con nombre similar.

### ROLE ASSETS

Type: Image/logo library
Status: Active
Primary Location: `Drive/1 - IA PROJECTS/ROLE ASSETS`
Git: No
GitHub: N/A
Backup Strategy: DRIVE ONLY
Last Known Activity: Unknown
Role OS Tracking: Registered
Security Classification: NORMAL

### CHARCOS_SPONSOR_BATCH

Type: Asset generation batch tool + output
Status: Active
Primary Location: `Drive/1 - IA PROJECTS/CHARCOS_SPONSOR_BATCH`
Git: No
GitHub: N/A
Backup Strategy: DRIVE ONLY
Last Known Activity: 2026-08-22
Role OS Tracking: Registered
Security Classification: NORMAL

### Role Super Facil

Type: Content / PDF guide deliverables
Status: Active
Primary Location: `Drive/1 - IA PROJECTS/Role Super Facil`
Git: No
GitHub: N/A
Backup Strategy: DRIVE ONLY
Last Known Activity: 2026-09-11
Role OS Tracking: Registered
Security Classification: NORMAL
Notes: Versionado por nombre de archivo (v0.1.0…v0.4.0), no por Git.

### ClaudeWidget

Type: Utility script (system tray widget)
Status: Unknown
Primary Location: `C:\Users\rolev\ClaudeWidget`
Git: No
GitHub: N/A
Backup Strategy: LOCAL ONLY
Last Known Activity: Unknown
Role OS Tracking: Registered
Security Classification: NORMAL
Notes: Candidato opcional a GIT + DRIVE, bajo esfuerzo.

### Deep-Live-Cam

Type: Experiment (herramienta open-source de terceros)
Status: Active (modificaciones locales)
Primary Location: `Drive/1 - IA PROJECTS/Deep-Live-Cam`
Git: Yes (branch `main`, 26 dirty)
GitHub: `https://github.com/hacksider/Deep-Live-Cam.git` (upstream público de terceros — NO es tuyo)
Backup Strategy: REVIEW FIRST
Last Known Activity: Unknown
Role OS Tracking: Registered
Security Classification: NORMAL
Notes: Si las modificaciones locales importan, requiere fork propio antes de depender de Git como backup — no ejecutado en Phase 2.

---

## CORPORATE

### fs_bulk

Type: IT automation script (Freshservice/CMDB)
Status: Active
Primary Location: `C:\Users\rolev\fs_bulk`
Git: No
GitHub: NOT APPROVED
Backup Strategy: REVIEW REQUIRED
Last Known Activity: Unknown
Role OS Tracking: Registered (referencia únicamente, sin contenido)
Security Classification: CORPORATE / REVIEW REQUIRED
Notes: Incluye datos de sesión de navegador (`fs_session/`). No migrar sin revisión de cumplimiento.

### OTROS - no proyectos / Unger

Type: Documentación IT corporativa (SOPs)
Status: Unknown
Primary Location: `Drive/1 - IA PROJECTS/OTROS - no proyectos/Unger`
Git: No
GitHub: NOT APPROVED
Backup Strategy: REVIEW REQUIRED
Last Known Activity: Unknown
Role OS Tracking: Registered (referencia únicamente)
Security Classification: CORPORATE / REVIEW REQUIRED
Notes: SOPs de ConnectWise Automate, acceso RDWeb/NAV Server. Ubicado dentro de la carpeta personal de proyectos de IA — fuera de lugar, revisar reubicación/eliminación con criterio propio del usuario.

### ROLE_KNOWLEDGE_OS (knowledge cards Kontoor/Unger)

Type: Legacy knowledge base (parcialmente corporativo)
Status: Legacy / probable predecesor de ROLE_OS
Primary Location: `Drive/1 - IA PROJECTS/ROLE_KNOWLEDGE_OS`
Git: No
GitHub: NOT APPROVED
Backup Strategy: REVIEW REQUIRED
Last Known Activity: Antiguo
Role OS Tracking: Registered (referencia únicamente)
Security Classification: CORPORATE / REVIEW REQUIRED
Notes: `04_KNOWLEDGE/KNOWLEDGE_CARDS/` contiene archivos con nombres que referencian Kontoor Brands (documentos clave, grabación/mensaje de llamada) y aclaración de nombre de Unger. Contenido no leído. Además es posible duplicado/legado de `ROLE_OS` (ver Duplicate/Overlap en la auditoría fuente).

### OneDrive - Kontoor Brands / OneDrive - Unger Enterprises

Type: Corporate cloud storage (propiedad del empleador)
Status: N/A
Primary Location: `C:\Users\rolev\OneDrive - Kontoor Brands`, `C:\Users\rolev\OneDrive - Unger Enterprises`
Git: N/A
GitHub: NOT APPROVED
Backup Strategy: OUT OF SCOPE
Role OS Tracking: Registered (existencia únicamente, sin exploración de contenido)
Security Classification: CORPORATE / REVIEW REQUIRED

---

## ARCHIVE / EXPERIMENTS

### SF_EEM

Type: Personal fiscal/legal documents (SAT/FIEL)
Status: Static
Primary Location: `C:\Users\rolev\SF_EEM`
Git: No
GitHub: NOT APPROVED — nunca aprobado, ni siquiera privado
Backup Strategy: REVIEW REQUIRED
Last Known Activity: Unknown
Role OS Tracking: Registered (referencia únicamente)
Security Classification: SENSITIVE
Notes: Contiene llaves privadas FIEL (`.key`) reales. Explícitamente fuera de alcance de Phase 2 y de cualquier proceso automatizado — ver regla de Phase 2.

### ROLE_KNOWLEDGE_OS (aspecto no corporativo — builder legado)

Type: Legacy builder / predecesor de ROLE_OS
Status: Legacy
Primary Location: `Drive/1 - IA PROJECTS/ROLE_KNOWLEDGE_OS`
Git: No
GitHub: N/A
Backup Strategy: DRIVE ONLY (mientras se revisa)
Role OS Tracking: Registered
Security Classification: REVIEW REQUIRED (ver también entrada en CORPORATE por las knowledge cards)
Notes: Contiene duplicado interno `ROLE_OS_BUILDER/` + `ROLE_OS_BUILDER.zip`. Candidato a archivar tras confirmar que está superado por `ROLE_OS`.

### OTROS - no proyectos / ROLE_ECOSYSTEM

Type: Posible copia obsoleta
Status: Unknown
Primary Location: `Drive/1 - IA PROJECTS/OTROS - no proyectos/ROLE_ECOSYSTEM`
Git: No
GitHub: N/A
Backup Strategy: REVIEW FIRST
Role OS Tracking: Registered
Security Classification: NORMAL
Notes: Posible duplicado del repo `role-ecosystem`. No comparado en detalle — pendiente.

### ComfyUI-Installs / ComfyUI-Shared

Type: Tool installation (no es proyecto propio)
Status: N/A
Primary Location: `C:\Users\rolev\ComfyUI-Installs`, `C:\Users\rolev\ComfyUI-Shared`
Git: No
GitHub: N/A
Backup Strategy: NO ACTION
Role OS Tracking: Registered (referencia)
Security Classification: NORMAL

### Postman

Type: App data (colecciones/exports)
Status: N/A
Primary Location: `C:\Users\rolev\Postman`
Git: No
GitHub: N/A
Backup Strategy: NO ACTION
Role OS Tracking: Registered (referencia)
Security Classification: NORMAL

---

## Second Google Drive account (not yet audited)

`My Drive (rolevaldez23@gmail.com)` — cuenta secundaria de Drive detectada pero fuera del alcance de la auditoría de 2026-09-12. Pendiente de revisión en una fase futura.

---

## Field Reference

- **Type**: categoría funcional (Software / ROLE OS / Content / Corporate / etc.)
- **Status**: Active / Inactive / Unknown
- **Primary Location**: ruta real (fuente de verdad, no copia)
- **Git**: Yes/No + branch si aplica
- **GitHub**: Private/Public/None/NOT APPROVED/PENDING
- **Backup Strategy**: SAFE / PARTIAL / LOCAL ONLY / DRIVE ONLY / GIT LOCAL ONLY / REMOTE BACKED UP / GIT + DRIVE / UNKNOWN / OUT OF SCOPE
- **Security Classification**: NORMAL / PERSONAL / SENSITIVE / CORPORATE / REVIEW REQUIRED
- **Role OS Tracking**: si este proyecto está registrado en el índice (todos lo están tras esta primera versión)
