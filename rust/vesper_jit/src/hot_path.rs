//! Hot path detection for JIT compilation

use std::collections::HashMap;

/// Tracks execution counts and determines which paths should be JIT compiled
pub struct HotPathDetector {
    /// Execution counts per node
    call_counts: HashMap<String, usize>,
    /// Threshold for triggering compilation
    compilation_threshold: usize,
}

impl HotPathDetector {
    /// Create a new detector with default threshold
    pub fn new() -> Self {
        Self {
            call_counts: HashMap::new(),
            compilation_threshold: 100,
        }
    }

    /// Create a detector with custom threshold
    pub fn with_threshold(threshold: usize) -> Self {
        Self {
            call_counts: HashMap::new(),
            compilation_threshold: threshold,
        }
    }

    /// Record an execution and check if compilation should be triggered
    pub fn record_execution(&mut self, node_id: &str) -> bool {
        let count = self.call_counts.entry(node_id.to_string()).or_insert(0);
        *count += 1;
        *count >= self.compilation_threshold
    }

    /// Check if a node should be compiled
    pub fn should_compile(&self, node_id: &str) -> bool {
        self.call_counts
            .get(node_id)
            .map(|&c| c >= self.compilation_threshold)
            .unwrap_or(false)
    }

    /// Get the execution count for a node
    pub fn get_count(&self, node_id: &str) -> usize {
        self.call_counts.get(node_id).copied().unwrap_or(0)
    }

    /// Reset all counts
    pub fn reset(&mut self) {
        self.call_counts.clear();
    }
}

impl Default for HotPathDetector {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hot_path_detection() {
        let mut detector = HotPathDetector::with_threshold(10);

        // Not hot yet
        for _ in 0..9 {
            assert!(!detector.record_execution("test_v1"));
        }

        // Now it's hot
        assert!(detector.record_execution("test_v1"));
        assert!(detector.should_compile("test_v1"));
    }

    #[test]
    fn test_separate_tracking() {
        let mut detector = HotPathDetector::with_threshold(5);

        for _ in 0..5 {
            detector.record_execution("node_a_v1");
        }

        assert!(detector.should_compile("node_a_v1"));
        assert!(!detector.should_compile("node_b_v1"));
    }
}

