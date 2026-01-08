//! Vesper JIT Compiler
//!
//! JIT compilation of Vesper specifications for optimized execution.
//! This crate provides hot-path detection and native code generation.

pub mod compiler;
pub mod hot_path;

pub use compiler::JitCompiler;
pub use hot_path::HotPathDetector;
