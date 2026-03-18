# Contributing to Agent Swarm

Thank you for your interest in contributing!

## Quick Start

```bash
git clone https://github.com/doeun/agent-swarm.git
cd agent-swarm
pytest tests/ -q          # 98 tests should pass
python test_agent_swarm.py  # 123 tests should pass
```

## Guidelines

1. **Zero dependencies.** This is a core design principle. Don't add external packages to `agent_swarm/`.
2. **Every feature needs a test.** Add tests to `tests/test_all.py` (pytest-native).
3. **Keep it small.** The whole engine is ~2,300 lines. Don't bloat it.

## What we need help with

- Real-world usage examples (connect to your LLM, share the result)
- Custom ontology bundles for specific domains (legal, healthcare, fintech)
- Custom playbook packs
- Bug reports with reproducible code
- Documentation improvements

## Pull Request Process

1. Fork the repo
2. Create a branch: `git checkout -b feature/my-feature`
3. Write tests first
4. Make sure all tests pass: `pytest tests/ -q`
5. Submit PR with a clear description

## Code Style

- Follow existing patterns in the codebase
- Docstrings on public functions
- Type hints where practical

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
