use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

pub type Tag = (String, u64);

#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct ORSet {
    elements: HashMap<String, HashSet<Tag>>,
    tombstones: HashMap<String, HashSet<Tag>>,
    counter: u64,
}

impl ORSet {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add(&mut self, value: &str, agent_did: &str) -> Tag {
        self.counter += 1;
        let tag = (agent_did.to_string(), self.counter);
        self.elements
            .entry(value.to_string())
            .or_default()
            .insert(tag.clone());
        tag
    }

    pub fn remove(&mut self, value: &str) -> Vec<Tag> {
        let observed: Vec<Tag> = self
            .elements
            .get(value)
            .map(|tags| tags.iter().cloned().collect())
            .unwrap_or_default();
        if let Some(tags) = self.elements.get_mut(value) {
            for tag in &observed {
                tags.remove(tag);
            }
            if tags.is_empty() {
                self.elements.remove(value);
            }
        }
        self.tombstones
            .entry(value.to_string())
            .or_default()
            .extend(observed.iter().cloned());
        observed
    }

    pub fn contains(&self, value: &str) -> bool {
        self.elements
            .get(value)
            .map(|tags| !tags.is_empty())
            .unwrap_or(false)
    }

    pub fn elements_list(&self) -> Vec<String> {
        self.elements
            .iter()
            .filter(|(_, tags)| !tags.is_empty())
            .map(|(value, _)| value.clone())
            .collect()
    }

    pub fn merge(&mut self, other: &ORSet) {
        for (value, tags) in &other.elements {
            let tombstones = self.tombstones.get(value);
            for tag in tags {
                if tombstones.map(|set| !set.contains(tag)).unwrap_or(true) {
                    self.elements
                        .entry(value.clone())
                        .or_default()
                        .insert(tag.clone());
                }
            }
        }
        for (value, tags) in &other.tombstones {
            self.tombstones
                .entry(value.clone())
                .or_default()
                .extend(tags.iter().cloned());
            if let Some(existing) = self.elements.get_mut(value) {
                for tag in tags {
                    existing.remove(tag);
                }
                if existing.is_empty() {
                    self.elements.remove(value);
                }
            }
        }
    }
}
