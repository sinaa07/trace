import enum


class CaseStatus(str, enum.Enum):
    OPEN = "open"
    INGESTING = "ingesting"
    READY = "ready"
    INVESTIGATING = "investigating"
    CLOSED = "closed"


class SourceType(str, enum.Enum):
    SIGNAL_LOG = "signal_log"
    TRAIN_TELEMETRY = "train_telemetry"
    MAINTENANCE = "maintenance"
    WEATHER = "weather"
    WITNESS = "witness"
    OTHER = "other"


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PARSING = "parsing"
    CLEANING = "cleaning"
    COMPLETED = "completed"
    FAILED = "failed"
