#[cfg(test)]
mod tests {
    use chronos_core::crypto::CryptoEngine;

    #[test]
    fn test_sign_and_verify() {
        let engine = CryptoEngine::new();
        let data = b"hello world";
        let sig = engine.sign(data);
        let pk = engine.public_key();
        assert!(CryptoEngine::verify(&pk, data, &sig));
    }

    #[test]
    fn test_verify_wrong_data_fails() {
        let engine = CryptoEngine::new();
        let sig = engine.sign(b"hello");
        let pk = engine.public_key();
        assert!(!CryptoEngine::verify(&pk, b"world", &sig));
    }

    #[test]
    fn test_content_hash_deterministic() {
        let h1 = CryptoEngine::content_hash(b"test data");
        let h2 = CryptoEngine::content_hash(b"test data");
        assert_eq!(h1, h2);
    }

    #[test]
    fn test_did_generation_matches_python_identity_format() {
        let public_key: Vec<u8> = (0u8..32).collect();
        let did = CryptoEngine::generate_did(&public_key);
        assert_eq!(
            did,
            "did:chronos:ed25519:000102030405060708090a0b0c0d0e0f10111213"
        );
    }

    #[test]
    #[should_panic(expected = "Ed25519 public key must be exactly 32 bytes")]
    fn test_did_generation_rejects_invalid_public_key_length() {
        CryptoEngine::generate_did(&[0u8; 31]);
    }
}
