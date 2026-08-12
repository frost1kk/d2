# Changelog

Все значимые изменения проекта. Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).

## [Unreleased]

### Added
- 🎯 **Скелет бота** для мини-игры «Сапожный снос»:
  - `src/config.py` — пороги детекции (HSV), геометрия поля (ROI-соотношения), клавиши,
    мёртвая зона, бюджет цикла. Значения детекции — первый прикид с опорных кадров.
  - `src/track.py` — предсказание точки падения сапога с отскоками (`reflect_1d`,
    `predict_landing_x`, `BootTracker`). Чистая математика, без OpenCV.
  - `src/control.py` — управляющая логика с гистерезисом (`decide_direction`, `Controller`).
  - `src/detect.py` — детекция поля/тележки/сапога (OpenCV, HSV-маски) + отладочная разметка.
  - `src/capture.py` — захват через dxcam + CLI `--save` для опорных кадров.
  - `src/input.py` — эмуляция ввода (pydirectinput, удержание стрелок, гарантированный release).
  - `src/main.py` — управляющий цикл + kill-switch (F12 / Ctrl+C).
  - `debug/overlay_frame.py` — оффлайн-проверка детекции на сохранённом кадре.
- ✅ **Юнит-тесты** чистой логики (`tests/test_track.py`, `tests/test_control.py`) — 26 тестов,
  все зелёные. Покрывают отскоки, предсказание, трекер, управление, edge-кейсы.
- 📄 Документация: `README.md`, `LOGIC.md`, `ARCHITECTURE.md`, `BACKLOG.md`, `ROADMAP.md`.
- 🔧 `requirements.txt`.

### Примечание
- Модули `detect`/`capture`/`input`/`main` написаны, но **ещё не валидированы** на реальных
  кадрах / вживую. HSV-пороги детекции требуют настройки — см. [BACKLOG.md](BACKLOG.md).

## [0.0.0] - 2026-08-12

### Added
- Инициализация репозитория: правила работы (`CLAUDE.md`), скиллы (`executor-expert`,
  `docs-maintainer`), `.gitignore`.
