use pyo3::prelude::*;

#[pyclass]
struct RustCryptoEngine {
    inner: crate::crypto::CryptoEngine,
}

#[pymethods]
impl RustCryptoEngine {
    #[new]
    fn new() -> Self {
        Self {
            inner: crate::crypto::CryptoEngine::new(),
        }
    }

    fn sign(&self, data: &[u8]) -> Vec<u8> {
        self.inner.sign(data)
    }

    fn verify(&self, public_key: &[u8], data: &[u8], signature: &[u8]) -> bool {
        crate::crypto::CryptoEngine::verify(public_key, data, signature)
    }

    fn public_key(&self) -> Vec<u8> {
        self.inner.public_key()
    }

    fn content_hash(&self, data: &[u8]) -> Vec<u8> {
        crate::crypto::CryptoEngine::content_hash(data)
    }

    fn generate_did(&self) -> String {
        crate::crypto::CryptoEngine::generate_did(&self.inner.public_key())
    }
}

#[pymodule]
fn chronos_core(_py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_class::<RustCryptoEngine>()?;
    Ok(())
}
