# Contributing to Vesper

Thank you for your interest in contributing! This is a research project exploring the future of LLM-native software development.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Documentation](#documentation)

## Code of Conduct

### Our Pledge

We pledge to make participation in this project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

**Positive behavior includes:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

**Unacceptable behavior includes:**
- Harassment, trolling, or discriminatory comments
- Publishing others' private information
- Other conduct inappropriate in a professional setting

## Getting Started

### Areas We Need Help

🔨 **Python Code Generator**
- Implement flow step generators (database, API calls, etc.)
- Add contract validation
- Improve error handling
- Generate more idiomatic Python

🦀 **Rust Direct Runtime**
- Core semantic IR interpreter
- JIT compiler integration
- Operation implementations
- Performance optimization

🧪 **Testing Infrastructure**
- Differential testing framework
- Property-based testing
- Confidence calculation
- Verification dashboards

📚 **Documentation**
- Examples and tutorials
- Architecture decision records
- Best practices guides
- API documentation

🎨 **Tooling**
- IDE plugins (VS Code, IntelliJ)
- Debugger improvements
- Dashboard features
- CLI enhancements

📊 **Research**
- Performance benchmarking
- Formal verification
- Security analysis
- Case studies

## Development Setup

### Prerequisites

- Python 3.10+
- Rust 1.70+
- PostgreSQL 14+
- Git

### Clone Repository

```bash
git clone https://github.com/witlox/vesper.git
cd vesper
```

### Python Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
cd python
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest
```

### Rust Setup

```bash
cd rust
cargo build
cargo test
```

### Database Setup

```bash
# Create database
createdb vesper_dev

# Run migrations
cd python
alembic upgrade head
```

### Verify Installation

```bash
# Test CLI
vesper --version

# Run example
vesper run examples/hello_world.vsp --mode python_only
```

## How to Contribute

### 1. Find an Issue

Browse [open issues](https://github.com/witlox/vesper/issues) or create a new one.

**Good first issues are labeled:** `good-first-issue`, `help-wanted`, `documentation`

### 2. Discuss Your Approach

For significant changes:
1. Create an issue first
2. Discuss the approach
3. Get feedback before coding

For small fixes (typos, bugs):
- Just submit a PR

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

**Branch naming:**
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation
- `test/` - Test improvements
- `refactor/` - Code refactoring

### 4. Make Changes

Follow our [coding standards](#coding-standards) and write tests.

### 5. Commit

Use clear, descriptive commit messages:

```bash
git commit -m "feat: add database query operation to Python generator"
git commit -m "fix: handle timeout errors in API calls"
git commit -m "docs: add example for payment processing"
```

**Commit message format:**
```
type: short description

Longer explanation if needed.

Fixes #123
```

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `test` - Tests
- `refactor` - Code refactoring
- `perf` - Performance improvement
- `chore` - Maintenance

### 6. Push and Create PR

```bash
git push origin your-branch-name
```

Then create a Pull Request on GitHub.

## Pull Request Process

### PR Checklist

Before submitting, ensure:

- [ ] Code follows style guidelines
- [ ] Tests added/updated
- [ ] Tests pass (`pytest` for Python, `cargo test` for Rust)
- [ ] Documentation updated
- [ ] Commit messages are clear
- [ ] Branch is up to date with main

### PR Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How was this tested?

## Related Issues
Fixes #123

## Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] Follows coding standards
```

### Review Process

1. **Automated checks run** (tests, linting, type checking)
2. **Maintainer reviews** (usually within 2-3 days)
3. **Address feedback**
4. **Approval & merge**

## Coding Standards

### Python

**Style Guide:** PEP 8 with modifications

```python
# Good
def execute_semantic_node(
    node_id: str,
    inputs: Dict[str, Any],
    mode: ExecutionMode = ExecutionMode.PYTHON_ONLY
) -> Result:
    """
    Execute a semantic node with specified inputs.
    
    Args:
        node_id: Unique identifier for the node
        inputs: Input parameters matching node schema
        mode: Execution mode (python_only, shadow_direct, etc.)
        
    Returns:
        Result object with output or error
        
    Raises:
        ValidationError: If inputs don't match schema
        ExecutionError: If execution fails
    """
    # Implementation
    pass

# Bad
def exec(n,i,m=0):  # No type hints, unclear names
    pass
```

**Key points:**
- Type hints required (Python 3.10+ syntax)
- Docstrings for all public functions (Google style)
- Max line length: 100 characters
- Use `black` for formatting
- Use `mypy` for type checking
- Use `ruff` for linting

**Run formatters:**
```bash
black python/
ruff check python/
mypy python/
```

### Rust

**Style Guide:** Rust standard style

```rust
// Good
pub async fn execute_semantic_node(
    node_id: &str,
    inputs: HashMap<String, Value>,
    mode: ExecutionMode,
) -> Result<Output> {
    /// Execute a semantic node with specified inputs.
    ///
    /// # Arguments
    /// * `node_id` - Unique identifier for the node
    /// * `inputs` - Input parameters matching node schema
    /// * `mode` - Execution mode
    ///
    /// # Returns
    /// Result with output or error
    ///
    /// # Errors
    /// Returns error if validation fails or execution fails
    
    // Implementation
}

// Bad
pub fn exec(n: &str, i: HashMap<String, Value>) -> Result<Output> {
    // No docs, unclear names
}
```

**Key points:**
- Use `rustfmt` for formatting
- Use `clippy` for linting
- Document all public APIs
- Use meaningful variable names
- Handle errors with `Result`/`anyhow`

**Run formatters:**
```bash
cargo fmt
cargo clippy
```

### YAML (Vesper)

```yaml
# Good - clear, well-documented
node_id: payment_processor_v1
type: payment_handler
intent: process_credit_card_payment  # Clear intent

inputs:
  amount:
    type: decimal
    required: true
    constraints:
      - positive
      - max: 50000
    description: Payment amount in USD  # Helpful description

# Bad - unclear, minimal documentation
node_id: pay_v1
type: handler
intent: pay

inputs:
  a: {type: decimal}  # What is 'a'?
```

## Testing Requirements

### Test Coverage

- **Minimum:** 80% code coverage
- **Target:** 90%+ for critical paths
- **Required:** 100% for contract validation

### Test Types

**1. Unit Tests**

Test individual functions:

```python
def test_contract_validator_preconditions():
    """Test precondition validation"""
    validator = ContractValidator()
    
    # Valid case
    result = validator.validate_preconditions(
        preconditions=["amount > 0"],
        context={"amount": 100}
    )
    assert result.valid
    
    # Invalid case
    result = validator.validate_preconditions(
        preconditions=["amount > 0"],
        context={"amount": -10}
    )
    assert not result.valid
    assert "amount > 0" in result.error_message
```

**2. Integration Tests**

Test components together:

```python
def test_python_generator_end_to_end():
    """Test complete code generation pipeline"""
    # Load Vesper
    vesper_node = load_vesper_file("test_cases/hello_world.vsp")
    
    # Generate Python
    generator = PythonGenerator()
    python_code = generator.generate(vesper_node)
    
    # Compile and execute
    exec(python_code)
    result = hello_world_v1(name="Alice")
    
    assert isinstance(result, HelloWorldSuccess)
    assert "Alice" in result.message
```

**3. Differential Tests**

Compare Python and Rust outputs:

```python
def test_payment_handler_differential():
    """Test payment handler produces identical outputs"""
    tester = DifferentialTester('payment_handler_v1')
    report = tester.run_tests(num_tests=1000)
    
    assert report.accuracy >= 0.999, \
        f"Accuracy {report.accuracy} below threshold"
    
    if report.divergences > 0:
        pytest.fail(f"Found {report.divergences} divergences")
```

**4. Property-Based Tests**

Test invariants:

```python
from hypothesis import given, strategies as st

@given(
    amount=st.decimals(min_value='0.01', max_value='10000'),
    user_id=st.text(min_size=1)
)
def test_payment_idempotency(amount, user_id):
    """Property: Same idempotency key returns same result"""
    key = "test_key"
    
    result1 = execute_node('payment_handler_v1', {
        'amount': amount,
        'user_id': user_id,
        'idempotency_key': key
    })
    
    result2 = execute_node('payment_handler_v1', {
        'amount': amount,
        'user_id': user_id,
        'idempotency_key': key
    })
    
    assert result1 == result2
```

### Running Tests

```bash
# Python tests
cd python
pytest                          # All tests
pytest -v                       # Verbose
pytest --cov=vesper_compiler      # With coverage
pytest -k test_contract        # Specific tests
pytest -m integration          # Integration tests only

# Rust tests
cd rust
cargo test                     # All tests
cargo test --release           # Optimized build
cargo test contract            # Tests matching "contract"
```

### Test Organization

```
tests/
├── unit/
│   ├── test_compiler.py
│   ├── test_validator.py
│   └── test_executor.py
├── integration/
│   ├── test_end_to_end.py
│   └── test_cli.py
├── differential/
│   └── test_python_vs_rust.py
├── property/
│   └── test_invariants.py
└── fixtures/
    ├── vesper_files/
    │   ├── hello_world.vsp
    │   └── payment_handler.vsp
    └── expected_outputs/
```

## Documentation

### What to Document

**Code changes:**
- Update relevant .md files
- Add docstrings to new functions
- Update API documentation

**New features:**
- Add to GETTING_STARTED.md
- Create example in examples/
- Update ARCHITECTURE.md if needed
- Add to CHANGELOG.md

**Bug fixes:**
- Note in commit message
- Add regression test

### Documentation Style

**Markdown files:**
- Use clear headings
- Include code examples
- Add cross-references
- Keep examples up-to-date

**Code comments:**
```python
# Good: Explain WHY, not WHAT
# Use Wilson score interval to account for sample size
confidence = self._calculate_wilson_score(metrics)

# Bad: State the obvious
# Calculate confidence
confidence = self._calculate_wilson_score(metrics)
```

**Docstrings:**
```python
def execute_node(node_id: str, inputs: Dict[str, Any]) -> Result:
    """
    Execute a semantic node with given inputs.
    
    This function handles the dual-path execution model, routing
    to either Python or direct runtime based on confidence scores.
    
    Args:
        node_id: Unique identifier (e.g., 'payment_handler_v1')
        inputs: Input parameters matching node's input schema
        
    Returns:
        Result object containing either success output or error
        
    Raises:
        ValidationError: If inputs don't match schema
        NodeNotFoundError: If node_id doesn't exist
        
    Example:
        >>> result = execute_node('hello_world_v1', {'name': 'Alice'})
        >>> print(result.message)
        Hello, Alice!
    """
```

## Architecture Decision Records (ADRs)

For significant architectural decisions, create an ADR:

```markdown
# ADR-001: Use Wilson Score for Confidence Calculation

## Status
Accepted

## Context
We need a statistical method to determine when direct runtime
is reliable enough to handle production traffic.

## Decision
Use Wilson score confidence interval with 99.9% confidence level.

## Consequences
- Conservative approach (slow migration)
- Statistically rigorous
- Requires minimum 10,000 samples
- Well-understood in industry

## Alternatives Considered
- Simple accuracy percentage (rejected: no statistical rigor)
- Bayesian confidence (rejected: too complex)
```

Store in `docs/adr/`.

## Communication

### GitHub Discussions

Use for:
- Feature proposals
- Design discussions
- Help requests
- Sharing ideas

### GitHub Issues

Use for:
- Bug reports
- Feature requests
- Specific tasks

**Good issue example:**
```markdown
Title: Add support for WebSocket operations in flow steps

**Description:**
Currently we support HTTP requests but not WebSocket connections.
Many real-time applications need WebSocket support.

**Proposed Solution:**
Add a new operation type: `websocket_connection`

**Example Vesper:**
```yaml
- step: connect_websocket
  operation: websocket_connection
  url: wss://example.com/stream
  on_message:
    handler: process_message
```

**Impact:**
- Changes to VESPER_SPEC.md
- New operation in Python generator
- New operation in Rust runtime
- Tests needed

**Questions:**
- How to handle connection lifecycle?
- Retry strategy for disconnections?
```

## Release Process

### Versioning

We use [Semantic Versioning](https://semver.org/):
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

### Release Checklist

1. Update CHANGELOG.md
2. Update version in:
   - `python/setup.py`
   - `rust/Cargo.toml`
   - `package.json` (if applicable)
3. Tag release: `git tag v0.2.0`
4. Push tags: `git push --tags`
5. Create GitHub release with notes
6. Publish to PyPI (Python)
7. Publish to crates.io (Rust)

## Recognition

Contributors are recognized in:
- CONTRIBUTORS.md
- GitHub contribution graphs
- Release notes
- Project documentation

## Questions?

- Check [GitHub Discussions](https://github.com/witlox/vesper/discussions)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing to the future of software development!

