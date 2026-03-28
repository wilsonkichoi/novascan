from typing import Any

import aws_cdk as cdk
from constructs import Construct

from cdkconstructs.storage import StorageConstruct
from cdkconstructs.auth import AuthConstruct
from cdkconstructs.api import ApiConstruct
from cdkconstructs.pipeline import PipelineConstruct
from cdkconstructs.frontend import FrontendConstruct


class NovascanStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        stage: str,
        config: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.storage = StorageConstruct(self, "Storage", stage=stage, config=config)
        self.auth = AuthConstruct(self, "Auth", stage=stage, config=config)
        self.api = ApiConstruct(self, "Api", stage=stage, config=config)
        self.pipeline = PipelineConstruct(self, "Pipeline", stage=stage, config=config)
        self.frontend = FrontendConstruct(self, "Frontend", stage=stage, config=config)
