//! Type definitions for Vesper nodes

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// A complete Vesper semantic node
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VesperNode {
    /// Unique versioned identifier
    pub node_id: String,

    /// Type of the node
    #[serde(rename = "type")]
    pub node_type: NodeType,

    /// High-level purpose
    pub intent: String,

    /// Optional metadata
    #[serde(default)]
    pub metadata: Option<Metadata>,

    /// Input specifications
    #[serde(default)]
    pub inputs: HashMap<String, InputSpec>,

    /// Output specifications
    #[serde(default)]
    pub outputs: Option<Outputs>,

    /// Custom type definitions
    #[serde(default)]
    pub types: HashMap<String, CustomType>,

    /// Formal contracts
    #[serde(default)]
    pub contracts: Option<Contracts>,

    /// Execution flow
    #[serde(default)]
    pub flow: Vec<FlowStep>,

    /// Performance requirements
    #[serde(default)]
    pub performance: Option<Performance>,

    /// Security configuration
    #[serde(default)]
    pub security: Option<Security>,
}

/// Types of semantic nodes
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NodeType {
    Function,
    HttpHandler,
    EventHandler,
    DataTransform,
    StateMachine,
    Aggregation,
    ScheduledJob,
}

/// Node metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Metadata {
    pub author: Option<String>,
    pub created: Option<String>,
    pub version: Option<String>,
    pub description: Option<String>,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub dependencies: Vec<String>,
}

/// Input parameter specification
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InputSpec {
    #[serde(rename = "type")]
    pub input_type: String,

    #[serde(default = "default_true")]
    pub required: bool,

    #[serde(default)]
    pub constraints: Vec<String>,

    pub default: Option<serde_yaml::Value>,

    pub description: Option<String>,
}

fn default_true() -> bool {
    true
}

/// Output specifications
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Outputs {
    #[serde(default)]
    pub success: HashMap<String, OutputField>,

    #[serde(default)]
    pub error: HashMap<String, OutputField>,
}

/// Output field specification
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutputField {
    #[serde(rename = "type")]
    pub output_type: Option<String>,

    pub description: Option<String>,

    #[serde(default)]
    pub values: Vec<String>,
}

/// Custom type definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CustomType {
    pub base: Option<String>,

    #[serde(default)]
    pub fields: HashMap<String, serde_yaml::Value>,

    #[serde(default)]
    pub constraints: Vec<String>,
}

/// Formal contracts
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Contracts {
    #[serde(default)]
    pub preconditions: Vec<String>,

    #[serde(default)]
    pub postconditions: Vec<String>,

    #[serde(default)]
    pub invariants: Vec<String>,
}

/// A step in the execution flow
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FlowStep {
    /// Step name
    pub step: String,

    /// Operation type
    pub operation: String,

    /// Optional description
    pub description: Option<String>,

    /// Operation parameters
    #[serde(default)]
    pub parameters: HashMap<String, serde_yaml::Value>,

    /// Guard conditions
    #[serde(default)]
    pub guards: Vec<String>,

    /// Condition for conditional operations
    pub condition: Option<String>,

    /// String template for template operations
    pub template: Option<String>,

    /// Arithmetic expression
    pub expression: Option<String>,

    /// Output variable name
    pub output: Option<String>,

    /// On success handler
    pub on_success: Option<serde_yaml::Value>,

    /// On error handler
    pub on_error: Option<serde_yaml::Value>,

    /// On failure handler
    pub on_failure: Option<serde_yaml::Value>,

    /// Return success data
    pub return_success: Option<HashMap<String, serde_yaml::Value>>,

    /// Return error data
    pub return_error: Option<HashMap<String, serde_yaml::Value>>,
}

/// Performance requirements
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Performance {
    pub expected_latency_ms: Option<u64>,
    pub p99_latency_ms: Option<u64>,
    pub max_latency_ms: Option<u64>,
    pub memory_limit_mb: Option<u64>,
    pub timeout_seconds: Option<u64>,
}

/// Security configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Security {
    #[serde(default)]
    pub capabilities_required: Vec<String>,

    #[serde(default)]
    pub denied_capabilities: Vec<String>,

    #[serde(default)]
    pub sensitive_data: Vec<String>,

    pub audit_level: Option<String>,
}

/// Runtime value type
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Value {
    Null,
    Bool(bool),
    Int(i64),
    Float(f64),
    String(String),
    Array(Vec<Value>),
    Object(HashMap<String, Value>),
}

impl Value {
    /// Check if value is truthy
    pub fn is_truthy(&self) -> bool {
        match self {
            Value::Null => false,
            Value::Bool(b) => *b,
            Value::Int(i) => *i != 0,
            Value::Float(f) => *f != 0.0,
            Value::String(s) => !s.is_empty(),
            Value::Array(a) => !a.is_empty(),
            Value::Object(o) => !o.is_empty(),
        }
    }

    /// Get as string
    pub fn as_str(&self) -> Option<&str> {
        match self {
            Value::String(s) => Some(s),
            _ => None,
        }
    }

    /// Get as integer
    pub fn as_int(&self) -> Option<i64> {
        match self {
            Value::Int(i) => Some(*i),
            _ => None,
        }
    }

    /// Get as float
    pub fn as_float(&self) -> Option<f64> {
        match self {
            Value::Float(f) => Some(*f),
            Value::Int(i) => Some(*i as f64),
            _ => None,
        }
    }
}

impl From<String> for Value {
    fn from(s: String) -> Self {
        Value::String(s)
    }
}

impl From<&str> for Value {
    fn from(s: &str) -> Self {
        Value::String(s.to_string())
    }
}

impl From<i64> for Value {
    fn from(i: i64) -> Self {
        Value::Int(i)
    }
}

impl From<f64> for Value {
    fn from(f: f64) -> Self {
        Value::Float(f)
    }
}

impl From<bool> for Value {
    fn from(b: bool) -> Self {
        Value::Bool(b)
    }
}
