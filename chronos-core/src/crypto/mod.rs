use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use rand::{rngs::SysRng, TryRng};
use sha2::{Digest, Sha256};

pub struct CryptoEngine {
    signing_key: SigningKey,
}

impl CryptoEngine {
    pub fn new() -> Self {
        let mut secret_key = [0u8; 32];
        SysRng
            .try_fill_bytes(&mut secret_key)
            .expect("failed to obtain cryptographically secure operating-system randomness");
        Self {
            signing_key: SigningKey::from_bytes(&secret_key),
        }
    }

    pub fn from_bytes(bytes: &[u8; 32]) -> Self {
        Self {
            signing_key: SigningKey::from_bytes(bytes),
        }
    }

    pub fn sign(&self, data: &[u8]) -> Vec<u8> {
        self.signing_key.sign(data).to_bytes().to_vec()
    }

    pub fn verify(public_key: &[u8], data: &[u8], signature: &[u8]) -> bool {
        if public_key.len() != 32 || signature.len() != 64 {
            return false;
        }
        let mut pk_bytes = [0u8; 32];
        pk_bytes.copy_from_slice(public_key);
        let pk = match VerifyingKey::from_bytes(&pk_bytes) {
            Ok(value) => value,
            Err(_) => return false,
        };
        let mut sig_bytes = [0u8; 64];
        sig_bytes.copy_from_slice(signature);
        let sig = Signature::from_bytes(&sig_bytes);
        pk.verify(data, &sig).is_ok()
    }

    pub fn public_key(&self) -> Vec<u8> {
        self.signing_key.verifying_key().to_bytes().to_vec()
    }

    pub fn content_hash(data: &[u8]) -> Vec<u8> {
        let mut hasher = Sha256::new();
        hasher.update(data);
        hasher.finalize().to_vec()
    }

    pub fn generate_did(public_key: &[u8]) -> String {
        assert_eq!(
            public_key.len(),
            32,
            "Ed25519 public key must be exactly 32 bytes"
        );
        const HEX: &[u8; 16] = b"0123456789abcdef";
        let mut encoded = String::with_capacity(40);
        for &byte in &public_key[..20] {
            encoded.push(char::from(HEX[usize::from(byte >> 4)]));
            encoded.push(char::from(HEX[usize::from(byte & 0x0f)]));
        }
        format!("did:chronos:ed25519:{encoded}")
    }
}

impl Default for CryptoEngine {
    fn default() -> Self {
        Self::new()
    }
}
