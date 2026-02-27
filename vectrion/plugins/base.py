from __future__ import annotations

from abc import ABC, abstractmethod


class ExtractorPlugin(ABC):
    name = "base"

    @abstractmethod
    def extract(self, record: dict) -> dict:
        raise NotImplementedError


class NotificationPlugin(ABC):
    name = "base-notifier"

    @abstractmethod
    def draft(self, incident: dict) -> str:
        raise NotImplementedError

    def send(self, _draft: str) -> None:
        raise RuntimeError("Auto-send is disabled by policy in Vectrion MVP")
