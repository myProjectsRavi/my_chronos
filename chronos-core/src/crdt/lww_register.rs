use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LWWRegister<T: Clone> {
    pub value: T,
    pub timestamp: u64,
    pub agent_did: String,
}

impl<T: Clone> LWWRegister<T> {
    pub fn new(value: T, timestamp: u64, agent_did: String) -> Self {
        Self {
            value,
            timestamp,
            agent_did,
        }
    }

    pub fn merge(&self, other: &Self) -> Self {
        if self.timestamp > other.timestamp {
            self.clone()
        } else if self.timestamp < other.timestamp {
            other.clone()
        } else if self.agent_did >= other.agent_did {
            self.clone()
        } else {
            other.clone()
        }
    }

    pub fn update(&self, value: T, timestamp: u64, agent_did: String) -> Self {
        let candidate = Self {
            value,
            timestamp,
            agent_did,
        };
        self.merge(&candidate)
    }
}
