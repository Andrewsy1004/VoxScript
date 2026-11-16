"""Errores de la aplicación.

Todos heredan de TranscriptorError y llevan un mensaje pensado para mostrarse
tal cual al usuario final (en español, sin trazas técnicas).
"""


class TranscriptorError(Exception):
    """Error base con un mensaje apto para el usuario."""


class ConfigError(TranscriptorError):
    """Falta configuración (API key, dependencias, etc.)."""


class MediaError(TranscriptorError):
    """El archivo no se pudo leer, no tiene audio o FFmpeg falló."""


class TranscriptionError(TranscriptorError):
    """El servicio de transcripción devolvió un error."""


class DocumentError(TranscriptorError):
    """Un documento (PDF, Word…) no se pudo leer o no tiene texto."""


class ExportError(TranscriptorError):
    """No se pudo escribir el archivo de salida."""


class CancelledError(TranscriptorError):
    """El usuario canceló el proceso."""
