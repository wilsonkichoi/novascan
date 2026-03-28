from typing import Any

from constructs import Construct


class ApiConstruct(Construct):
    def __init__(
        self, scope: Construct, id: str, *, stage: str, config: dict[str, Any], **kwargs: Any
    ) -> None:
        super().__init__(scope, id, **kwargs)
