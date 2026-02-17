# Vesper Framework

**Verified execution bridging traditional code and LLM-native runtimes**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Build](https://github.com/witlox/vesper/actions/workflows/build.yml/badge.svg)](https://github.com/witlox/vesper/actions/workflows/build.yml)
[![Python Tests](https://github.com/witlox/vesper/actions/workflows/python-test.yml/badge.svg)](https://github.com/witlox/vesper/actions/workflows/python-test.yml)
[![Python Lint](https://github.com/witlox/vesper/actions/workflows/python-lint.yml/badge.svg)](https://github.com/witlox/vesper/actions/workflows/python-lint.yml)
[![Rust Tests](https://github.com/witlox/vesper/actions/workflows/rust-test.yml/badge.svg)](https://github.com/witlox/vesper/actions/workflows/rust-test.yml)
[![Rust Lint](https://github.com/witlox/vesper/actions/workflows/rust-lint.yml/badge.svg)](https://github.com/witlox/vesper/actions/workflows/rust-lint.yml)
[![Integration Tests](https://github.com/witlox/vesper/actions/workflows/integration.yml/badge.svg)](https://github.com/witlox/vesper/actions/workflows/integration.yml)
[![codecov](https://codecov.io/gh/witlox/vesper/branch/main/graph/badge.svg)](https://codecov.io/gh/witlox/vesper)

## Vision

Vesper enables a future where software is developed at the intent level rather than implementation level. It provides:

- **Semantic Specification**: A high-level, LLM-native way to express software behavior
- **Dual-Path Execution**: Run the same semantic specification through both proven Python implementations and experimental optimized runtimes
- **Gradual Migration**: Shift from traditional code to direct execution based on empirical verification
- **Verification-First**: Prove correctness through differential testing before trusting new implementations

## The Problem

Current software development is constrained by human-centric programming languages designed decades ago. As LLMs become capable of understanding intent directly, we need representations optimized for:

1. **LLM reasoning** - Semantic graphs, contracts, and capabilities rather than imperative code
2. **Automatic optimization** - Runtimes that can reoptimize based on actual behavior
3. **Formal verification** - Provable correctness through contracts and properties
4. **Evolution** - Systems that adapt without manual refactoring

But we can't abandon proven technology. We need a **hedged bet**: maintain traditional implementations while building toward an LLM-native future.

## The Solution

```
┌─────────────────────────┐
│   Vesper Spec (.vsp)    │  ← Single source of truth
│  Intent + Contracts     │
└────────────┬────────────┘
             │
   ┌─────────┴─────────┐
   │                   │
   ▼                   ▼
┌──────────────┐  ┌──────────────┐
│ Python Path  │  │ Direct Path  │
│  (Proven)    │  │ (Optimized)  │
└──────┬───────┘  └──────┬───────┘
       │                 │
       └────────┬────────┘
                ▼
       ┌─────────────────┐
       │  Verification   │  ← Compare outputs
       │  Dashboard      │
       └─────────────────┘
```

### Key Features

- ✅ **Write intent, not implementation** - Express what you want, not how to do it
- ✅ **Automatic verification** - Both paths must produce identical outputs
- ✅ **Gradual migration** - Start Python-only, migrate to direct runtime as confidence grows
- ✅ **Confidence-based routing** - Route traffic based on empirical reliability
- ✅ **Rich debugging** - Debug at semantic level across both runtimes
- ✅ **Performance visibility** - Know exactly how much faster the optimized path is

## Project Status

**Current Phase**: initializing

- [x] Architecture design
- [x] Vesper specification v0.1
- [ ] Python code generator (in progress)
- [ ] Direct runtime core (planned)
- [ ] Differential testing framework (planned)
- [ ] First production deployment (planned)

## Documentation

- **[Architecture Overview](docs/ARCHITECTURE.md)** - System design and dual-path execution
- **[Vesper Specification](docs/VESPER_SPEC.md)** - Complete format reference

## Repository Structure

```
vesper/
├── README.md                 # This file
├── docs/                     # Documentation
│   ├── ARCHITECTURE.md
│   ├── VESPER_SPEC.md
├── spec/                     # Vesper format definitions
│   ├── v0.1/
│   │   ├── schema.json
│   │   └── examples/
├── python/                   # Python implementation
│   ├── vesper_compiler/      # Vesper → Python code generator
│   ├── vesper_runtime/       # Python execution runtime
│   └── tests/
├── rust/                     # Direct runtime (Rust)
│   ├── vesper_core/          # Core semantic interpreter
│   ├── vesper_jit/           # JIT compiler
│   └── tests/
├── tools/                    # CLI and utilities
│   ├── cli/                  # `vesper` command-line tool
│   ├── dashboard/            # Web UI for verification
│   └── profiler/             # Performance analysis
├── examples/                 # Example semantic nodes
│   ├── hello_world/
│   ├── payment_handler/
│   └── data_pipeline/
└── tests/
    ├── differential/         # Differential testing
    ├── integration/
    └── property/             # Property-based tests
```

## Contributing

We welcome contributions! This is a research project exploring the future of software development.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Areas We Need Help

- 🔨 **Python code generator** - Converting Vesper to idiomatic Python
- 🦀 **Rust runtime** - Building the direct execution path
- 🧪 **Testing frameworks** - Differential and property-based testing
- 📚 **Documentation** - Examples, tutorials, best practices
- 🎨 **Tooling** - IDE plugins, debuggers, visualizations

## Research Questions

This project explores several open questions:

1. **Can LLMs reason more effectively with semantic specifications than traditional code?**
2. **What's the performance overhead of semantic interpretation vs JIT compilation?**
3. **At what confidence threshold can we safely migrate from Python to direct runtime?**
4. **How do we maintain debuggability without human-readable code?**
5. **Can semantic specifications enable automatic optimization based on runtime behavior?**

## Inspiration & Related Work

- **LLVM IR** - Proven intermediate representation for compilers
- **WebAssembly** - Portable compilation target with security properties
- **TLA+** - Formal specification language for distributed systems
- **Dafny** - Verified programming language
- **NormCode** - Semi-formal language for AI planning

## License

MIT License - see [LICENSE](LICENSE) for details.

## Citation

If you use this work in research, please cite:

```bibtex
@software{vesper_framework,
  title = {Vesper: Verified Execution Framework for LLM-Native Software},
  author = {Witlox},
  year = {2025},
  url = {https://github.com/witlox/vesper}
}
```

## Contact

- **GitHub**: [github.com/witlox/vesper](https://github.com/witlox/vesper)
- **Issues**: [GitHub Issues](https://github.com/witlox/vesper/issues)
- **Discussions**: [GitHub Discussions](https://github.com/witlox/vesper/discussions)

---

**Vesper** - *Guiding the transition from traditional to LLM-native software development*
