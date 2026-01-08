# Hello World Example

This is the simplest Vesper example - a greeting function that demonstrates the basic structure of a Vesper specification.

## What it demonstrates

- Basic node structure (node_id, type, intent)
- Input specification with constraints
- Output specification with success and error cases
- Contracts (preconditions and postconditions)
- Flow steps with validation and string templates
- Test cases

## Running the example

```bash
# Validate the specification
vesper compile --validate-only hello_world.vsp

# Show information about the node
vesper show hello_world.vsp

# Generate Python code
vesper codegen hello_world.vsp

# Run with inputs
vesper run hello_world.vsp -i name=World

# Run tests
vesper test hello_world.vsp
```

## Using in Python

```python
from vesper import VesperRuntime

runtime = VesperRuntime()
runtime.load_node("hello_world.vsp")

result = runtime.execute_sync("hello_world_v1", {"name": "Developer"})

if result.success:
    print(result.data)
else:
    print(f"Error: {result.error}")
```

