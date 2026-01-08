//! Vesper Core
//!
//! Core semantic interpreter for the Vesper framework.
//! This crate provides direct execution of Vesper specifications
//! without intermediate Python code generation.

pub mod contracts;
pub mod error;
pub mod executor;
pub mod loader;
pub mod types;

pub use error::{Result, VesperError};
pub use executor::SemanticExecutor;
pub use loader::VesperLoader;
pub use types::{Value, VesperNode};
