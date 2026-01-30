"""Limites e constantes para validação de mensagens WhatsApp/Meta."""

# Limites de tamanho por tipo (caracteres/bytes)
MAX_TEXT_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024
MAX_BUTTON_TEXT_LENGTH = 20
MAX_LIST_ITEMS = 10
MAX_BUTTONS_PER_MESSAGE = 3
MAX_FILE_SIZE_MB = 100
MAX_TEMPLATE_NAME_LENGTH = 512
MAX_IDEMPOTENCY_KEY_LENGTH = 255

# Tipos MIME suportados por categoria
SUPPORTED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png"})

SUPPORTED_VIDEO_TYPES = frozenset({"video/mp4", "video/3gpp"})

SUPPORTED_AUDIO_TYPES = frozenset(
    {
        "audio/aac",
        "audio/mp4",
        "audio/amr",
        "audio/ogg",
    }
)

SUPPORTED_DOCUMENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/msword",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
)
