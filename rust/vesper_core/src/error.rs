//! Error types for Vesper Core

use thiserror::Error;

/// Result type for Vesper operations
pub type Result<T> = std::result::Result<T, VesperError>;

/// Errors that can occur during Vesper execution
#[derive(Error, Debug)]
pub enum VesperError {
    /// Error parsing a Vesper specification
    #[error("Parse error: {0}")]
    ParseError(String),

    /// Error validating a Vesper node
    #[error("Validation error at {path}: {message}")]
    ValidationError { path: String, message: String },

    /// Contract precondition failed
    #[error("Precondition failed: {0}")]
    PreconditionFailed(String),

    /// Contract postcondition failed
    #[error("Postcondition failed: {0}")]
    PostconditionFailed(String),

    /// Contract invariant violated
    #[error("Invariant violated: {0}")]
    InvariantViolated(String),

    /// Type error during execution
    #[error("Type error: expected {expected}, got {actual}")]
    TypeError { expected: String, actual: String },

    /// Unknown operation
    #[error("Unknown operation: {0}")]
    UnknownOperation(String),

    /// Missing required input
    #[error("Missing required input: {0}")]
    MissingInput(String),

    /// Execution error
    #[error("Execution error: {0}")]
    ExecutionError(String),

    /// IO error
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    /// YAML parsing error
    #[error("YAML error: {0}")]
    YamlError(#[from] serde_yaml::Error),

    /// JSON error
    #[error("JSON error: {0}")]
    JsonError(#[from] serde_json::Error),
}

