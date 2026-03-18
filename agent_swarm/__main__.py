"""CLI entrypoint: python -m agent_swarm"""
import asyncio
import json
import sys

def main():
    from . import Swarm, BUILTIN_PLAYBOOKS, CORE_ONTOLOGY, OntologyRegistry, __version__

    if "--version" in sys.argv:
        print(f"agent-swarm {__version__}")
        return

    if "--help" in sys.argv or len(sys.argv) < 2:
        print(f"""agent-swarm {__version__} — Lightweight engine for research, review, and approval workflows.

Usage:
  python -m agent_swarm "your goal here"
  python -m agent_swarm --playbook discover "explore new product ideas"

Commands:
  --playbooks        List available playbooks
  --ontology         Show core ontology vocabulary
  --packs            List available skill packs
  --pack-info NAME   Show pack details
  --add NAME         Install a skill pack
  --remove NAME      Remove a skill pack
  --installed        List installed packs
  --version          Show version

Export/Import:
  export             Export workspace to JSON (for Pro migration)
                     python -m agent_swarm export --output my_workspace.json
  export --summary   Show what would be exported without writing

Options:
  --playbook NAME    Run with a built-in playbook
  --with-pack NAME   Run with a skill pack loaded
  --json             Output result as JSON

MCP:
  python -m agent_swarm.mcp_server          Start MCP server
  python -m agent_swarm.mcp_server --setup  Show MCP setup guide
""")
        return

    # ── Export command ──
    if len(sys.argv) >= 2 and sys.argv[1] == "export":
        from .migrate import WorkspaceExporter
        exporter = WorkspaceExporter()

        if "--summary" in sys.argv:
            # Dry run — show what would be exported
            bundle = exporter.export("/dev/null") if sys.platform != "win32" else exporter.export("NUL")
            print(bundle.summary())
            return

        output = "workspace_export.json"
        for i, arg in enumerate(sys.argv):
            if arg == "--output" and i + 1 < len(sys.argv):
                output = sys.argv[i + 1]

        bundle = exporter.export(output)
        print(f"Exported to: {output}")
        print(bundle.summary())
        print(f"\nNext steps:")
        print(f"  1. Go to agentswarm.dev")
        print(f"  2. Upgrade to Pro ($49/mo)")
        print(f"  3. Click 'Import Workspace'")
        print(f"  4. Upload {output}")
        return

    if "--playbooks" in sys.argv:
        print("Available playbooks:")
        for name, pb in BUILTIN_PLAYBOOKS.items():
            print(f"  {name:15s} — {pb.description}")
            if pb.next_steps:
                print(f"  {'':15s}   next: {', '.join(pb.next_steps)}")
        return

    if "--ontology" in sys.argv:
        reg = OntologyRegistry([CORE_ONTOLOGY])
        stats = reg.get_stats()
        print(f"Core Ontology: {stats['terms']} terms, {stats['relations']} relations")
        print("\nTask Types:")
        for t in CORE_ONTOLOGY.terms:
            if "TaskType" in t.id:
                caps = reg.task_requires(t.id)
                prods = reg.task_produces(t.id)
                print(f"  {t.label:15s} requires: {', '.join(c.split('/')[-1] for c in caps) or '-':30s} produces: {', '.join(p.split('/')[-1] for p in prods) or '-'}")
        return

    # ── Pack Commands ──────────────────────────────────────
    if "--packs" in sys.argv or "--list-packs" in sys.argv:
        from .packs import PackManager
        pm = PackManager()
        available = pm.list_available()
        print(f"Available skill packs ({len(available)}):\n")
        for name in available:
            meta = pm.get(name) or pm._load_pack(
                __import__("os").path.join(__import__("os").path.dirname(__file__), "builtin_packs", name))
            if meta:
                print(f"  {meta.name:20s} {meta.description}")
                print(f"  {'':20s} skills: {len(meta.skills)}, ontology terms: {len(meta.ontology_terms)}, tags: {', '.join(meta.tags)}")
                print()
            else:
                print(f"  {name}")
        return

    if "--installed" in sys.argv:
        from .packs import PackManager
        pm = PackManager()
        installed = pm.list_installed()
        if not installed:
            print("No packs installed. Use --add NAME to install one.")
            print("Use --packs to see available packs.")
            return
        print(f"Installed packs ({len(installed)}):\n")
        for p in installed:
            print(f"  {p['name']:20s} v{p['version']} — {p['description']}")
            print(f"  {'':20s} skills: {p['skills']}, ontology: {p['ontology_terms']}")
        return

    if "--add" in sys.argv:
        from .packs import PackManager
        idx = sys.argv.index("--add")
        if idx + 1 >= len(sys.argv):
            print("Usage: python -m agent_swarm --add PACK_NAME")
            sys.exit(1)
        pack_name = sys.argv[idx + 1]
        pm = PackManager()
        if pm.install(pack_name):
            meta = pm.get(pack_name)
            print(f"✓ Installed '{pack_name}'")
            print(f"  {meta.description}")
            print(f"  {len(meta.skills)} skills, {len(meta.ontology_terms)} ontology terms")
        else:
            print(f"✗ Pack '{pack_name}' not found. Use --packs to see available.")
            sys.exit(1)
        return

    if "--remove" in sys.argv:
        from .packs import PackManager
        idx = sys.argv.index("--remove")
        if idx + 1 >= len(sys.argv):
            print("Usage: python -m agent_swarm --remove PACK_NAME")
            sys.exit(1)
        pack_name = sys.argv[idx + 1]
        pm = PackManager()
        if pm.uninstall(pack_name):
            print(f"✓ Removed '{pack_name}'")
        else:
            print(f"✗ Pack '{pack_name}' not installed.")
        return

    if "--pack-info" in sys.argv:
        from .packs import PackManager
        idx = sys.argv.index("--pack-info")
        if idx + 1 >= len(sys.argv):
            print("Usage: python -m agent_swarm --pack-info PACK_NAME")
            sys.exit(1)
        pack_name = sys.argv[idx + 1]
        pm = PackManager()
        pm.install(pack_name)
        meta = pm.get(pack_name)
        if not meta:
            print(f"Pack '{pack_name}' not found."); sys.exit(1)
        print(f"{meta.name} v{meta.version}")
        print(f"  {meta.description}\n")
        print(f"Skills ({len(meta.skills)}):")
        for s in meta.skills:
            print(f"  • {s['name']:25s} {s.get('principle', '')[:60]}")
        if meta.ontology_terms:
            print(f"\nOntology terms ({len(meta.ontology_terms)}):")
            for t in meta.ontology_terms:
                print(f"  • {t['label']:25s} {t.get('definition', '')[:60]}")
        if meta.competency_questions:
            print(f"\nCompetency questions:")
            for q in meta.competency_questions:
                print(f"  ? {q}")
        return

    # ── Parse Run Arguments ────────────────────────────────
    playbook = None
    pack_name = None
    as_json = "--json" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if "--playbook" in sys.argv:
        idx = sys.argv.index("--playbook")
        if idx + 1 < len(sys.argv):
            playbook = sys.argv[idx + 1]
            args = [a for a in args if a != playbook]

    if "--with-pack" in sys.argv:
        idx = sys.argv.index("--with-pack")
        if idx + 1 < len(sys.argv):
            pack_name = sys.argv[idx + 1]
            args = [a for a in args if a != pack_name]

    goal = " ".join(args) if args else ""
    if not goal:
        print("Error: provide a goal. Use --help for usage.")
        sys.exit(1)

    async def run():
        from .packs import PackManager
        from .skills import SkillBank
        from .genetics import SkillGenetics

        bank = None
        genetics = None
        ontology = None

        if pack_name:
            pm = PackManager()
            pm.install(pack_name)
            bank, bundles = pm.apply()
            genetics = SkillGenetics(bank)
            for s in bank._all():
                genetics.register_lineage(s)
            if bundles:
                all_bundles = [CORE_ONTOLOGY] + bundles
                ontology = OntologyRegistry(all_bundles)

        swarm = Swarm(llm=None, skill_bank=bank, genetics=genetics,
                      ontology=ontology or OntologyRegistry([CORE_ONTOLOGY]))
        if playbook:
            result = await swarm.run(goal, playbook=playbook)
        else:
            result = await swarm.run(goal)
        return result

    result = asyncio.run(run())

    if as_json:
        meta = {k: v for k, v in result["metadata"].items() if k not in ("tracing", "checkpoint", "global_metrics")}
        print(json.dumps({"output": result["final_output"], "metadata": meta}, indent=2, ensure_ascii=False, default=str))
    else:
        print(result["final_output"])
        meta = result["metadata"]
        print(f"\n--- {meta['succeeded']}/{meta['total_tasks']} tasks succeeded in {meta['execution_time_s']}s ---")
        if meta.get("next_steps"):
            print(f"Suggested next: {', '.join(meta['next_steps'])}")

if __name__ == "__main__":
    main()
