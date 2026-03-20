"""Agent Swarm — The agent engine that learns.

Install-and-run, zero dependencies, every feature tested.

    from agent_swarm import Swarm
    result = await Swarm(llm=my_llm).run("Research AI trends")
"""
__version__ = "1.0.0"

from .core import (
    Swarm, Agent, SubTask, TaskResult, RunContext,
    PlanTier, SwarmPlan, AgentConfig, DEFAULT_CONFIGS,
    SwarmEvent, FailPolicy, TaskStatus,
    LLMCallback, ApprovalCallback,
    run_sync, score_plan_quality,
    _topological_waves, _safe_truncate,
)
from .models import (
    Handoff, Ticket, GoalAncestry, BudgetPolicy,
    OrgNode, OrgRole, HeartbeatConfig,
)
from .validation import (
    Validator, LengthValidator, SchemaValidator, MultiValidator, ValidationError,
    SCHEMA_PRESETS,
)
from .metrics import MetricsCollector, Tracer, Span
from .session import SessionStore, InMemorySessionStore
from .skills import (
    Skill, SkillBank, SkillState, SkillType, SkillManifest,
    SkillPreamble, SkillChain, SkillSuggestor, SkillSuggestion,
    FailureCluster, PERSISTENCE_VERSION,
)
from .telemetry import TelemetryEvent, TelemetryWriter, TelemetryReader
from .ontology import (
    OntologyTerm, OntologyRelation, OntologyBundle,
    OntologyRegistry, OntologyGateMode, OntologyViolation, ValidationReport,
    CORE_ONTOLOGY,
)
from .playbooks import (
    SOPStep, SOPPlaybook, BUILTIN_PLAYBOOKS,
)
from .genetics import (
    SkillGenetics, FitnessWeights, LineageRecord,
    compute_fitness, adversarial_test, crossover, tournament_select,
    TournamentMatch, ADVERSARIAL_CHALLENGES,
)
from .packs import PackManager, PackMetadata
from .progress import ProgressDisplay
from .events import EventBus, Event, HttpEventBridge, get_event_bus, set_event_bus
from .cache import LLMCache, cached_llm
from .router import SmartRouter
from .tools import Tool, ToolRegistry, BUILTIN_TOOLS, SAFE_TOOLS, DEFAULT_REGISTRY, web_search, http_fetch, file_read, file_write, shell_exec, json_parse
from .memory import MemoryStore, Memory
from .streaming import StreamingAdapter, StreamCollector, streaming_print
from .durable import DurableCheckpoint
from .tracing import DetailedTracer, Trace, TraceNode
from .run_machine import RunMachine, RunState, Run, RunConfig, ProofBundle, StateTransition, ReviewGate, ReviewResult, SpecGate
from .workspace import WorkspaceManager, Workspace
from .tracker import TrackerAdapter, TriggerEvent, TriggerFilter, LabelFilter
from .supervisor import Supervisor, SupervisorConfig
from .migrate import WorkspaceExporter, WorkspaceImporter, WorkspaceBundle
from .pro_client import ProClient, ProClientError
from .llm_connectors import openai, claude, ollama, litellm, vllm
from .auto_tools import auto_tools
from .result_export import save_result
from .skill_eval import SkillEvaluator, SkillEvalReport, SkillDelta, evaluate_skill_focus
from .context_diversity import ContextDiversityScorer, exclude_self_context, diversity_report
from .vllm_presets import get_preset, list_presets, vllm_optimized, PRESETS
from .attention import AttentionMap, AttentionMapBuilder, softmax, rmsnorm_score
from .review import (
    ReviewRole, ReviewStage, ReviewPipeline, ReviewPipelineResult, ReviewResult as PipelineReviewResult,
)
from .context_filter import ContextFilter, ContextPolicy
from .safety import CarefulGuard, FreezeGuard, GuardChain, GuardAction, GuardResult
from .qa import (
    IssueSeverity, IssueCategory, QAIssue, HealthScore, QAReport, QAReviewGate,
)
from .retro import Retro, RetroReport
from .ship import ShipPipeline, ShipConfig, ShipStage, ShipStatus, ShipResult, ShipCheckpoint
from .templates import (
    Template, TemplateSection, TemplateRenderer,
    QA_REPORT, TODO_LIST, DESIGN_REVIEW, RETRO_REPORT,
)
