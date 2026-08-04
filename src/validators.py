from pydantic import BaseModel, Field
from typing import List


class SandboxConfig(BaseModel):
    """Sandbox configuration for student solutions.
    Uses allowlist approach: only imports in authorized_imports are allowed.
    Everything else is blocked by default.
    """

    authorized_imports: List[str] = Field(default_factory=lambda: [
        "math", "math.*",
        "collections", "collections.*",
        "itertools", "re", "json",
        "typing", "typing.*",
        "functools", "operator",
        "heapq", "bisect", "copy",
        "string", "random",
        "datetime", "datetime.*",
        "array", "cmath",
    ])
    allowed_directories: List[str] = Field(default_factory=lambda: [
        "/testbed", "/tmp/agent"
    ])
    max_execution_time_seconds: int = 30
    max_memory_mb: int = 512


class MBPPTaskInput(BaseModel):
    """Input for MBPP task validation."""
    pass


class SWEBenchTaskInput(BaseException):
    """Input for SWEBench task validation."""
    pass


class StepMetrics(BaseModel):
    """Input for StepMetrics task validation."""
    pass


class SolutionOutput(BaseModel):
    """Output for solution validation."""
    pass
