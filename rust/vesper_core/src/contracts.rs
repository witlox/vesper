//! Contract validation for Vesper nodes

use crate::error::{Result, VesperError};
use crate::types::{Contracts, Value};
use std::collections::HashMap;

/// Contract validator
pub struct ContractValidator {
    /// Enable strict mode (fail on any contract violation)
    strict: bool,
}

impl ContractValidator {
    /// Create a new validator
    pub fn new() -> Self {
        Self { strict: true }
    }

    /// Create a permissive validator
    pub fn permissive() -> Self {
        Self { strict: false }
    }

    /// Check preconditions before execution
    pub fn check_preconditions(
        &self,
        contracts: &Contracts,
        inputs: &HashMap<String, Value>,
    ) -> Result<()> {
        for condition in &contracts.preconditions {
            if !self.evaluate_condition(condition, inputs, &HashMap::new())? {
                if self.strict {
                    return Err(VesperError::PreconditionFailed(condition.clone()));
                }
                tracing::warn!("Precondition failed: {}", condition);
            }
        }
        Ok(())
    }

    /// Check postconditions after execution
    pub fn check_postconditions(
        &self,
        contracts: &Contracts,
        inputs: &HashMap<String, Value>,
        outputs: &HashMap<String, Value>,
    ) -> Result<()> {
        for condition in &contracts.postconditions {
            if !self.evaluate_condition(condition, inputs, outputs)? {
                if self.strict {
                    return Err(VesperError::PostconditionFailed(condition.clone()));
                }
                tracing::warn!("Postcondition failed: {}", condition);
            }
        }
        Ok(())
    }

    /// Check invariants
    pub fn check_invariants(
        &self,
        contracts: &Contracts,
        context: &HashMap<String, Value>,
    ) -> Result<()> {
        for invariant in &contracts.invariants {
            if !self.evaluate_condition(invariant, context, &HashMap::new())? {
                if self.strict {
                    return Err(VesperError::InvariantViolated(invariant.clone()));
                }
                tracing::warn!("Invariant violated: {}", invariant);
            }
        }
        Ok(())
    }

    /// Evaluate a condition expression
    fn evaluate_condition(
        &self,
        condition: &str,
        inputs: &HashMap<String, Value>,
        outputs: &HashMap<String, Value>,
    ) -> Result<bool> {
        let condition = condition.trim();

        // Handle simple comparisons
        if let Some(result) = self.try_evaluate_comparison(condition, inputs, outputs)? {
            return Ok(result);
        }

        // Handle logical operators
        if condition.contains(" AND ") {
            let parts: Vec<&str> = condition.split(" AND ").collect();
            for part in parts {
                if !self.evaluate_condition(part.trim(), inputs, outputs)? {
                    return Ok(false);
                }
            }
            return Ok(true);
        }

        if condition.contains(" OR ") {
            let parts: Vec<&str> = condition.split(" OR ").collect();
            for part in parts {
                if self.evaluate_condition(part.trim(), inputs, outputs)? {
                    return Ok(true);
                }
            }
            return Ok(false);
        }

        // Default: condition passes (we can't evaluate it)
        tracing::debug!("Cannot evaluate condition, assuming true: {}", condition);
        Ok(true)
    }

    /// Try to evaluate a simple comparison
    fn try_evaluate_comparison(
        &self,
        condition: &str,
        inputs: &HashMap<String, Value>,
        outputs: &HashMap<String, Value>,
    ) -> Result<Option<bool>> {
        // Check for comparison operators
        for (op, evaluator) in [
            ("==", Self::eval_eq as fn(&Value, &Value) -> bool),
            ("!=", Self::eval_ne as fn(&Value, &Value) -> bool),
            (">=", Self::eval_ge as fn(&Value, &Value) -> bool),
            ("<=", Self::eval_le as fn(&Value, &Value) -> bool),
            (">", Self::eval_gt as fn(&Value, &Value) -> bool),
            ("<", Self::eval_lt as fn(&Value, &Value) -> bool),
        ] {
            if let Some(idx) = condition.find(op) {
                let left = condition[..idx].trim();
                let right = condition[idx + op.len()..].trim();

                let left_val = self.resolve_value(left, inputs, outputs);
                let right_val = self.resolve_value(right, inputs, outputs);

                return Ok(Some(evaluator(&left_val, &right_val)));
            }
        }

        Ok(None)
    }

    /// Resolve a value from a string (variable or literal)
    fn resolve_value(
        &self,
        s: &str,
        inputs: &HashMap<String, Value>,
        outputs: &HashMap<String, Value>,
    ) -> Value {
        let s = s.trim().trim_matches('\'').trim_matches('"');

        // Check outputs first
        if let Some(val) = outputs.get(s) {
            return val.clone();
        }

        // Then inputs
        if let Some(val) = inputs.get(s) {
            return val.clone();
        }

        // Try as a number
        if let Ok(n) = s.parse::<i64>() {
            return Value::Int(n);
        }
        if let Ok(n) = s.parse::<f64>() {
            return Value::Float(n);
        }

        // Try as boolean
        if s == "true" {
            return Value::Bool(true);
        }
        if s == "false" {
            return Value::Bool(false);
        }

        // Return as string
        Value::String(s.to_string())
    }

    fn eval_eq(left: &Value, right: &Value) -> bool {
        left == right
    }

    fn eval_ne(left: &Value, right: &Value) -> bool {
        left != right
    }

    fn eval_gt(left: &Value, right: &Value) -> bool {
        match (left, right) {
            (Value::Int(a), Value::Int(b)) => a > b,
            (Value::Float(a), Value::Float(b)) => a > b,
            (Value::Int(a), Value::Float(b)) => (*a as f64) > *b,
            (Value::Float(a), Value::Int(b)) => *a > (*b as f64),
            _ => false,
        }
    }

    fn eval_lt(left: &Value, right: &Value) -> bool {
        match (left, right) {
            (Value::Int(a), Value::Int(b)) => a < b,
            (Value::Float(a), Value::Float(b)) => a < b,
            (Value::Int(a), Value::Float(b)) => (*a as f64) < *b,
            (Value::Float(a), Value::Int(b)) => *a < (*b as f64),
            _ => false,
        }
    }

    fn eval_ge(left: &Value, right: &Value) -> bool {
        Self::eval_gt(left, right) || Self::eval_eq(left, right)
    }

    fn eval_le(left: &Value, right: &Value) -> bool {
        Self::eval_lt(left, right) || Self::eval_eq(left, right)
    }
}

impl Default for ContractValidator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple_comparison() {
        let validator = ContractValidator::new();

        let mut inputs = HashMap::new();
        inputs.insert("amount".to_string(), Value::Int(100));

        let contracts = Contracts {
            preconditions: vec!["amount > 0".to_string()],
            postconditions: vec![],
            invariants: vec![],
        };

        assert!(validator.check_preconditions(&contracts, &inputs).is_ok());
    }

    #[test]
    fn test_failing_precondition() {
        let validator = ContractValidator::new();

        let mut inputs = HashMap::new();
        inputs.insert("amount".to_string(), Value::Int(-10));

        let contracts = Contracts {
            preconditions: vec!["amount > 0".to_string()],
            postconditions: vec![],
            invariants: vec![],
        };

        assert!(validator.check_preconditions(&contracts, &inputs).is_err());
    }
}
