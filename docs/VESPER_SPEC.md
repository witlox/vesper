# Vesper Specification v0.1

**Status**: Draft
**Last Updated**: 2025-01-08

## Overview

Vesper is a declarative, LLM-native format for expressing software behavior at the intent level rather than the implementation level.

## Design Goals

1. **Human-readable**: Uses YAML for clarity
2. **Machine-parseable**: Strict schema, validation
3. **LLM-friendly**: Semantic constructs LLMs understand naturally
4. **Verifiable**: Contracts enable formal verification
5. **Composable**: Nodes reference other nodes
6. **Versionable**: Semantic versioning for evolution

## File Format

### File Extension

`.vsp` - Vesper files use this extension (Vesper SPecification)

### Encoding

UTF-8 without BOM

### Structure

Top-level YAML document with required and optional fields.

## Complete Schema

### Minimal Example

```yaml
node_id: hello_world_v1
type: function
intent: greet_user

inputs:
  name: {type: string}

outputs:
  message: string

flow:
  - step: generate_greeting
    operation: string_template
    template: "Hello, {name}!"
```

### Complete Example

```yaml
# Required fields
node_id: payment_processor_v1
type: payment_handler
intent: process_credit_card_payment

# Optional metadata
metadata:
  author: alice@example.com
  created: 2025-01-08T10:00:00Z
  version: 1.0.0
  description: |
    Processes credit card payments through Stripe API.
    Handles idempotency, retries, and error cases.
  tags: [payments, stripe, financial]
  dependencies:
    - user_service_v2
    - ledger_service_v3
  changelog:
    - version: 1.0.0
      date: 2025-01-08
      changes: Initial implementation

# Input specification
inputs:
  order_id:
    type: string
    required: true
    constraints:
      - non_empty
      - pattern: "^ord_[a-zA-Z0-9]{16}$"
    description: Unique order identifier

  amount:
    type: decimal
    required: true
    constraints:
      - positive
      - max: 50000.00
    description: Payment amount in USD

  user_id:
    type: string
    required: true
    constraints:
      - non_empty

  idempotency_key:
    type: string
    required: false
    default: null
    description: Optional key for idempotent requests

# Output specification
outputs:
  success:
    transaction_id:
      type: string
      description: Unique transaction identifier
    status:
      type: enum
      values: [completed, pending, processing]
    amount_charged:
      type: decimal
    timestamp:
      type: timestamp

  error:
    error_code:
      type: enum
      values: [insufficient_funds, invalid_card, expired_card,
               network_timeout, service_unavailable, rate_limited]
    message:
      type: string
    retry_after_seconds:
      type: integer
      required: false

# Custom type definitions
types:
  PaymentMethod:
    fields:
      type: {type: enum, values: [card, bank_account]}
      card_last_four: {type: string, pattern: "^[0-9]{4}$"}
      expiry_month: {type: integer, min: 1, max: 12}
      expiry_year: {type: integer}
    constraints:
      - "expiry_year >= current_year()"

# Contracts
contracts:
  preconditions:
    - "amount > 0"
    - "amount <= 50000"
    - "user.authenticated"
    - "order.status == 'pending'"
    - "user.payment_method_valid"

  postconditions:
    - "transaction.recorded OR error.logged"
    - "order.status IN ['paid', 'payment_failed']"
    - "(success AND user.balance >= amount) OR error.occurred"
    - "idempotency: same idempotency_key => same transaction_id"

  invariants:
    - "total_balance_never_increases"
    - "FORALL transaction: transaction.amount == order.amount"
    - "user.balance >= 0"

# Execution flow
flow:
  - step: validate_request
    operation: validation
    description: Validate input parameters and user state
    guards:
      - "user_has_permission('process_payment')"
      - "amount_within_daily_limit(user, amount)"
    on_failure:
      return_error:
        error_code: validation_failed

  - step: check_idempotency
    operation: conditional
    condition: "idempotency_key IS NOT NULL"
    then:
      - operation: database_query
        query: "SELECT transaction_id FROM transactions WHERE idempotency_key = {idempotency_key}"
        on_result:
          if_found:
            return_success:
              transaction_id: "{query_result.transaction_id}"
              status: completed

  - step: state_transition_1
    operation: state_machine_transition
    state_machine: order_lifecycle
    from: pending
    to: processing
    guards:
      - order_not_locked

  - step: call_payment_provider
    operation: external_api_call
    provider: stripe
    endpoint: /v1/charges
    method: POST
    parameters:
      amount: "{amount}"
      currency: usd
      source: "{user.payment_method_id}"
      idempotency_key: "{idempotency_key}"
    timeout: 30s
    retry_policy:
      max_attempts: 3
      backoff: exponential
      backoff_base: 2
      initial_delay: 1s
    on_success:
      extract:
        transaction_id: "{response.id}"
        status: completed
    on_error:
      - error_type: card_declined
        map_to:
          error_code: insufficient_funds
          message: "{response.decline_reason}"
      - error_type: timeout
        action: retry
      - error_type: rate_limit
        action: backoff
        retry_after: "{response.retry_after}"

  - step: record_transaction
    operation: database_write
    table: transactions
    data:
      transaction_id: "{transaction_id}"
      order_id: "{order_id}"
      user_id: "{user_id}"
      amount: "{amount}"
      status: "{status}"
      idempotency_key: "{idempotency_key}"
      created_at: "{current_timestamp()}"
    consistency: strong
    timeout: 5s
    on_error:
      action: compensate
      compensation_steps:
        - operation: external_api_call
          provider: stripe
          endpoint: /v1/refunds
          method: POST
          parameters:
            charge: "{transaction_id}"

  - step: update_user_balance
    operation: database_update
    table: users
    where:
      user_id: "{user_id}"
    set:
      balance: "balance - {amount}"
      last_transaction_at: "{current_timestamp()}"
    consistency: strong

  - step: state_transition_2
    operation: state_machine_transition
    state_machine: order_lifecycle
    from: processing
    to: paid

  - step: emit_event
    operation: event_publish
    event_type: payment_completed
    data:
      order_id: "{order_id}"
      transaction_id: "{transaction_id}"
      amount: "{amount}"

# Error handling
error_handling:
  insufficient_funds:
    action: return_error
    notify: user
    log_level: info

  invalid_card:
    action: return_error
    notify: user
    log_level: warning

  network_timeout:
    action: retry
    max_retries: 3
    notify: ops_team
    log_level: error

  service_unavailable:
    action: circuit_breaker
    threshold: 5
    timeout: 60s
    notify: ops_team
    log_level: critical

# Performance requirements
performance:
  expected_latency_ms: 200
  p99_latency_ms: 500
  max_latency_ms: 2000
  memory_limit_mb: 256
  cpu_limit_cores: 0.5
  timeout_seconds: 30
  rate_limit:
    per_user: 100/minute
    global: 10000/minute

# Security configuration
security:
  capabilities_required:
    - database.write.transactions
    - database.write.users
    - network.http_client.stripe.com
    - secrets.read.stripe_api_key
    - event_bus.publish.payment_events

  denied_capabilities:
    - filesystem.write
    - network.http_server
    - exec.shell_command

  sensitive_data:
    - user.payment_method
    - transaction.card_details

  audit_level: detailed
  compliance:
    - PCI_DSS_v3.2
    - GDPR
    - SOC2

# Monitoring & Observability
observability:
  metrics:
    - name: payment_success_rate
      type: counter
      labels: [provider, currency]
    - name: payment_amount_total
      type: histogram
      buckets: [10, 50, 100, 500, 1000, 5000, 10000]
    - name: payment_latency_ms
      type: histogram
      buckets: [50, 100, 200, 500, 1000, 2000]

  alerts:
    - condition: "payment_success_rate < 0.95"
      severity: warning
      notify: [ops_team]
    - condition: "p99_latency_ms > 500"
      severity: warning
      notify: [ops_team]
    - condition: "payment_success_rate < 0.80"
      severity: critical
      notify: [ops_team, engineering_leads]

  tracing:
    enabled: true
    sample_rate: 0.1  # 10% of requests

  logging:
    level: info
    structured: true
    include_request_id: true

# Testing specifications
testing:
  property_tests:
    - property: idempotency
      description: Same idempotency key always returns same result
      strategy: hypothesis

    - property: balance_conservation
      description: Total system balance never changes
      invariant: "SUM(all_balances) == constant"

    - property: state_machine_correctness
      description: Only valid state transitions occur
      verify: order_lifecycle_states

  test_cases:
    - name: successful_payment
      inputs:
        order_id: ord_test_123456789012
        amount: 99.99
        user_id: user_test_123
      expected_output:
        success: true
        status: completed

    - name: insufficient_funds
      inputs:
        order_id: ord_test_123456789013
        amount: 99999.99
        user_id: user_test_123
      expected_output:
        error_code: insufficient_funds

    - name: idempotent_retry
      description: Same idempotency key returns same transaction
      steps:
        - execute_with:
            idempotency_key: idem_key_123
        - execute_with:
            idempotency_key: idem_key_123
        - assert: "result1.transaction_id == result2.transaction_id"

# Documentation
documentation:
  examples:
    - title: Basic payment
      code: |
        result = execute_node('payment_processor_v1', {
          'order_id': 'ord_abc123',
          'amount': 99.99,
          'user_id': 'user_789'
        })

    - title: Idempotent payment
      code: |
        result = execute_node('payment_processor_v1', {
          'order_id': 'ord_abc123',
          'amount': 99.99,
          'user_id': 'user_789',
          'idempotency_key': 'unique_key_123'
        })

  related_nodes:
    - user_service_v2
    - ledger_service_v3
    - refund_processor_v1

  migration_notes: |
    Migrating from payment_processor_v0:
    - Added idempotency_key parameter
    - Changed error_code enum values
    - Removed deprecated 'currency' parameter (now always USD)
```

## Field Reference

### Required Fields

#### `node_id`
- **Type**: string
- **Format**: `{name}_v{version}` where version is integer
- **Example**: `payment_processor_v1`
- **Description**: Unique identifier for this semantic node
- **Versioning**: Increment version for breaking changes

#### `type`
- **Type**: string
- **Valid values**:
  - `function` - Pure computation
  - `http_handler` - HTTP request handler
  - `event_handler` - Event stream processor
  - `data_transform` - Data transformation pipeline
  - `state_machine` - Stateful workflow
  - `aggregation` - Data aggregation
  - `scheduled_job` - Cron/scheduled task
- **Description**: Category of semantic node

#### `intent`
- **Type**: string
- **Description**: High-level purpose in plain English
- **Example**: "Process credit card payment through Stripe"

#### `inputs`
- **Type**: map<string, InputSpec>
- **Description**: Input parameters
- **Schema**:
  ```yaml
  parameter_name:
    type: string | integer | decimal | boolean | bytes | timestamp | custom_type
    required: boolean (default: true)
    constraints: [constraint_list]
    default: value (if required: false)
    description: string
  ```

#### `outputs`
- **Type**: map<string, OutputSpec>
- **Description**: Output specification
- **Must define**: `success` and `error` cases
- **Schema**:
  ```yaml
  success:
    field_name:
      type: type_specification
      description: string
  error:
    error_code:
      type: enum
      values: [error_values]
    message:
      type: string
  ```

#### `flow`
- **Type**: list<FlowStep>
- **Description**: Execution steps
- **Schema**:
  ```yaml
  - step: step_name
    operation: operation_type
    description: string (optional)
    parameters: {...}
    guards: [guard_conditions] (optional)
    on_success: {...} (optional)
    on_error: {...} (optional)
  ```

### Optional Fields

#### `metadata`
Provides documentation and tracking information:

```yaml
metadata:
  author: email_or_username
  created: ISO8601_timestamp
  version: semver_string
  description: multiline_string
  tags: [string_list]
  dependencies: [node_id_list]
  changelog:
    - version: string
      date: ISO8601_date
      changes: string
```

#### `types`
Define custom types:

```yaml
types:
  TypeName:
    fields:
      field_name: {type: type_spec, constraints: [...]}
    constraints:
      - "logical_expression"
```

#### `contracts`
Formal specifications:

```yaml
contracts:
  preconditions: [logical_expressions]
  postconditions: [logical_expressions]
  invariants: [logical_expressions]
```

**Contract Language**:
- Logical operators: `AND`, `OR`, `NOT`, `=>` (implies)
- Comparisons: `==`, `!=`, `<`, `<=`, `>`, `>=`
- Set operations: `IN`, `CONTAINS`
- Quantifiers: `FORALL`, `EXISTS`
- Functions: `old(expr)`, `current_timestamp()`, `SUM()`, `COUNT()`

#### `performance`
Performance requirements:

```yaml
performance:
  expected_latency_ms: integer
  p99_latency_ms: integer
  max_latency_ms: integer
  memory_limit_mb: integer
  cpu_limit_cores: float
  timeout_seconds: integer
  rate_limit:
    per_user: string  # e.g., "100/minute"
    global: string
```

#### `security`
Security configuration:

```yaml
security:
  capabilities_required: [capability_list]
  denied_capabilities: [capability_list]
  sensitive_data: [field_list]
  audit_level: none | basic | detailed
  compliance: [standard_list]
```

**Capability Format**: `{resource}.{operation}.{target}`

Examples:
- `database.write.transactions`
- `network.http_client.stripe.com`
- `secrets.read.api_keys`
- `filesystem.read.uploads`

#### `observability`
Monitoring configuration:

```yaml
observability:
  metrics:
    - name: metric_name
      type: counter | gauge | histogram
      labels: [label_list]
      buckets: [bucket_values]  # for histogram

  alerts:
    - condition: "logical_expression"
      severity: info | warning | error | critical
      notify: [recipient_list]

  tracing:
    enabled: boolean
    sample_rate: float  # 0.0 to 1.0

  logging:
    level: debug | info | warning | error
    structured: boolean
    include_request_id: boolean
```

#### `testing`
Test specifications:

```yaml
testing:
  property_tests:
    - property: property_name
      description: string
      strategy: hypothesis | quickcheck

  test_cases:
    - name: test_name
      inputs: {input_map}
      expected_output: {output_map}

  differential_tests:
    enabled: boolean
    sample_size: integer
```

## Operations Reference

### Validation

```yaml
operation: validation
guards: [condition_list]
on_failure:
  return_error: {error_spec}
```

### Conditional Logic

```yaml
operation: conditional
condition: "logical_expression"
then: [step_list]
else: [step_list]
```

### State Machine Transition

```yaml
operation: state_machine_transition
state_machine: state_machine_id
from: state_name
to: state_name
guards: [guard_list]
```

### Database Operations

```yaml
# Query
operation: database_query
query: "SQL or semantic query"
parameters: {param_map}
on_result:
  if_found: [step_list]
  if_empty: [step_list]

# Write
operation: database_write
table: table_name
data: {field_map}
consistency: eventual | strong
timeout: duration

# Update
operation: database_update
table: table_name
where: {condition_map}
set: {field_map}
consistency: eventual | strong
```

### External API Call

```yaml
operation: external_api_call
provider: provider_name
endpoint: /api/path
method: GET | POST | PUT | DELETE
parameters: {param_map}
headers: {header_map}
timeout: duration
retry_policy:
  max_attempts: integer
  backoff: exponential | linear | constant
  initial_delay: duration
on_success:
  extract: {field_mapping}
on_error: [error_handler_list]
```

### Event Operations

```yaml
# Publish
operation: event_publish
event_type: event_name
data: {event_data}

# Subscribe
operation: event_subscribe
event_type: event_name
handler: handler_node_id
```

### Data Transformation

```yaml
operation: data_transform
input: expression
transform: map | filter | reduce | aggregate
function: transformation_function
output: variable_name
```

### String Template

```yaml
operation: string_template
template: "template with {placeholders}"
parameters: {param_map}
output: variable_name
```

## Validation Rules

### Syntax Validation

1. Valid YAML structure
2. Required fields present
3. Type correctness (string, integer, etc.)
4. Enum values are valid
5. References to other nodes exist

### Semantic Validation

1. **Type consistency**: Inputs match parameter types
2. **Contract satisfiability**: Contracts are not contradictory
3. **Capability closure**: All required capabilities declared
4. **Flow completeness**: All execution paths return result
5. **Error coverage**: All error cases handled

### Example Validator

```python
class SIRValidator:
    def validate(self, vesper_file: str) -> ValidationResult:
        # Parse YAML
        node = yaml.safe_load(open(vesper_file))

        errors = []

        # Required fields
        if 'node_id' not in node:
            errors.append("Missing required field: node_id")

        # Type validation
        if 'inputs' in node:
            for name, spec in node['inputs'].items():
                if 'type' not in spec:
                    errors.append(f"Input {name} missing type")

        # Contract validation
        if 'contracts' in node:
            if not self.validate_contracts(node['contracts']):
                errors.append("Contracts are contradictory")

        # Flow validation
        if 'flow' in node:
            if not self.validate_flow_completeness(node['flow']):
                errors.append("Flow does not cover all paths")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors
        )
```

## Versioning Strategy

### Semantic Versioning

Node IDs use semantic versioning: `{name}_v{major}.{minor}.{patch}`

- **Major**: Breaking changes (input/output schema changes)
- **Minor**: Backward-compatible additions
- **Patch**: Bug fixes, performance improvements

### Breaking Changes

Changes that require major version bump:
- Removing input parameters
- Changing input/output types
- Removing output fields
- Changing error codes
- Modifying contracts (stricter preconditions, weaker postconditions)

### Non-Breaking Changes

Changes that only require minor version bump:
- Adding optional input parameters (with defaults)
- Adding output fields
- Adding error codes
- Improving performance
- Tightening postconditions (stronger guarantees)

## Examples

### Simple Function

```yaml
node_id: add_numbers_v1
type: function
intent: add_two_numbers

inputs:
  a: {type: integer}
  b: {type: integer}

outputs:
  result: integer

contracts:
  postconditions:
    - "result == a + b"

flow:
  - step: compute_sum
    operation: arithmetic
    expression: "a + b"
    output: result
```

### HTTP Handler

```yaml
node_id: get_user_profile_v1
type: http_handler
intent: retrieve_user_profile

inputs:
  user_id: {type: string, constraints: [non_empty]}

outputs:
  success:
    user:
      type: User
  error:
    error_code: {type: enum, values: [not_found, unauthorized]}
    message: string

contracts:
  preconditions:
    - "request.authenticated"
  postconditions:
    - "success => user.id == user_id"

flow:
  - step: check_auth
    operation: validation
    guards: ["request.has_valid_token"]

  - step: query_database
    operation: database_query
    query: "SELECT * FROM users WHERE id = {user_id}"
    on_result:
      if_found:
        return_success:
          user: "{query_result}"
      if_empty:
        return_error:
          error_code: not_found
          message: "User not found"
```

### Event Handler

```yaml
node_id: process_order_created_v1
type: event_handler
intent: handle_new_order_event

inputs:
  event:
    type: OrderCreatedEvent
    fields:
      order_id: string
      user_id: string
      items: array<OrderItem>

outputs:
  success:
    processed: boolean
  error:
    error_code: enum[validation_failed, processing_failed]
    message: string

flow:
  - step: validate_order
    operation: validation
    guards:
      - "event.items.length > 0"
      - "event.total_amount > 0"

  - step: reserve_inventory
    operation: call_node
    node_id: inventory_reservation_v2
    parameters:
      items: "{event.items}"

  - step: send_confirmation_email
    operation: call_node
    node_id: email_sender_v1
    parameters:
      to: "{event.user.email}"
      template: order_confirmation
      data: "{event}"
```

## Extension Points

### Custom Operations

Implementations can extend with custom operations:

```yaml
flow:
  - step: custom_ml_inference
    operation: custom.machine_learning.inference
    model: recommendation_model_v3
    input_features: [user_history, context]
```

### Custom Types

Define domain-specific types:

```yaml
types:
  EmailAddress:
    base: string
    constraints:
      - pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"

  USPhoneNumber:
    base: string
    constraints:
      - pattern: "^\\+1[0-9]{10}$"
```

## Best Practices

1. **Descriptive intent**: Write clear, human-readable intent statements
2. **Comprehensive contracts**: Specify all preconditions and postconditions
3. **Error handling**: Cover all error cases explicitly
4. **Idempotency**: Use idempotency keys for state-changing operations
5. **Observability**: Add metrics and alerts for production nodes
6. **Testing**: Include test cases and property tests
7. **Documentation**: Add examples and migration notes
8. **Versioning**: Follow semantic versioning strictly

## Future Extensions

Planned for v0.2:
- **Concurrency primitives**: Parallel execution, locks, transactions
- **Streaming operations**: Handle streams of data
- **Advanced types**: Generics, union types, algebraic data types
- **Formal verification**: Integration with proof assistants
- **Cross-language FFI**: Call into C/Rust/Go directly

## Changelog

### v0.1 (2025-01-08)
- Initial specification
- Core fields and operations
- Contract language
- Validation rules
