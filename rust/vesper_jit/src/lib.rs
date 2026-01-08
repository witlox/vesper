//! Vesper JIT Compiler
//!
//! JIT compilation of Vesper specifications for optimized execution.
//! This crate provides hot-path detection and native code generation.

pub mod hot_path;
pub mod compiler;

pub use hot_path::HotPathDetector;
pub use compiler::JitCompiler;

