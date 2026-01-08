# Payment Handler Example

This example demonstrates a more complex Vesper specification for processing credit card payments.

## What it demonstrates

- HTTP handler node type
- Complex input validation with patterns
- External API calls with retry policies
- Database operations
- Error handling with different strategies
- Security capabilities
- Performance requirements
- Observability configuration (metrics, alerts, tracing)
- Comprehensive testing

## Key Features

### Idempotency
The handler supports idempotency keys to prevent duplicate payments:
```yaml
check_idempotency:
  operation: conditional
  condition: "idempotency_key IS NOT NULL"
```

### Retry Policy
External API calls have configurable retry behavior:
```yaml
retry_policy:
  max_attempts: 3
  backoff: exponential
  initial_delay: 1s
```

### Security
Explicit capability requirements and denials:
```yaml
security:
  capabilities_required:
    - database.write.transactions
    - network.http_client.stripe.com
  denied_capabilities:
    - filesystem.write
```

## Running the example

```bash
# Validate the specification
vesper compile --validate-only payment_handler.vsp

# Show the node structure
vesper show payment_handler.vsp

# Generate Python code
vesper compile payment_handler.vsp -o payment_handler.py
```

## Production Considerations

This is an example - in production you would:
1. Implement actual Stripe API integration
2. Set up proper database connections
3. Configure monitoring and alerting
4. Run through the dual-path verification system

