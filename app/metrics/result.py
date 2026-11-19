from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MetricResult:
    value: Any
    status: str = "ok"
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "status": self.status, "reason": self.reason}
