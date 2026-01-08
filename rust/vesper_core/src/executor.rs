//! Semantic executor for Vesper nodes

use crate::error::{Result, VesperError};
use crate::types::{FlowStep, Value, VesperNode};
use std::collections::HashMap;

/// Result of executing a Vesper node
#[derive(Debug, Clone)]
pub struct ExecutionResult {
    /// Whether execution succeeded
    pub success: bool,
    /// Output data on success
    pub data: Option<Value>,
    /// Error information on failure
    pub error: Option<ExecutionError>,
    /// Execution duration in milliseconds
    pub duration_ms: f64,
}

/// Error information
#[derive(Debug, Clone)]
pub struct ExecutionError {
    /// Error code
    pub code: String,
    /// Error message
    pub message: String,
}

/// Execution context containing variables
pub struct ExecutionContext {
    /// Variable bindings
    variables: HashMap<String, Value>,
    /// Input values
    inputs: HashMap<String, Value>,
}

impl ExecutionContext {
    /// Create a new context with inputs
    pub fn new(inputs: HashMap<String, Value>) -> Self {
        Self {
            variables: HashMap::new(),
            inputs,
        }
    }

    /// Get a variable or input value
    pub fn get(&self, name: &str) -> Option<&Value> {
        self.variables.get(name).or_else(|| self.inputs.get(name))
    }

    /// Set a variable
    pub fn set(&mut self, name: String, value: Value) {
        self.variables.insert(name, value);
    }

    /// Get an input value
    pub fn get_input(&self, name: &str) -> Option<&Value> {
        self.inputs.get(name)
    }
}

/// Semantic executor for Vesper nodes
pub struct SemanticExecutor {
    /// Loaded nodes
    nodes: HashMap<String, VesperNode>,
}

impl SemanticExecutor {
    /// Create a new executor
    pub fn new() -> Self {
        Self {
            nodes: HashMap::new(),
        }
    }

    /// Register a node with the executor
    pub fn register(&mut self, node: VesperNode) {
        self.nodes.insert(node.node_id.clone(), node);
    }

    /// Execute a node with given inputs
    pub fn execute(
        &self,
        node_id: &str,
        inputs: HashMap<String, Value>,
    ) -> Result<ExecutionResult> {
        let start = std::time::Instant::now();

        let node = self
            .nodes
            .get(node_id)
            .ok_or_else(|| VesperError::ExecutionError(format!("Node not found: {}", node_id)))?;

        // Validate inputs
        self.validate_inputs(node, &inputs)?;

        // Check preconditions
        if let Some(contracts) = &node.contracts {
            for precondition in &contracts.preconditions {
                // TODO: Implement proper condition evaluation
                tracing::debug!("Checking precondition: {}", precondition);
            }
        }

        // Execute flow
        let mut ctx = ExecutionContext::new(inputs);
        let result = self.execute_flow(node, &mut ctx)?;

        let duration_ms = start.elapsed().as_secs_f64() * 1000.0;

        Ok(ExecutionResult {
            success: true,
            data: Some(result),
            error: None,
            duration_ms,
        })
    }

    /// Validate inputs against node specification
    fn validate_inputs(&self, node: &VesperNode, inputs: &HashMap<String, Value>) -> Result<()> {
        for (name, spec) in &node.inputs {
            if spec.required && !inputs.contains_key(name) {
                return Err(VesperError::MissingInput(name.clone()));
            }
        }
        Ok(())
    }

    /// Execute the flow steps
    fn execute_flow(&self, node: &VesperNode, ctx: &mut ExecutionContext) -> Result<Value> {
        let mut last_result = Value::Null;

        for step in &node.flow {
            last_result = self.execute_step(step, ctx)?;

            // Check for early return
            if step.return_success.is_some() || step.return_error.is_some() {
                break;
            }
        }

        Ok(last_result)
    }

    /// Execute a single flow step
    fn execute_step(&self, step: &FlowStep, ctx: &mut ExecutionContext) -> Result<Value> {
        tracing::debug!("Executing step: {} ({})", step.step, step.operation);

        match step.operation.as_str() {
            "validation" => self.execute_validation(step, ctx),
            "string_template" => self.execute_template(step, ctx),
            "arithmetic" => self.execute_arithmetic(step, ctx),
            "return" => self.execute_return(step, ctx),
            "conditional" => self.execute_conditional(step, ctx),
            _ => {
                tracing::warn!("Unknown operation: {}", step.operation);
                Ok(Value::Null)
            }
        }
    }

    /// Execute a validation step
    fn execute_validation(&self, step: &FlowStep, _ctx: &ExecutionContext) -> Result<Value> {
        for guard in &step.guards {
            // TODO: Implement proper guard evaluation
            tracing::debug!("Checking guard: {}", guard);
        }
        Ok(Value::Bool(true))
    }

    /// Execute a string template step
    fn execute_template(&self, step: &FlowStep, ctx: &mut ExecutionContext) -> Result<Value> {
        let template = step.template.as_ref().ok_or_else(|| {
            VesperError::ExecutionError("Template step missing template".to_string())
        })?;

        // Simple template substitution
        let mut result = template.clone();

        // Replace {variable} patterns
        for (name, value) in ctx.inputs.iter() {
            let placeholder = format!("{{{}}}", name);
            if result.contains(&placeholder) {
                let replacement = match value {
                    Value::String(s) => s.clone(),
                    Value::Int(i) => i.to_string(),
                    Value::Float(f) => f.to_string(),
                    Value::Bool(b) => b.to_string(),
                    _ => format!("{:?}", value),
                };
                result = result.replace(&placeholder, &replacement);
            }
        }

        // Store result in output variable
        if let Some(output) = &step.output {
            ctx.set(output.clone(), Value::String(result.clone()));
        }

        Ok(Value::String(result))
    }

    /// Execute an arithmetic step
    fn execute_arithmetic(&self, step: &FlowStep, ctx: &mut ExecutionContext) -> Result<Value> {
        let expression = step.expression.as_ref().ok_or_else(|| {
            VesperError::ExecutionError("Arithmetic step missing expression".to_string())
        })?;

        // Very simple expression evaluation (a + b, a - b, a * b, a / b)
        // TODO: Implement proper expression parser
        let result = self.evaluate_simple_expression(expression, ctx)?;

        if let Some(output) = &step.output {
            ctx.set(output.clone(), result.clone());
        }

        Ok(result)
    }

    /// Evaluate a simple arithmetic expression
    fn evaluate_simple_expression(
        &self,
        expression: &str,
        ctx: &ExecutionContext,
    ) -> Result<Value> {
        let expr = expression.trim();

        // Try to parse as a simple binary operation
        for op in [" + ", " - ", " * ", " / "] {
            if let Some(idx) = expr.find(op) {
                let left = expr[..idx].trim();
                let right = expr[idx + op.len()..].trim();

                let left_val = self.get_numeric_value(left, ctx)?;
                let right_val = self.get_numeric_value(right, ctx)?;

                let result = match op.trim() {
                    "+" => left_val + right_val,
                    "-" => left_val - right_val,
                    "*" => left_val * right_val,
                    "/" => {
                        if right_val == 0.0 {
                            return Err(VesperError::ExecutionError(
                                "Division by zero".to_string(),
                            ));
                        }
                        left_val / right_val
                    }
                    _ => unreachable!(),
                };

                return Ok(if result.fract() == 0.0 {
                    Value::Int(result as i64)
                } else {
                    Value::Float(result)
                });
            }
        }

        // Try as a single value
        let val = self.get_numeric_value(expr, ctx)?;
        Ok(if val.fract() == 0.0 {
            Value::Int(val as i64)
        } else {
            Value::Float(val)
        })
    }

    /// Get a numeric value from a string (variable name or literal)
    fn get_numeric_value(&self, s: &str, ctx: &ExecutionContext) -> Result<f64> {
        // Try as a number literal
        if let Ok(n) = s.parse::<f64>() {
            return Ok(n);
        }

        // Try as a variable
        if let Some(value) = ctx.get(s) {
            return value.as_float().ok_or_else(|| VesperError::TypeError {
                expected: "number".to_string(),
                actual: format!("{:?}", value),
            });
        }

        Err(VesperError::ExecutionError(format!(
            "Unknown variable or invalid number: {}",
            s
        )))
    }

    /// Execute a return step
    fn execute_return(&self, step: &FlowStep, ctx: &ExecutionContext) -> Result<Value> {
        if let Some(success_data) = &step.return_success {
            let mut result = HashMap::new();
            for (key, value) in success_data {
                // Resolve variable references
                let resolved = self.resolve_value(value, ctx);
                result.insert(key.clone(), resolved);
            }
            return Ok(Value::Object(result));
        }

        if let Some(error_data) = &step.return_error {
            let code = error_data
                .get("error_code")
                .and_then(|v| v.as_str())
                .map(String::from)
                .unwrap_or_else(|| "unknown".to_string());
            let message = error_data
                .get("message")
                .and_then(|v| v.as_str())
                .map(String::from)
                .unwrap_or_else(|| "An error occurred".to_string());

            return Err(VesperError::ExecutionError(format!(
                "{}: {}",
                code, message
            )));
        }

        Ok(Value::Null)
    }

    /// Execute a conditional step
    fn execute_conditional(&self, step: &FlowStep, _ctx: &mut ExecutionContext) -> Result<Value> {
        // TODO: Implement proper condition evaluation
        let condition = step.condition.as_ref().ok_or_else(|| {
            VesperError::ExecutionError("Conditional step missing condition".to_string())
        })?;

        tracing::debug!("Evaluating condition: {}", condition);

        // For now, just return null
        Ok(Value::Null)
    }

    /// Resolve a YAML value, substituting variable references
    #[allow(clippy::only_used_in_recursion)]
    fn resolve_value(&self, value: &serde_yaml::Value, ctx: &ExecutionContext) -> Value {
        match value {
            serde_yaml::Value::String(s) => {
                // Check for variable reference pattern {var}
                if s.starts_with('{') && s.ends_with('}') && s.len() > 2 {
                    let var_name = &s[1..s.len() - 1];
                    if let Some(val) = ctx.get(var_name) {
                        return val.clone();
                    }
                }
                Value::String(s.clone())
            }
            serde_yaml::Value::Number(n) => {
                if let Some(i) = n.as_i64() {
                    Value::Int(i)
                } else if let Some(f) = n.as_f64() {
                    Value::Float(f)
                } else {
                    Value::Null
                }
            }
            serde_yaml::Value::Bool(b) => Value::Bool(*b),
            serde_yaml::Value::Null => Value::Null,
            serde_yaml::Value::Sequence(seq) => {
                Value::Array(seq.iter().map(|v| self.resolve_value(v, ctx)).collect())
            }
            serde_yaml::Value::Mapping(map) => {
                let mut result = HashMap::new();
                for (k, v) in map {
                    if let serde_yaml::Value::String(key) = k {
                        result.insert(key.clone(), self.resolve_value(v, ctx));
                    }
                }
                Value::Object(result)
            }
            _ => Value::Null,
        }
    }
}

impl Default for SemanticExecutor {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::loader::VesperLoader;

    #[test]
    fn test_execute_arithmetic() {
        let yaml = r#"
node_id: add_v1
type: function
intent: add numbers

inputs:
  a:
    type: integer
  b:
    type: integer

outputs:
  success:
    result:
      type: integer

flow:
  - step: add
    operation: arithmetic
    expression: "a + b"
    output: result
"#;

        let loader = VesperLoader::new();
        let node = loader.load_string(yaml).unwrap();

        let mut executor = SemanticExecutor::new();
        executor.register(node);

        let mut inputs = HashMap::new();
        inputs.insert("a".to_string(), Value::Int(5));
        inputs.insert("b".to_string(), Value::Int(3));

        let result = executor.execute("add_v1", inputs).unwrap();

        assert!(result.success);
        assert_eq!(result.data, Some(Value::Int(8)));
    }

    #[test]
    fn test_execute_template() {
        let yaml = r#"
node_id: greet_v1
type: function
intent: greet user

inputs:
  name:
    type: string

outputs:
  success:
    message:
      type: string

flow:
  - step: greet
    operation: string_template
    template: "Hello, {name}!"
    output: message
"#;

        let loader = VesperLoader::new();
        let node = loader.load_string(yaml).unwrap();

        let mut executor = SemanticExecutor::new();
        executor.register(node);

        let mut inputs = HashMap::new();
        inputs.insert("name".to_string(), Value::String("World".to_string()));

        let result = executor.execute("greet_v1", inputs).unwrap();

        assert!(result.success);
        assert_eq!(
            result.data,
            Some(Value::String("Hello, World!".to_string()))
        );
    }
}
