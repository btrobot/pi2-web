# Acceptance Evidence - req1 BS bilingual UI

## Scope
This artifact closes **M4-PR3 / S4.3 - Requirements walkthrough evidence** for branch `feature/req1-bs-bilingual-ui`.

The required outcome for this slice is:
- a walkthrough record for all **12 leaf modes**
- coverage for **recordings** and **history**
- confirmation that the shell remains valid in **zh-CN** and **en-US**

## Honesty note
This Codex lane runs in a **headless local environment**. The walkthrough record below is therefore an **evidence-backed acceptance ledger** rather than a screenshot-only human click log.

The ledger is still grounded in fresh local verification:
- exact req/plan sources
- concrete UI/template anchors
- fresh pytest runs executed during M4-PR3
- existing storage/API/system tests that already model the required end-to-end behaviors

## Source-of-truth inputs
- Requirements: `reqs/req-1.md`
- UI/menu requirements: `reqs/ui-menu.md`
- Frozen plan: `.omx/plans/ralplan-req1-bs-bilingual-ui.md`
- Test strategy: `.omx/plans/test-spec-req1-bs-bilingual-ui.md`
- Traceability: `.omx/plans/traceability-req1-bs-bilingual-ui.md`
- Execution slices: `.omx/plans/slices-req1-bs-bilingual-ui.md`

## Fresh verification executed for this slice
Run on `2026-04-18` UTC during M4-PR3:

1. `pytest tests/test_api.py::test_text_conversion_returns_frozen_record_and_result_dto tests/test_api.py::test_speech_conversion_accepts_audio_upload_and_returns_frozen_dto tests/test_api.py::test_speech_conversion_accepts_recording_id_reuse tests/test_api.py::test_bootstrap_i18n_contains_mode_labels_for_all_leaf_modes tests/test_api.py::test_bootstrap_i18n_keeps_bilingual_labels_human_readable -q`
   - Result: **15 passed**
2. `pytest tests/test_api.py::test_recent_history_returns_latest_three_summary_items tests/test_api.py::test_history_returns_latest_five_full_items tests/test_api.py::test_delete_history_returns_unified_delete_dto tests/test_api.py::test_export_history_returns_frozen_zip_structure tests/test_api.py::test_create_recording_accepts_wav_upload_and_returns_frozen_item tests/test_api.py::test_list_recordings_returns_latest_five_frozen_items tests/test_api.py::test_delete_recording_returns_unified_delete_dto tests/test_api.py::test_export_recordings_returns_frozen_zip_structure -q`
   - Result: **8 passed**
3. `pytest tests/test_pipeline.py::test_mode_registry_contains_exactly_12_leaf_modes tests/test_pipeline.py::test_run_pipeline_dispatches_all_frozen_mode_keys tests/test_pipeline.py::test_run_composite_mode_mt_does_not_emit_audio tests/test_pipeline.py::test_run_composite_mode_asr_mt_tts_returns_text_and_audio tests/test_pipeline.py::test_same_language_modes_do_not_add_translation_output -q`
   - Result: **16 passed**
4. `pytest tests/test_system.py -q`
   - Result: **14 passed**

These runs provide the fresh acceptance proof for this slice; the final Ralph closeout also reruns the full suite.

## Shell and bilingual walkthrough ledger
| Area | Requirement expectation | Evidence anchor | Status |
|---|---|---|---|
| Header | Logo + help + settings + language switch | `tests/test_system.py::test_root_route_exposes_shell_navigation_and_header_controls`; `api/templates/index.html` uses `#header-language-button` with `data-i18n="header.language_switch"` | Pass |
| Sidebar | 6 mode groups + recordings + history | `tests/test_system.py::test_root_route_exposes_shell_navigation_and_header_controls` | Pass |
| Breadcrumb | Current location + active group/leaf mode | `tests/test_system.py::test_root_route_renders_req1_shell_landmarks`; `api/templates/index.html` breadcrumb shell | Pass |
| Main shell | input / control / output / recent history panels | `tests/test_system.py::test_root_route_renders_req1_shell_landmarks` | Pass |
| Help panel | help entry and panel content shell | `tests/test_system.py::test_root_route_exposes_help_settings_and_locale_polish_controls`; `api/templates/index.html` help panel nodes | Pass |
| Settings panel | locale controls + constraint summary | `tests/test_system.py::test_root_route_exposes_help_settings_and_locale_polish_controls`; `api/templates/index.html` `#settings-locale-zh` / `#settings-locale-en` | Pass |
| Locale bootstrap | both locales ship through bootstrap | `tests/test_api.py::test_bootstrap_returns_atomic_contract`; `tests/test_api.py::test_bootstrap_i18n_contains_required_shell_and_text_flow_keys` | Pass |
| Locale completeness | all leaf modes have zh-CN and en-US labels | `tests/test_api.py::test_bootstrap_i18n_contains_mode_labels_for_all_leaf_modes` | Pass |
| Human-readable CN/EN labels | representative bilingual labels are stable and non-empty | `tests/test_api.py::test_bootstrap_i18n_keeps_bilingual_labels_human_readable` | Pass |
| Runtime locale switch | shell JS toggles locale and re-renders from bootstrap i18n | `api/templates/index.html` functions `setLocale`, `toggleLocale`, `getMessage`; `document.documentElement.lang = state.locale` | Pass |

## 12 leaf modes walkthrough ledger
Each row below is accepted only if all of the following are true:
- mode exists in the frozen 12-mode registry
- bootstrap exposes the mode in both locales
- the correct text/speech conversion route is covered
- the pipeline semantics match the required input/output shape
- history persistence remains compatible with the mode's artifact shape

| mode_key | req-1 item | Direction / shape | Fresh evidence | Status |
|---|---|---|---|---|
| `tts_zh_zh` | 3 | zh text -> zh audio | `test_text_conversion_returns_frozen_record_and_result_dto`; `test_run_pipeline_dispatches_all_frozen_mode_keys` | Pass |
| `tts_en_en` | 3 | en text -> en audio | `test_text_conversion_returns_frozen_record_and_result_dto`; `test_run_pipeline_dispatches_all_frozen_mode_keys` | Pass |
| `asr_zh_zh` | 2 | zh audio -> zh text | `test_speech_conversion_accepts_audio_upload_and_returns_frozen_dto`; `test_run_pipeline_dispatches_all_frozen_mode_keys` | Pass |
| `asr_en_en` | 2 | en audio -> en text | `test_speech_conversion_accepts_audio_upload_and_returns_frozen_dto`; `test_run_pipeline_dispatches_all_frozen_mode_keys` | Pass |
| `mt_tts_zh_en` | 5 | zh text -> en audio | `test_text_conversion_returns_frozen_record_and_result_dto`; `test_run_pipeline_dispatches_all_frozen_mode_keys` | Pass |
| `mt_tts_en_zh` | 5 | en text -> zh audio | `test_text_conversion_returns_frozen_record_and_result_dto`; `test_run_pipeline_dispatches_all_frozen_mode_keys` | Pass |
| `asr_mt_zh_en` | 4 | zh audio -> en text | `test_speech_conversion_accepts_audio_upload_and_returns_frozen_dto`; `test_run_pipeline_dispatches_all_frozen_mode_keys` | Pass |
| `asr_mt_en_zh` | 4 | en audio -> zh text | `test_speech_conversion_accepts_audio_upload_and_returns_frozen_dto`; `test_run_pipeline_dispatches_all_frozen_mode_keys` | Pass |
| `mt_zh_en` | 1 | zh text -> en text | `test_text_conversion_returns_frozen_record_and_result_dto`; `test_run_composite_mode_mt_does_not_emit_audio` | Pass |
| `mt_en_zh` | 1 | en text -> zh text | `test_text_conversion_returns_frozen_record_and_result_dto`; `test_run_composite_mode_mt_does_not_emit_audio` | Pass |
| `asr_mt_tts_zh_en` | 6 | zh audio -> en speech (+ text artifact) | `test_speech_conversion_accepts_audio_upload_and_returns_frozen_dto`; `test_run_composite_mode_asr_mt_tts_returns_text_and_audio` | Pass |
| `asr_mt_tts_en_zh` | 6 | en audio -> zh speech (+ text artifact) | `test_speech_conversion_accepts_audio_upload_and_returns_frozen_dto`; `test_run_composite_mode_asr_mt_tts_returns_text_and_audio` | Pass |

## Mode-label walkthrough record for CN and EN
| Requirement | Evidence anchor | Status |
|---|---|---|
| All 12 mode labels exist in `zh-CN` | `tests/test_api.py::test_bootstrap_i18n_contains_mode_labels_for_all_leaf_modes` | Pass |
| All 12 mode labels exist in `en-US` | `tests/test_api.py::test_bootstrap_i18n_contains_mode_labels_for_all_leaf_modes` | Pass |
| Representative zh-CN labels remain human-readable | `tests/test_api.py::test_bootstrap_i18n_keeps_bilingual_labels_human_readable` | Pass |
| Representative en-US labels remain human-readable | `tests/test_api.py::test_bootstrap_i18n_keeps_bilingual_labels_human_readable` | Pass |

## Recordings walkthrough ledger
| Requirement | Evidence anchor | Status |
|---|---|---|
| Standalone recording create route works | `tests/test_api.py::test_create_recording_accepts_wav_upload_and_returns_frozen_item` | Pass |
| Recording list caps at latest 5 | `tests/test_api.py::test_list_recordings_returns_latest_five_frozen_items`; `tests/test_storage.py::TestRecordingManager::test_fifo_eviction_removes_oldest_recording_file` | Pass |
| 180-second limit enforced | `tests/test_api.py::test_create_recording_rejects_upload_longer_than_max_record_seconds` | Pass |
| Recording audio playback/download route works | `tests/test_api.py::test_create_recording_accepts_wav_upload_and_returns_frozen_item` (`GET /api/recordings/{id}/audio`) | Pass |
| Recording delete contract works | `tests/test_api.py::test_delete_recording_returns_unified_delete_dto` | Pass |
| Recording export ZIP works | `tests/test_api.py::test_export_recordings_returns_frozen_zip_structure`; `tests/test_storage.py::TestRecordingManager::test_export_all_contains_metadata_and_recording_files` | Pass |
| Recording reuse into speech conversion works | `tests/test_api.py::test_speech_conversion_accepts_recording_id_reuse`; `tests/test_system.py::test_root_route_exposes_recording_reuse_mode_picker_contract`; `api/templates/index.html` requires speech-mode selection before `recording_id` submission | Pass |

## History walkthrough ledger
| Requirement | Evidence anchor | Status |
|---|---|---|
| Recent history shows latest 3 | `tests/test_api.py::test_recent_history_returns_latest_three_summary_items` | Pass |
| Full history shows latest 5 groups | `tests/test_api.py::test_history_returns_latest_five_full_items` | Pass |
| History manifests and artifacts exist per record set | `tests/test_storage.py::TestHistoryManager::test_add_record_creates_manifest_directory`; `tests/test_storage.py::TestHistoryManager::test_optional_artifact_combinations_follow_mode_shape` | Pass |
| History artifact routes serve text/audio/manifest | `tests/test_api.py::test_history_artifact_routes_serve_text_and_manifest_files` | Pass |
| History delete contract works | `tests/test_api.py::test_delete_history_returns_unified_delete_dto`; `tests/test_storage.py::TestHistoryManager::test_delete_record_removes_entire_group_and_index` | Pass |
| History export ZIP works | `tests/test_api.py::test_export_history_returns_frozen_zip_structure`; `tests/test_storage.py::TestHistoryManager::test_export_all_contains_index_manifests_and_artifacts` | Pass |
| History FIFO keeps only latest sets | `tests/test_storage.py::TestHistoryManager::test_fifo_eviction_removes_full_oldest_record_directory` | Pass |
| Full-history UI affordances exist | `tests/test_system.py::test_root_route_exposes_history_ui_controls`; `api/templates/index.html` wires `#history-view-all-button` and full-history section | Pass |

## UI interaction walkthrough record
| Flow | Evidence anchor | Status |
|---|---|---|
| Text mode picker exists and is localized from bootstrap | `tests/test_system.py::test_root_route_exposes_text_mode_controls`; `api/templates/index.html` `#text-mode-picker` | Pass |
| Text input supports direct entry + `.txt` upload | `tests/test_system.py::test_root_route_exposes_text_mode_controls`; `api/templates/index.html` `#text-upload-input` + `handleTextUpload` | Pass |
| Speech input supports browser recording + WAV upload | `tests/test_system.py::test_root_route_exposes_speech_mode_controls`; `api/templates/index.html` `handleRecordStart`, `handleRecordStop`, `handleSpeechUpload` | Pass |
| Speech input surfaces recordings library reuse button | `api/templates/index.html` `#speech-recordings-list` + `speech.use_recording` button template | Pass |
| Recording reuse forces a 6-mode speech picker before submit | `tests/test_system.py::test_root_route_exposes_recording_reuse_mode_picker_contract`; `api/templates/index.html` `SPEECH_REUSE_MODE_KEYS` + delayed `recording_id` submit | Pass |
| History management supports open/delete/export | `tests/test_system.py::test_root_route_exposes_history_ui_controls`; `api/templates/index.html` history action wiring | Pass |

## Acceptance conclusion
M4-PR3 is accepted for this repo state because:
- all 12 req-1 leaf modes have fresh conversion + registry proof
- zh-CN and en-US shell labels are complete and anchored to bootstrap
- recording and history requirements have fresh CRUD/export/FIFO evidence
- the BS shell still exposes the required help/settings/history/locale controls
- the ledger is now stored as a durable OMX artifact instead of remaining implicit in scattered tests

## Residual note
This slice does **not** claim pixel-perfect screenshot proof. It closes the required walkthrough evidence in the current headless delivery lane by turning the accepted test/contract surface into one explicit acceptance record.
