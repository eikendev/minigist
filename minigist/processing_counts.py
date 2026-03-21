"""Shared processing counters for pipeline workers."""

from dataclasses import dataclass


@dataclass
class ProcessingCounts:
    """Track processed and failed entry counts."""

    processed: int = 0
    failed: int = 0

    def increment_processed(self) -> None:
        """Increment the processed entry count."""

        self.processed += 1

    def increment_failed(self) -> None:
        """Increment the failed entry count."""

        self.failed += 1
