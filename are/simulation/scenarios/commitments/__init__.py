"""
Commitment tracking scenarios for testing
obligation management across multiple turns.
"""

from are.simulation.scenarios.commitments.scenario import (
    CommitmentTrackingScenario,
)

__all__ = ["CommitmentTrackingScenario"]

# are-run -s commitment_tracking -a responses --model gpt-5-mini --model_provider openai
# https://facebookresearch.github.io/meta-agents-research-environments/tutorials/working_with_scenarios.html