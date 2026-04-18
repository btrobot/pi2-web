# Standard library
import logging
import time

# Third-party
import argostranslate.translate

logger = logging.getLogger(__name__)

SUPPORTED_PAIRS = {("zh", "en"), ("en", "zh")}


class TranslationError(Exception):
    """翻译引擎异常"""


class MTEngine:
    """Argos Translate 机器翻译引擎，按需加载语言对模型。"""

    def __init__(self) -> None:
        self._translations: dict[tuple[str, str], object] = {}

    def _ensure_loaded(self, source_lang: str, target_lang: str) -> None:
        pair = (source_lang, target_lang)
        if pair in self._translations:
            return

        if pair not in SUPPORTED_PAIRS:
            raise TranslationError(
                "不支持的语言对: %s → %s" % (source_lang, target_lang)
            )

        logger.info("加载翻译模型: %s → %s", source_lang, target_lang)
        try:
            installed = argostranslate.translate.get_installed_languages()
            langs = {lang.code: lang for lang in installed}

            if source_lang not in langs:
                raise TranslationError("未安装源语言包: %s" % source_lang)
            if target_lang not in langs:
                raise TranslationError("未安装目标语言包: %s" % target_lang)

            translation = langs[source_lang].get_translation(langs[target_lang])
            if translation is None:
                raise TranslationError(
                    "未找到翻译包: %s → %s" % (source_lang, target_lang)
                )

            self._translations[pair] = translation
            logger.info("翻译模型加载完成: %s → %s", source_lang, target_lang)

        except TranslationError:
            raise
        except Exception as e:
            logger.error(
                "翻译模型加载失败: %s → %s, error=%s", source_lang, target_lang, str(e)
            )
            raise TranslationError(
                "加载模型失败: %s → %s" % (source_lang, target_lang)
            ) from e

    def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """翻译文本。

        Args:
            text: 待翻译文本
            source_lang: 源语言代码，如 "zh" 或 "en"
            target_lang: 目标语言代码，如 "zh" 或 "en"

        Returns:
            翻译结果字符串

        Raises:
            TranslationError: 语言对不支持、模型未安装或翻译失败时
        """
        if not text or not text.strip():
            return ""

        self._ensure_loaded(source_lang, target_lang)

        start = time.monotonic()
        try:
            translation = self._translations[(source_lang, target_lang)]
            result: str = translation.translate(text)
        except TranslationError:
            raise
        except Exception as e:
            logger.error(
                "翻译失败: %s → %s, error=%s", source_lang, target_lang, str(e)
            )
            raise TranslationError("翻译失败: %s → %s" % (source_lang, target_lang)) from e

        elapsed = time.monotonic() - start
        logger.info(
            "翻译完成: %s → %s, 耗时=%.3fs, 字符数=%d",
            source_lang,
            target_lang,
            elapsed,
            len(text),
        )
        return result
