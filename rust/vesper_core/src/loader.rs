//! Vesper specification loader

use crate::error::{Result, VesperError};
use crate::types::VesperNode;
use std::path::Path;

/// Loads Vesper specification files
pub struct VesperLoader {
    /// Base path for resolving relative imports
    #[allow(dead_code)]
    base_path: Option<std::path::PathBuf>,
}

impl VesperLoader {
    /// Create a new loader
    pub fn new() -> Self {
        Self { base_path: None }
    }

    /// Create a loader with a base path
    pub fn with_base_path<P: AsRef<Path>>(path: P) -> Self {
        Self {
            base_path: Some(path.as_ref().to_path_buf()),
        }
    }

    /// Load a Vesper node from a file
    pub fn load_file<P: AsRef<Path>>(&self, path: P) -> Result<VesperNode> {
        let content = std::fs::read_to_string(path)?;
        self.load_string(&content)
    }

    /// Load a Vesper node from a YAML string
    pub fn load_string(&self, content: &str) -> Result<VesperNode> {
        let node: VesperNode = serde_yaml::from_str(content)?;
        self.validate(&node)?;
        Ok(node)
    }

    /// Validate a loaded node
    fn validate(&self, node: &VesperNode) -> Result<()> {
        // Validate node_id format
        if !node.node_id.contains("_v") {
            return Err(VesperError::ValidationError {
                path: "node_id".to_string(),
                message: format!(
                    "Invalid node_id format: {}. Expected: name_vN",
                    node.node_id
                ),
            });
        }

        // Validate inputs have types
        for (name, spec) in &node.inputs {
            if spec.input_type.is_empty() {
                return Err(VesperError::ValidationError {
                    path: format!("inputs.{}", name),
                    message: "Missing type field".to_string(),
                });
            }
        }

        // Validate flow is not empty
        if node.flow.is_empty() {
            tracing::warn!("Node {} has no flow steps defined", node.node_id);
        }

        Ok(())
    }
}

impl Default for VesperLoader {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_load_simple_node() {
        let yaml = r#"
node_id: test_v1
type: function
intent: test function

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
    template: "Hello!"
"#;

        let loader = VesperLoader::new();
        let node = loader.load_string(yaml).unwrap();

        assert_eq!(node.node_id, "test_v1");
        assert_eq!(node.intent, "test function");
    }

    #[test]
    fn test_invalid_node_id() {
        let yaml = r#"
node_id: invalid
type: function
intent: test

inputs: {}

flow: []
"#;

        let loader = VesperLoader::new();
        let result = loader.load_string(yaml);

        assert!(result.is_err());
    }
}
