//! Vesper Core
//!
//! Core semantic interpreter for the Vesper framework.
//! This crate provides direct execution of Vesper specifications
//! without intermediate Python code generation.

pub mod error;
pub mod loader;
pub mod executor;
pub mod types;
pub mod contracts;

pub use error::{VesperError, Result};
pub use loader::VesperLoader;
pub use executor::SemanticExecutor;
pub use types::{VesperNode, Value};

