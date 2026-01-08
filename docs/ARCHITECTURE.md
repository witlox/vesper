# Vesper Architecture

This document describes the technical architecture of the Vesper Framework.

## Table of Contents

- [High-Level Architecture](#high-level-architecture)
- [Vesper Design](#semantic-ir-design)
- [Dual-Path Execution](#dual-path-execution)
- [Verification System](#verification-system)
- [Migration Strategy](#migration-strategy)
- [Runtime Architecture](#runtime-architecture)
- [Debugging Infrastructure](#debugging-infrastructure)

## High-Level Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Developer Interface                     │
│  (CLI, IDE plugins, Web dashboard)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Vesper Compiler & Tools                   │
│  - Parser (YAML → AST)                                      │
│  - Validator (contract checking)                            │
│  - Code Generator (Vesper → Python)                         │
│  - Optimizer (semantic transformations)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Vesper Repository                        │
│  - Version control for .vsp files                           │
│  - Dependency resolution                                    │
│  - Capability registry                                      │
└────────────────────────┬────────────────────────────────────┘
                         │
           ┌─────────────┴──────────────┐
           │                            │
           ▼                            ▼
┌──────────────────────┐    ┌──────────────────────┐
│   Python Runtime     │    │   Direct Runtime     │
│   (Reference)        │    │   (Optimized)        │
│                      │    │                      │
│ ┌──────────────────┐ │    │ ┌──────────────────┐ │
│ │ Python Executor  │ │    │ │ Semantic Engine  │ │
│ │ - Interpret      │ │    │ │ - Interpret IR   │ │
│ │   generated code │ │    │ │ - JIT compile    │ │
│ └──────────────────┘ │    │ └──────────────────┘ │
│                      │    │                      │
│ ┌──────────────────┐ │    │ ┌──────────────────┐ │
│ │ Standard Library │ │    │ │ Native Backends  │ │
│ │ - numpy, pandas  │ │    │ │ - BLAS, CUDA     │ │
│ └──────────────────┘ │    │ └──────────────────┘ │
└──────────────────────┘    └──────────────────────┘
           │                            │
           └────────────┬───────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Verification & Monitoring System               │
│  - Differential testing                                     │
│  - Metrics collection                                       │
│  - Confidence calculation                                   │
│  - Traffic routing decisions                                │
└─────────────────────────────────────────────────────────────┘
```

## Vesper Design

### Core Principles

1. **Intent-First**: Every node expresses *what* not *how*
2. **Contract-Driven**: Preconditions, postconditions, invariants enforced
3. **Capability-Based**: Explicit permissions, no ambient authority
4. **Composable**: Nodes reference other nodes, build complex systems
5. **Verifiable**: Formal semantics enable proof of correctness

### Node Structure

Every semantic IR node has:

```yaml
node_id: unique_identifier_v1        # Versioned identifier
type: capability_type                # http_handler, data_transform, etc.
intent: high_level_purpose           # Human-readable purpose

metadata:
  author: string
  created: timestamp
  dependencies: [node_ids]
  tags: [searchable, keywords]

inputs:
  param_name:
    type: string | integer | decimal | boolean | custom_type
    constraints: [validation_rules]
    required: boolean
    default: value

outputs:
  success:
    field_name: type
  error:
    error_code: enum[...]
    message: string

contracts:
  preconditions: [logical_expressions]
  postconditions: [logical_expressions]
  invariants: [never_violated_properties]

flow:
  - step: step_name
    operation: operation_type
    parameters: {...}
    guards: [conditional_checks]
    error_handling: {...}

performance:
  expected_latency_ms: integer
  memory_limit_mb: integer
  timeout_seconds: integer

security:
  capabilities_required: [capability_list]
  sensitive_data: boolean
  audit_level: none | basic | detailed
```

### Type System

**Primitive Types**:
- `string` - UTF-8 text
- `integer` - Signed 64-bit
- `decimal` - Arbitrary precision decimal (for money)
- `boolean` - true/false
- `bytes` - Binary data
- `timestamp` - ISO 8601 datetime

**Collection Types**:
- `array<T>` - Ordered list
- `map<K,V>` - Key-value pairs
- `set<T>` - Unordered unique elements

**Custom Types**:
```yaml
types:
  User:
    fields:
      id: string
      email: string
      balance: decimal
    constraints:
      - balance >= 0
```

### Contract Language

Contracts are expressed in a subset of first-order logic:

```yaml
contracts:
  preconditions:
    - "amount > 0"
    - "user.authenticated"
    - "order.status == 'pending'"
  
  postconditions:
    - "transaction.recorded OR error.logged"
    - "order.status IN ['paid', 'payment_failed']"
    - "user.balance == old(user.balance) - amount OR error.occurred"
  
  invariants:
    - "SUM(all_user_balances) == total_system_balance"
    - "all(user.balance >= 0)"
```

**Logical Operators**:
- `AND`, `OR`, `NOT`
- `==`, `!=`, `<`, `<=`, `>`, `>=`
- `IN`, `CONTAINS`
- `FORALL`, `EXISTS`
- `old(expr)` - value before execution

## Dual-Path Execution

### Execution Modes

| Mode | Python | Direct | Use Case |
|------|--------|--------|----------|
| `python_only` | ✅ Primary | ❌ Disabled | Early development, low confidence |
| `shadow_direct` | ✅ Primary | ✅ Background | Data collection, no production impact |
| `canary_direct` | ✅ 95% | ✅ 5% | Initial production testing |
| `dual_verify` | ✅ Primary | ✅ Verify | High confidence, continuous verification |
| `direct_only` | ❌ Disabled | ✅ Primary | Very high confidence, maximum performance |

### Execution Flow

```python
async def execute_semantic_node(node_id: str, inputs: dict) -> Result:
    # 1. Load semantic IR
    vesper_node = load_node(node_id)
    
    # 2. Determine execution mode
    mode = migration_controller.get_execution_mode(node_id)
    
    # 3. Route based on mode
    if mode == ExecutionMode.PYTHON_ONLY:
        return await python_runtime.execute(vesper_node, inputs)
    
    elif mode == ExecutionMode.SHADOW_DIRECT:
        # Python runs in foreground
        python_result = await python_runtime.execute(vesper_node, inputs)
        
        # Direct runs in background (async)
        asyncio.create_task(
            direct_runtime.execute(vesper_node, inputs)
        )
        
        return python_result
    
    elif mode == ExecutionMode.CANARY_DIRECT:
        # Route 5% to direct, 95% to Python
        if hash(str(inputs)) % 100 < 5:
            try:
                return await direct_runtime.execute(vesper_node, inputs)
            except Exception:
                # Fallback to Python on failure
                return await python_runtime.execute(vesper_node, inputs)
        else:
            return await python_runtime.execute(vesper_node, inputs)
    
    elif mode == ExecutionMode.DUAL_VERIFY:
        # Execute both, compare, return Python
        python_result, direct_result = await asyncio.gather(
            python_runtime.execute(vesper_node, inputs),
            direct_runtime.execute(vesper_node, inputs)
        )
        
        if python_result != direct_result:
            metrics.record_divergence(node_id, inputs, python_result, direct_result)
        
        return python_result
    
    elif mode == ExecutionMode.DIRECT_ONLY:
        # Direct runtime with 1% sampling for verification
        if random.random() < 0.01:
            return await execute_dual_verify(node_id, inputs)
        else:
            return await direct_runtime.execute(vesper_node, inputs)
```

## Verification System

### Differential Testing

**Goal**: Prove that direct runtime produces identical outputs to Python runtime.

```python
class DifferentialTester:
    def test_node(self, node_id: str, num_tests: int = 10000):
        """Generate random inputs, compare outputs"""
        
        vesper_node = load_node(node_id)
        
        for i in range(num_tests):
            # Generate valid random input
            inputs = self.generate_random_input(vesper_node.inputs)
            
            # Execute both runtimes
            python_output = python_runtime.execute(node_id, inputs)
            direct_output = direct_runtime.execute(node_id, inputs)
            
            # Compare
            if python_output != direct_output:
                self.report_divergence({
                    'test_id': i,
                    'node_id': node_id,
                    'inputs': inputs,
                    'python_output': python_output,
                    'direct_output': direct_output
                })
```

### Confidence Calculation

Confidence is calculated using Wilson score interval:

```python
def calculate_confidence(metrics: RuntimeMetrics) -> float:
    """
    Calculate confidence that direct runtime is correct
    
    Uses Wilson score confidence interval for binomial proportion:
    - Accounts for sample size
    - Provides conservative lower bound
    - Statistical rigor over simple accuracy
    """
    
    if metrics.total_executions < MIN_SAMPLE_SIZE:
        return 0.0
    
    successes = metrics.total_executions - metrics.divergences
    
    # Wilson score with 99.9% confidence
    z = 3.29  # z-score for 99.9% confidence
    p = successes / metrics.total_executions
    
    denominator = 1 + z**2 / metrics.total_executions
    center = (p + z**2 / (2 * metrics.total_executions)) / denominator
    margin = z * sqrt(
        (p * (1-p) / metrics.total_executions + 
         z**2 / (4 * metrics.total_executions**2))
    ) / denominator
    
    return max(0, center - margin)  # Lower bound
```

**Confidence Thresholds**:
- `< 0.95`: Not ready, stay in Python
- `0.95 - 0.999`: Canary testing (5% traffic)
- `0.999 - 0.9999`: Dual verify (both runtimes)
- `> 0.9999`: Direct only (with 1% sampling)

### Property-Based Testing

Using Hypothesis to test invariant properties:

```python
from hypothesis import given, strategies as st

@given(
    amount=st.decimals(min_value='0.01', max_value='10000'),
    user_id=st.text(min_size=1)
)
def test_payment_idempotency(amount, user_id):
    """Property: Same payment request twice = same transaction"""
    
    idempotency_key = "test_key_123"
    
    # Execute twice with same key
    result1 = execute_node('payment_handler', {
        'amount': amount,
        'user_id': user_id,
        'idempotency_key': idempotency_key
    })
    
    result2 = execute_node('payment_handler', {
        'amount': amount,
        'user_id': user_id,
        'idempotency_key': idempotency_key
    })
    
    # Property: Results are identical
    assert result1 == result2
    assert result1.transaction_id == result2.transaction_id
```

## Migration Strategy

### Phase 1: Foundation

**Deliverables**:
- Vesper spec v0.1
- Python code generator
- CLI tools (`vesper compile`, `vesper run`)
- Basic differential testing

**Milestone**: First semantic node running in production (Python only)

### Phase 2: Validation

**Deliverables**:
- Direct runtime core (Rust)
- Shadow mode execution
- 10,000+ executions per node
- Differential testing dashboard

**Milestone**: 99.9% accuracy on critical nodes in shadow mode

### Phase 3: Canary

**Deliverables**:
- Canary routing (1-5% traffic)
- Error monitoring and alerting
- Automatic rollback on failures
- Performance benchmarking

**Milestone**: 10 nodes with 5% canary traffic

### Phase 4: Gradual Migration

**Deliverables**:
- Confidence-based routing
- 20+ nodes in production
- JIT compilation for hot paths
- Migration playbook

**Milestone**: 50% of traffic on direct runtime

### Phase 5: Majority Direct

**Deliverables**:
- 80%+ nodes on direct runtime
- Python runtime maintained for edge cases
- Comprehensive monitoring
- Performance optimization

## Runtime Architecture

### Python Runtime

**Components**:

```
Python Runtime
├── Code Generator
│   ├── Vesper Parser (YAML → AST)
│   ├── Validation (contract checking)
│   ├── Python AST Generator
│   └── Code Emitter (idiomatic Python)
│
├── Execution Engine
│   ├── Function Loader
│   ├── Contract Validator (preconditions, postconditions)
│   ├── Exception Handler
│   └── Metrics Collector
│
└── Standard Library
    ├── Common Operations (map, filter, reduce)
    ├── External Integrations (Stripe, AWS, etc.)
    └── Data Structures (validated types)
```

**Code Generation Strategy**:

1. Parse Vesper YAML to AST
2. Validate contracts and types
3. Generate Python function with:
   - Type hints
   - Docstrings with intent
   - Precondition checks
   - Implementation logic
   - Postcondition checks
   - Error handlers
4. Emit to `.py` file with header: `# AUTO-GENERATED - DO NOT EDIT`

### Direct Runtime (Rust)

**Architecture**:

```
Direct Runtime
├── Core Interpreter
│   ├── Vesper Loader (parse .vsp files)
│   ├── Semantic Executor
│   ├── Contract Validator
│   └── Operation Dispatcher
│
├── JIT Compiler
│   ├── Hot Path Detector (profiling)
│   ├── LLVM IR Generator
│   ├── Native Code Generator
│   └── Compiled Code Cache
│
├── Native Backends
│   ├── BLAS (matrix operations)
│   ├── CUDA (GPU compute)
│   ├── libpq (Postgres)
│   ├── Redis client
│   └── HTTP client
│
└── Memory Manager
    ├── Arena Allocator
    ├── Reference Counting
    └── Capability Tracking
```

**Execution Strategy**:

1. **Cold Path** (first execution):
   - Interpret semantic IR directly
   - Profile execution time per operation
   - Collect data for JIT compilation

2. **Warm Path** (after profiling):
   - Detect hot functions (>100 calls)
   - JIT compile to native code
   - Cache compiled version

3. **Hot Path** (optimized):
   - Execute compiled native code
   - Near-zero interpretation overhead
   - Monitor for performance regression

## Debugging Infrastructure

### Unified Debugger

Debug across both runtimes simultaneously:

```bash
$ vesper debug payment_handler --comparative

Comparative Debugging Session
========================================

PYTHON RUNTIME              | DIRECT RUNTIME
----------------------------+----------------------------
Location: validate_request  | Location: validate_request
Variables:                  | Variables:
  amount: 99.99            |   amount: 99.99
  user_id: "user_123"      |   user_id: "user_123"
  user.balance: 500.00     |   user.balance: 500.00

(sir-db) step

PYTHON RUNTIME              | DIRECT RUNTIME
----------------------------+----------------------------
Location: call_stripe_api   | Location: call_stripe_api
About to call:              | About to call:
  stripe.charge.create()    |   native_stripe_call()

(sir-db) continue
```

### Semantic Breakpoints

Set breakpoints on semantic events:

```python
# Break when contract violated
vesper debug --break-on contract_violation

# Break on state transition
vesper debug --break-on state_transition:paid->refunded

# Break on specific input
vesper debug --break-on 'input.amount > 10000'

# Break on divergence
vesper debug --break-on divergence
```

### Time-Travel Debugging

Replay execution from semantic trace:

```bash
$ vesper replay trace_id_12345

Replaying execution: trace_id_12345
Timestamp: 2025-01-08 14:23:15

Step 1: validate_request ✓
Step 2: state_transition: pending -> processing ✓
Step 3: call_stripe_api ✗ (timeout)

(replay) modify step 3
  Change: timeout 30s -> 60s

Re-executing from step 3...
  Response: 200 OK (45s)

Success! Apply fix? [y/N]
```

## Performance Optimization

### JIT Compilation

**Strategy**: Lazy compilation of hot paths

```rust
struct HotPathDetector {
    call_counts: HashMap<String, usize>,
    compilation_threshold: usize,
}

impl HotPathDetector {
    fn should_compile(&mut self, node_id: &str) -> bool {
        let count = self.call_counts.entry(node_id.to_string())
            .or_insert(0);
        
        *count += 1;
        
        *count >= self.compilation_threshold
    }
}

impl JITCompiler {
    fn compile_node(&self, node: &SemanticNode) -> CompiledCode {
        // Generate LLVM IR from semantic node
        let llvm_ir = self.generate_llvm_ir(node);
        
        // Optimize
        let optimized = self.optimize_llvm_ir(llvm_ir);
        
        // Compile to native
        let native_code = self.compile_to_native(optimized);
        
        native_code
    }
}
```

### Caching Strategy

**Multi-Level Cache**:

1. **L1: JIT Cache** - Compiled native code (in-memory)
2. **L2: Semantic Cache** - Parsed Vesper nodes (in-memory)
3. **L3: Result Cache** - Idempotent operations (Redis)

```rust
async fn execute_with_caching(node_id: &str, inputs: &Inputs) -> Result<Output> {
    // Check result cache (for idempotent operations)
    if node.is_idempotent() {
        if let Some(cached) = result_cache.get(node_id, inputs).await {
            return Ok(cached);
        }
    }
    
    // Check JIT cache
    if let Some(compiled) = jit_cache.get(node_id) {
        let result = compiled.execute(inputs)?;
        
        if node.is_idempotent() {
            result_cache.set(node_id, inputs, &result).await;
        }
        
        return Ok(result);
    }
    
    // Check semantic cache
    let vesper_node = semantic_cache.get_or_load(node_id).await?;
    
    // Execute and potentially compile
    let result = self.execute_semantic(vesper_node, inputs)?;
    
    if self.hot_path_detector.should_compile(node_id) {
        let compiled = self.jit_compiler.compile(vesper_node);
        jit_cache.insert(node_id, compiled);
    }
    
    Ok(result)
}
```

## Security Model

### Capability-Based Security

Every node explicitly declares required capabilities:

```yaml
node_id: payment_handler
security:
  capabilities_required:
    - database.write.transactions
    - network.http_client.stripe.com
    - secrets.read.stripe_api_key
  
  denied_capabilities:
    - filesystem.write
    - network.http_server
    - exec.shell_command
```

Runtime enforces capabilities:

```rust
fn execute_with_capabilities(
    node: &SemanticNode,
    inputs: &Inputs,
    granted_caps: &CapabilitySet
) -> Result<Output> {
    // Verify node has required capabilities
    for required_cap in &node.security.capabilities_required {
        if !granted_caps.contains(required_cap) {
            return Err(SecurityError::MissingCapability(required_cap.clone()));
        }
    }
    
    // Create sandboxed execution environment
    let sandbox = Sandbox::new(granted_caps);
    
    // Execute in sandbox
    sandbox.execute(node, inputs)
}
```

### Audit Logging

All sensitive operations logged:

```yaml
node_id: payment_handler
security:
  audit_level: detailed

# Generates audit log:
{
  "timestamp": "2025-01-08T14:23:15Z",
  "node_id": "payment_handler_v23",
  "user_id": "user_789",
  "action": "process_payment",
  "inputs": {"amount": 99.99, "order_id": "12345"},
  "result": "success",
  "transaction_id": "txn_abc123"
}
```

## Observability

### Metrics Collection

```python
class MetricsCollector:
    def record_execution(self, node_id: str, execution: Execution):
        """Record execution metrics"""
        
        self.metrics.counter('sir.executions.total', 
                            labels={'node': node_id, 'path': execution.path})
        
        self.metrics.histogram('sir.execution.duration_ms',
                              execution.duration_ms,
                              labels={'node': node_id, 'path': execution.path})
        
        if execution.error:
            self.metrics.counter('sir.executions.errors',
                                labels={'node': node_id, 'error': execution.error_type})
        
        if execution.divergence:
            self.metrics.counter('sir.divergences',
                                labels={'node': node_id})
```

**Key Metrics**:
- `sir.executions.total` - Total executions per node and path
- `sir.execution.duration_ms` - Latency distribution
- `sir.executions.errors` - Error rates
- `sir.divergences` - Divergence count
- `sir.confidence` - Current confidence score
- `sir.traffic_split` - Percentage on each path

### Distributed Tracing

OpenTelemetry integration:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

def execute_node(node_id: str, inputs: dict) -> Result:
    with tracer.start_as_current_span(
        "sir.execute",
        attributes={
            "sir.node_id": node_id,
            "sir.node_type": node.type,
            "sir.intent": node.intent
        }
    ) as span:
        
        result = runtime.execute(node_id, inputs)
        
        span.set_attribute("sir.execution_path", result.path_used)
        span.set_attribute("sir.duration_ms", result.duration_ms)
        
        if result.divergence:
            span.set_attribute("sir.divergence", True)
            span.add_event("divergence_detected")
        
        return result
```

## Next Steps

- Read [VESPER_SPEC.md](VESPER_SPEC.md) for complete IR specification

## Open Questions

1. **Optimal JIT threshold**: When should we compile? 100 calls? 1000?
2. **Cache invalidation**: How do we handle Vesper updates?
3. **Distributed execution**: How do semantic nodes run across multiple machines?
4. **Cost model**: What's the token cost of LLM-assisted optimization?
5. **Error attribution**: When both paths fail differently, which is right?
