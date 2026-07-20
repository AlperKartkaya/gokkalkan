# AGENTS.md

This file is the first-stop guide for AI coding agents working in the Gökkalkan repository. Read it before editing anything.

## Project identity

Gökkalkan is the software-development and report-preparation workspace for the TEKNOFEST 2026 Çelikkubbe Hava Savunma Sistemleri Yarışması. It is not yet an implementation-heavy codebase: the main software directories exist mostly as scaffolding, while the clearest source of truth is currently the documentation.

The competition specification is the final authority. If any repository note, initializer report, or older README statement conflicts with the competition specification, i.e., `docs/sartname_v5.pdf` and its text file `docs/sartname_v5.txt`, follow the competition specification and update the repo note instead of preserving the conflict.

Primary references:
- `README.md` — short project/team/delivery overview.
- `docs/sartname_v5.pdf` — authoritative competition specification.
- `docs/sartname_v5.txt` — searchable text extraction of the same specification; use it for grep/search, then refer back to the PDF when exact formatting or figures matter.
- `docs/tech_stack.md` — competition specification-aligned software architecture, technology direction, mission stages, safety constraints, and verification priorities.
- `TARIHLER.md` — fixed delivery/result dates.
- `reports/` — report artifacts and templates.
- `.github/ISSUE_TEMPLATE/` — team workflow expectations for handovers, features, and bug reports.

## Current repository state

Treat this repository as documentation-first and scaffold-first until real source files are added.

Directory map:
- `backend/` — planned mission/core logic and hardware communication area. `backend/src/` is currently a placeholder.
- `backend/hardware_mock/` — planned hardware simulation/mock area for development without real devices.
- `frontend/` — planned operator GUI area. `frontend/src/` and `frontend/assets/` are currently placeholders.
- `perception/` — planned camera, inference, tracking, and model area. `perception/src/` and `perception/models/` are currently placeholders.
- `tests/` — planned automated test area; currently placeholder-only.
- `software/` — reserved placeholder; no clear responsibility yet.
- `docs/` — architecture and competition reference documents.
- `reports/` — OTR/KTR report material and templates.

Do not assume production code exists just because a directory exists. Check whether the relevant folder contains real files or only `.gitkeep` before making implementation decisions.

## Domain glossary

- **TEKNOFEST Çelikkubbe** — the competition context. Requirements and deliverables should be interpreted through the competition specification in `docs/sartname_v5.pdf`.
- **Gökkalkan** — this team/project’s air-defense-system workspace.
- **Şartname** — `docs/sartname_v5.pdf`; the binding TEKNOFEST technical specification for this repo.
- **OTR** — `Ön Tasarım Raporu` (Preliminary Design Report). The şartname says it is at most 10 pages including cover, contents, visuals, and references.
- **KTR** — `Kritik Tasarım Raporu` (Critical Design Report). The şartname says it is at most 30 pages including cover, contents, technical visuals, and references.
- **Görev Kabiliyeti Gösterimi Videosu** — post-KTR video gate. The şartname requires a single YouTube link, at least 720p, 2–5 minutes, and the required capabilities in order.
- **WP-01 Manuel Mod** — manual mode work package.
- **WP-02 Otonom Tespit ve Takip** — autonomous detection and tracking work package.
- **WP-03 Dost-Düşman + Menzil** — friend/foe plus range-related work package.
- **WP-04 Güvenlik Katmanı** — safety-layer work package.
- **WP-05 Log/Telemetri** — logging and telemetry work package.

When writing issues, reports, or user-facing documentation, preserve these Turkish terms unless the task explicitly asks for translation.

## Planned architecture and technology direction

The planned system communicates with lower-level hardware and must satisfy the mission stages and safety constraints in the şartname. The current technical direction in `docs/tech_stack.md` is:

1. **Perception** — camera frames are processed into target candidates, tracks, target type/dost-düşman information, and range-related decisions as needed by the active stage.
2. **Mission logic** — manual/otonom mode control, stage state machines, scoring-relevant events, and target priorities are handled in the backend.
3. **Safety gate** — movement and firing are blocked unless emergency stop, forbidden movement area, forbidden firing area, mode, and operator/hakem constraints allow them.
4. **Hardware action** — validated commands go to pan/tilt and the non-explosive target-imha mechanism; mocks should be used before real hardware assumptions.
5. **UI and telemetry** — the operator UI displays mode, live view, target state, safety locks, stage/tour/time information, and records evidence for KTR/video/report use.

Documented stack direction:
- Python is the primary expected implementation language.
- GUI: React / Vite (Web technologies wrapped for desktop if needed).
- Perception: OpenCV first; Picamera2, model files, Hailo, YOLO, or DeepSORT-style approaches only when justified by real target data and latency/accuracy needs.
- Communication: `pySerial` and/or `python-can` depending on the MCU interface; ROS2 is optional unless the project actually adds a ROS workspace.
- Testing: pytest.
- Possible native/robotics build artifacts: ROS2/colcon/CMake are reflected in `.gitignore`, but no build setup exists yet.

## Language and naming conventions

- Existing project documentation is mostly Turkish. Keep report-facing and competition-facing prose in Turkish by default.
- Use correct Turkish letters in Turkish text: `Ç/ç`, `Ğ/ğ`, `İ`, `I/ı`, `Ö/ö`, `Ş/ş`, `Ü/ü`. Do not write ASCII approximations such as `sartname`, `gorev`, `guvenlik`, or `tasarim` in prose when the Turkish spelling is `şartname`, `görev`, `güvenlik`, or `tasarım`. File names may remain ASCII when already established, for example `docs/sartname_v5.pdf`.
- Use exact Turkish competition terms for deliverables and work packages: `OTR`, `KTR`, `Manuel Mod`, `Otonom Tespit ve Takip`, `Güvenlik Katmanı`, `Log/Telemetri`.
- For source code that will be added later, prefer clear English identifiers unless an existing file or external interface establishes a Turkish name.
- When documenting mixed-language concepts, Turkish first and English clarification second is usually best, for example: `Algı (Perception)`.

## Workflow expectations for agents

Before changing code or docs:
1. Read `docs/sartname_v5.txt` or `docs/sartname_v5.pdf` for requirement-sensitive tasks; treat the şartname as final authority.
2. Read `docs/tech_stack.md` for architecture-sensitive tasks after checking the şartname.
3. Read `TARIHLER.md` for delivery-sensitive report tasks.
4. Read the relevant `.github/ISSUE_TEMPLATE/` file when the task resembles a handover, feature, or bug.
5. Confirm whether the target directory contains implementation or only placeholders.

For feature work:
- Map the work to the closest WP label when possible.
- Keep the module split intact: perception logic in `perception/`, mission/hardware logic in `backend/`, GUI logic in `frontend/`, tests in `tests/`.
- Implement safety as an explicit gate, not as UI-only warnings: emergency stop, movement-forbidden area, firing-forbidden area, mode state, and target/range constraints must be enforceable in backend logic.
- Do not add large binaries, generated telemetry, recordings, or model weights to git. `.gitignore` excludes common Hailo/YOLO model formats, videos, logs, CSV telemetry, and most images.
- If model files are necessary, document where to obtain them instead of committing heavy binaries unless the team explicitly decides to use Git LFS.

For report/documentation work:
- KTR/OTR content must align with the competition specification. Do not treat `reports/Gökkalkan Ön Tasarım Raporu.docx` as binding architecture; it is an initializer artifact unless the user says otherwise.
- Keep deadline-sensitive statements synchronized with `TARIHLER.md`.
- Avoid inventing measurements, test results, or hardware capabilities. Mark uncertain items as assumptions or TODOs.

## Commands and verification

There is now a root-level `package.json` only for lightweight npm script proxies into `frontend/` (for example `npm run desktop`, `npm run desktop:check`, `npm run test:competition`, `npm run build`). Python packaging, root dependency installation, `pyproject.toml`, `requirements.txt`, `Makefile`, `Dockerfile`, and a root test-runner configuration are still not present. Do not claim additional standard commands exist until they are added.

When code is added later, prefer verification in this order:
1. Run the narrowest relevant test first.
2. Run pytest for Python changes once a pytest setup exists.
3. Run ROS2/colcon/CMake commands only if the relevant workspace/configuration has been added.
4. Manually exercise hardware-facing behavior with mocks before assuming real-device behavior.

For documentation-only changes, verify by re-reading the changed file and checking `git diff` for accidental product-code changes.

## Safety notes

This project targets a physical air-defense-style system with motors, camera inference, safety checks, and a firing mechanism. Treat safety-related code and documentation conservatively:
- Keep safety checks explicit and testable.
- Do not bypass safety layers for convenience.
- Prefer mocks/simulation in `backend/hardware_mock/` before any real hardware assumption.
- Bug reports should include hardware, OS, connection, and power-state context when relevant.
