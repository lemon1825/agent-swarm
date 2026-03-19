"""Workspace Export/Import — migrate local data to Pro hosted.

Export collects all local agent-swarm data into a single JSON file.
Import (Pro-only) restores that data on the hosted server.

Usage:
    # Export from local
    python -m agent_swarm export --output my_workspace.json

    # Or programmatically
    from agent_swarm.migrate import WorkspaceExporter
    exporter = WorkspaceExporter()
    exporter.export("my_workspace.json")
"""

__all__ = ['WorkspaceExporter', 'WorkspaceImporter', 'WorkspaceBundle']

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class WorkspaceBundle:
    """All exportable data from a local agent-swarm installation."""
    version: str = "1.0.0"
    exported_at: float = field(default_factory=time.time)
    source: str = "local"  # local, hosted

    # Skills
    skills: List[Dict] = field(default_factory=list)
    skill_genetics: List[Dict] = field(default_factory=list)

    # Memory
    memories: List[Dict] = field(default_factory=list)

    # Ontology (custom additions)
    custom_ontology_terms: List[Dict] = field(default_factory=list)

    # Run history (recent)
    recent_runs: List[Dict] = field(default_factory=list)

    # Settings
    settings: Dict = field(default_factory=dict)

    # Packs (user-installed)
    installed_packs: List[str] = field(default_factory=list)

    # Stats
    total_runs: int = 0
    total_tokens: int = 0
    total_skills_evolved: int = 0

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent, ensure_ascii=False, default=str)

    @classmethod
    def from_json(cls, data: str) -> 'WorkspaceBundle':
        d = json.loads(data)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def summary(self) -> str:
        return (
            f"Workspace Bundle v{self.version}\n"
            f"  Skills: {len(self.skills)}\n"
            f"  Memories: {len(self.memories)}\n"
            f"  Genetics: {len(self.skill_genetics)} lineage records\n"
            f"  Custom ontology: {len(self.custom_ontology_terms)} terms\n"
            f"  Recent runs: {len(self.recent_runs)}\n"
            f"  Packs: {', '.join(self.installed_packs) if self.installed_packs else 'none'}\n"
            f"  Total runs: {self.total_runs}\n"
            f"  Total tokens: {self.total_tokens:,}\n"
            f"  Exported: {time.strftime('%Y-%m-%d %H:%M', time.localtime(self.exported_at))}"
        )


class WorkspaceExporter:
    """Collect all local data and export to a single JSON file."""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.expanduser("~/.agent-swarm")

    def export(self, output_path: str) -> WorkspaceBundle:
        """Export all local data to a JSON file."""
        bundle = WorkspaceBundle()

        # 1. Skills
        bundle.skills = self._collect_skills()
        bundle.total_skills_evolved = len(bundle.skills)

        # 2. Skill genetics / lineage
        bundle.skill_genetics = self._collect_genetics()

        # 3. Memory
        bundle.memories = self._collect_memories()

        # 4. Run history
        bundle.recent_runs = self._collect_runs()
        bundle.total_runs = len(bundle.recent_runs)

        # 5. Token usage
        bundle.total_tokens = sum(
            r.get("total_tokens", 0) for r in bundle.recent_runs
        )

        # 6. Custom ontology
        bundle.custom_ontology_terms = self._collect_ontology()

        # 7. Packs
        bundle.installed_packs = self._collect_packs()

        # 8. Settings
        bundle.settings = self._collect_settings()

        # Write
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(bundle.to_json())

        return bundle

    def _collect_skills(self) -> List[Dict]:
        """Collect evolved skills from SkillBank persistence."""
        skills_file = os.path.join(self.data_dir, "skills.json")
        if not os.path.isfile(skills_file):
            # Try to collect from in-memory if available
            return self._try_in_memory_skills()
        try:
            with open(skills_file) as f:
                data = json.load(f)
            skills = []
            for s in data.get("general", []):
                skills.append(s)
            for category, skill_list in data.get("specific", {}).items():
                for s in skill_list:
                    s["category"] = category
                    skills.append(s)
            return skills
        except Exception:
            return []

    def _try_in_memory_skills(self) -> List[Dict]:
        """Try to collect skills from a running SkillBank."""
        try:
            from agent_swarm import SkillBank
            bank = SkillBank()
            return [{"name": s.name, "principle": s.principle,
                     "when_to_apply": s.when_to_apply,
                     "state": s.state.value if hasattr(s.state, 'value') else str(s.state),
                     "usage_count": s.hit_count, "success_count": s.helped_count,
                     "fitness": getattr(s, 'fitness', 0)}
                    for s in bank._all()]
        except Exception:
            return []

    def _collect_genetics(self) -> List[Dict]:
        """Collect skill lineage records."""
        genetics_file = os.path.join(self.data_dir, "genetics.json")
        if os.path.isfile(genetics_file):
            try:
                with open(genetics_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _collect_memories(self) -> List[Dict]:
        """Collect persistent memories."""
        mem_file = os.path.join(self.data_dir, "memory", "memories.json")
        if os.path.isfile(mem_file):
            try:
                with open(mem_file) as f:
                    data = json.load(f)
                return data.get("memories", [])
            except Exception:
                pass
        return []

    def _collect_runs(self, limit: int = 50) -> List[Dict]:
        """Collect recent run data."""
        runs_dir = os.path.join(self.data_dir, "hosted", "runs")
        if not os.path.isdir(runs_dir):
            runs_dir = os.path.join(self.data_dir, "checkpoints")
        if not os.path.isdir(runs_dir):
            return []

        runs = []
        try:
            for fname in sorted(os.listdir(runs_dir), reverse=True)[:limit]:
                if not fname.endswith(".json"):
                    continue
                with open(os.path.join(runs_dir, fname)) as f:
                    runs.append(json.load(f))
        except Exception:
            pass
        return runs

    def _collect_ontology(self) -> List[Dict]:
        """Collect custom ontology terms."""
        onto_file = os.path.join(self.data_dir, "custom_ontology.json")
        if os.path.isfile(onto_file):
            try:
                with open(onto_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _collect_packs(self) -> List[str]:
        """List installed user packs."""
        packs_dir = os.path.join(self.data_dir, "packs")
        if not os.path.isdir(packs_dir):
            return []
        try:
            return [d for d in os.listdir(packs_dir)
                    if os.path.isdir(os.path.join(packs_dir, d))]
        except Exception:
            return []

    def _collect_settings(self) -> Dict:
        """Collect user settings/config."""
        config_file = os.path.join(self.data_dir, "config.json")
        if os.path.isfile(config_file):
            try:
                with open(config_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}


class WorkspaceImporter:
    """Import a workspace bundle into the current environment.

    Used by Pro hosted server to restore user's local data.
    """

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.expanduser("~/.agent-swarm")

    def import_bundle(self, bundle: WorkspaceBundle, user_id: str = "") -> Dict:
        """Import a workspace bundle. Returns summary of what was imported."""
        result = {
            "user_id": user_id,
            "skills_imported": 0,
            "memories_imported": 0,
            "genetics_imported": 0,
            "runs_imported": 0,
            "ontology_imported": 0,
            "packs_imported": 0,
        }

        # 1. Skills
        if bundle.skills:
            result["skills_imported"] = self._import_skills(bundle.skills, user_id)

        # 2. Genetics
        if bundle.skill_genetics:
            result["genetics_imported"] = self._import_genetics(bundle.skill_genetics, user_id)

        # 3. Memories
        if bundle.memories:
            result["memories_imported"] = self._import_memories(bundle.memories, user_id)

        # 4. Runs
        if bundle.recent_runs:
            result["runs_imported"] = self._import_runs(bundle.recent_runs, user_id)

        # 5. Ontology
        if bundle.custom_ontology_terms:
            result["ontology_imported"] = self._import_ontology(bundle.custom_ontology_terms, user_id)

        # 6. Packs (names only — user needs to install them)
        result["packs_imported"] = len(bundle.installed_packs)
        result["packs_to_install"] = bundle.installed_packs

        return result

    def _import_skills(self, skills: List[Dict], user_id: str) -> int:
        """Import skills into SkillBank."""
        try:
            from agent_swarm import SkillBank, Skill
            bank = SkillBank()
            count = 0
            for sd in skills:
                try:
                    skill = Skill(
                        name=sd.get("name", f"imported_{count}"),
                        principle=sd.get("principle", ""),
                        when_to_apply=sd.get("when_to_apply", ""),
                    )
                    bank.add(skill)
                    count += 1
                except Exception:
                    pass

            # Persist
            user_dir = os.path.join(self.data_dir, "users", user_id)
            os.makedirs(user_dir, exist_ok=True)
            bank.save(os.path.join(user_dir, "skills.json"))
            return count
        except Exception:
            return 0

    def _import_genetics(self, records: List[Dict], user_id: str) -> int:
        """Import genetics lineage."""
        try:
            user_dir = os.path.join(self.data_dir, "users", user_id)
            os.makedirs(user_dir, exist_ok=True)
            with open(os.path.join(user_dir, "genetics.json"), "w") as f:
                json.dump(records, f, indent=2, default=str)
            return len(records)
        except Exception:
            return 0

    def _import_memories(self, memories: List[Dict], user_id: str) -> int:
        """Import memories into MemoryStore."""
        try:
            user_dir = os.path.join(self.data_dir, "users", user_id, "memory")
            os.makedirs(user_dir, exist_ok=True)
            with open(os.path.join(user_dir, "memories.json"), "w") as f:
                json.dump({"memories": memories, "id_counter": len(memories)},
                          f, indent=2, ensure_ascii=False, default=str)
            return len(memories)
        except Exception:
            return 0

    def _import_runs(self, runs: List[Dict], user_id: str) -> int:
        """Import run history."""
        try:
            user_dir = os.path.join(self.data_dir, "users", user_id, "runs")
            os.makedirs(user_dir, exist_ok=True)
            for i, run in enumerate(runs):
                rid = run.get("id", run.get("_durable_run_id", f"imported_{i}"))
                with open(os.path.join(user_dir, f"{rid}.json"), "w") as f:
                    json.dump(run, f, indent=2, default=str)
            return len(runs)
        except Exception:
            return 0

    def _import_ontology(self, terms: List[Dict], user_id: str) -> int:
        """Import custom ontology terms."""
        try:
            user_dir = os.path.join(self.data_dir, "users", user_id)
            os.makedirs(user_dir, exist_ok=True)
            with open(os.path.join(user_dir, "custom_ontology.json"), "w") as f:
                json.dump(terms, f, indent=2, ensure_ascii=False, default=str)
            return len(terms)
        except Exception:
            return 0
