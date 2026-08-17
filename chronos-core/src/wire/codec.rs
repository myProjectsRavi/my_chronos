use serde::{Deserialize, Serialize};
use std::collections::HashMap;

const MAGIC: [u8; 2] = [0xCB, 0x03];

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CWPMessage {
    pub id: Vec<u8>,
    pub msg_type: u8,
    pub timestamp: u64,
    pub sender_did: String,
    pub payload: HashMap<String, String>,
    pub signature: Vec<u8>,
}

impl CWPMessage {
    pub fn encode(&self) -> Vec<u8> {
        let payload = rmp_serde::to_vec(self).unwrap_or_default();
        let mut frame = Vec::with_capacity(6 + payload.len());
        frame.extend_from_slice(&MAGIC);
        frame.extend_from_slice(&(payload.len() as u32).to_be_bytes());
        frame.extend_from_slice(&payload);
        frame
    }

    pub fn decode(data: &[u8]) -> Result<Self, Box<dyn std::error::Error>> {
        Ok(rmp_serde::from_slice(data)?)
    }
}
