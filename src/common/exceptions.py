class HofizError(Exception):
    """Base exception for HOFIZ BOT."""


class DownloadError(HofizError):
    """Media download failed."""


class ScraperError(HofizError):
    """Scraper could not extract media."""


class PlatformNotSupportedError(HofizError):
    """URL platform is not supported."""


class RateLimitError(HofizError):
    """User exceeded rate limit."""


class SubscriptionRequiredError(HofizError):
    """User must subscribe to required channels."""


class RecognitionError(HofizError):
    """Music recognition failed."""


class BackupError(HofizError):
    """Backup or restore operation failed."""
