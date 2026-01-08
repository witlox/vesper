# Data Pipeline Example

This example shows how to build data transformation pipelines in Vesper.

## What it demonstrates

- Data transform node type
- Custom type definitions
- Filter and aggregate operations
- Property-based testing for data invariants
- Complex output structures

## Key Features

### Custom Types
Define domain-specific types:
```yaml
types:
  SalesRecord:
    fields:
      id: {type: string}
      amount: {type: decimal}
      category: {type: string}
```

### Data Transformations
Chain filter, map, and reduce operations:
```yaml
- step: filter_by_date
  operation: data_transform
  transform: filter
  function: "record.timestamp >= start_date"
```

### Property Testing
Verify data invariants:
```yaml
property_tests:
  - property: sum_consistency
    invariant: "SUM(categories.total_sales) == summary.total_sales"
```

## Running the example

```bash
vesper show data_pipeline.vsp
vesper compile data_pipeline.vsp
```

