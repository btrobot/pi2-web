# Standard library
import importlib
import logging
import os
import sys
import time
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

SUPPORTED_PAIRS = {("zh", "en"), ("en", "zh")}
STANZA_LANGUAGE_CODE_MAPPING = {"zt": "zh-hant", "pb": "pt"}


class TranslationError(Exception):
    """Machine translation engine failure."""


def configure_argos_environment(package_dir: str | Path | None) -> Path | None:
    """Point Argos Translate at the configured package directory before import."""

    if package_dir is None:
        _refresh_argos_runtime(_discover_argos_package_dirs(None))
        return None

    resolved_dir = Path(package_dir).expanduser().resolve()
    resolved_dir.mkdir(parents=True, exist_ok=True)
    os.environ["ARGOS_PACKAGES_DIR"] = str(resolved_dir)
    _refresh_argos_runtime(_discover_argos_package_dirs(resolved_dir))
    return resolved_dir


def _default_argos_package_dir() -> Path:
    home_dir = Path.home()
    if "SNAP" in os.environ:
        home_dir = Path(os.environ["SNAP_USER_DATA"])

    data_home = Path(os.getenv("XDG_DATA_HOME", default=home_dir / ".local" / "share"))
    return (data_home / "argos-translate" / "packages").expanduser().resolve()


def _discover_argos_package_dirs(package_dir: str | Path | None) -> list[Path]:
    package_dirs: list[Path] = []
    configured_dir = Path(package_dir).expanduser().resolve() if package_dir is not None else None

    for candidate in (configured_dir, _default_argos_package_dir()):
        if candidate is None:
            continue
        candidate.mkdir(parents=True, exist_ok=True)
        if candidate not in package_dirs:
            package_dirs.append(candidate)

    return package_dirs


def _refresh_argos_runtime(package_dirs: list[Path]) -> None:
    if not package_dirs:
        return

    try:
        settings_module = importlib.import_module("argostranslate.settings")
    except ModuleNotFoundError:
        return

    settings_module.package_data_dir = package_dirs[0]
    settings_module.package_dirs = package_dirs

    translate_module = sys.modules.get("argostranslate.translate")
    if translate_module is None:
        return

    cache_clear = getattr(translate_module.get_installed_languages, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()

    installed_translates = getattr(translate_module, "installed_translates", None)
    if isinstance(installed_translates, list):
        installed_translates.clear()


def get_argos_package_dirs(package_dir: str | Path | None) -> list[Path]:
    """Return every package directory the app will search for Argos packages."""

    return _discover_argos_package_dirs(package_dir)


def describe_argos_package_dirs(package_dir: str | Path | None) -> str:
    """Human-readable Argos package search path summary."""

    return ", ".join(str(path) for path in get_argos_package_dirs(package_dir))


def _validate_stanza_dependency(
    *,
    translation: object,
    source_lang: str,
    target_lang: str,
    allow_network: bool,
) -> str | None:
    pkg = getattr(translation, "pkg", None)
    packaged_sbd_path = getattr(pkg, "packaged_sbd_path", None)
    if pkg is None or packaged_sbd_path is None or "stanza" not in str(packaged_sbd_path):
        return None

    try:
        stanza = importlib.import_module("stanza")
        pipeline_core = importlib.import_module("stanza.pipeline.core")
        stanza_lang_code = STANZA_LANGUAGE_CODE_MAPPING.get(pkg.from_code, pkg.from_code)

        pipeline_kwargs = {
            "lang": stanza_lang_code,
            "dir": str(pkg.package_path / "stanza"),
            "processors": "tokenize",
            "logging_level": "WARNING",
        }
        if not allow_network:
            pipeline_kwargs["download_method"] = pipeline_core.DownloadMethod.NONE

        stanza.Pipeline(**pipeline_kwargs)
    except Exception as exc:  # noqa: BLE001 - convert readiness issues into a stable diagnostic
        return f"MT sentence tokenizer unavailable for {source_lang}→{target_lang}: {exc}"

    return None


def validate_mt_runtime(
    *,
    package_dir: str | Path | None,
    allow_network: bool = False,
    required_pairs: Iterable[tuple[str, str]] = SUPPORTED_PAIRS,
) -> list[str]:
    """Validate offline MT dependencies for the configured language pairs."""

    configure_argos_environment(package_dir)
    searched_dirs = describe_argos_package_dirs(package_dir)

    try:
        translate_module = importlib.import_module("argostranslate.translate")
    except ModuleNotFoundError:
        return [
            "translation engine unavailable: argostranslate is not installed in the active Python environment"
        ]

    try:
        languages = {lang.code: lang for lang in translate_module.get_installed_languages()}
    except Exception as exc:  # noqa: BLE001 - diagnostics should stay actionable
        return [f"MT runtime validation failed while enumerating installed languages: {exc}"]

    issues: list[str] = []
    for source_lang, target_lang in required_pairs:
        source = languages.get(source_lang)
        if source is None:
            issues.append(f"MT package missing source language: {source_lang} (searched: {searched_dirs})")
            continue

        target = languages.get(target_lang)
        if target is None:
            issues.append(f"MT package missing target language: {target_lang} (searched: {searched_dirs})")
            continue

        translation = source.get_translation(target)
        if translation is None:
            issues.append(
                f"MT package missing translation pair: {source_lang}→{target_lang} (searched: {searched_dirs})"
            )
            continue

        pkg = getattr(translation, "pkg", None)
        model_path = getattr(pkg, "package_path", None)
        if model_path is not None and not (Path(model_path) / "model").exists():
            issues.append(
                f"MT model directory missing for {source_lang}→{target_lang}: {Path(model_path) / 'model'}"
            )
            continue

        stanza_issue = _validate_stanza_dependency(
            translation=translation,
            source_lang=source_lang,
            target_lang=target_lang,
            allow_network=allow_network,
        )
        if stanza_issue is not None:
            issues.append(stanza_issue)

    return issues


class MTEngine:
    """Argos Translate wrapper with lazy dependency loading."""

    def __init__(self) -> None:
        self._translations: dict[tuple[str, str], object] = {}
        self._translate_module = None

    def _get_translate_module(self):
        if self._translate_module is None:
            try:
                self._translate_module = importlib.import_module("argostranslate.translate")
            except ModuleNotFoundError as exc:
                logger.error("Argos Translate dependency is missing: error=%s", str(exc))
                raise TranslationError(
                    "translation engine unavailable: argostranslate is not installed in the active Python environment"
                ) from exc
        return self._translate_module

    def _ensure_loaded(self, source_lang: str, target_lang: str) -> None:
        pair = (source_lang, target_lang)
        if pair in self._translations:
            return

        if pair not in SUPPORTED_PAIRS:
            raise TranslationError(f"unsupported language pair: {source_lang} → {target_lang}")

        logger.info("加载翻译模型: %s → %s", source_lang, target_lang)
        try:
            installed = self._get_translate_module().get_installed_languages()
            langs = {lang.code: lang for lang in installed}
            searched_dirs = describe_argos_package_dirs(os.environ.get("ARGOS_PACKAGES_DIR"))

            if source_lang not in langs:
                raise TranslationError(
                    f"source language package is not installed: {source_lang} (searched: {searched_dirs})"
                )
            if target_lang not in langs:
                raise TranslationError(
                    f"target language package is not installed: {target_lang} (searched: {searched_dirs})"
                )

            translation = langs[source_lang].get_translation(langs[target_lang])
            if translation is None:
                raise TranslationError(
                    f"translation package not found: {source_lang} → {target_lang} (searched: {searched_dirs})"
                )

            self._translations[pair] = translation
            logger.info("翻译模型加载完成: %s → %s", source_lang, target_lang)

        except TranslationError:
            raise
        except Exception as exc:
            logger.error(
                "翻译模型加载失败: %s → %s, error=%s",
                source_lang,
                target_lang,
                str(exc),
            )
            raise TranslationError(f"failed to load translation model: {source_lang} → {target_lang}") from exc

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text from source_lang to target_lang."""

        if not text or not text.strip():
            return ""

        self._ensure_loaded(source_lang, target_lang)

        start = time.monotonic()
        try:
            translation = self._translations[(source_lang, target_lang)]
            result: str = translation.translate(text)
        except TranslationError:
            raise
        except Exception as exc:
            logger.error("翻译失败: %s → %s, error=%s", source_lang, target_lang, str(exc))
            raise TranslationError(f"translation failed: {source_lang} → {target_lang}") from exc

        elapsed = time.monotonic() - start
        logger.info(
            "翻译完成: %s → %s, 耗时=%.3fs, 字符数=%d",
            source_lang,
            target_lang,
            elapsed,
            len(text),
        )
        return result
