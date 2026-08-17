//! SIMD-accelerated distance computations for HNSW+.

#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::*;

/// Cosine distance with AVX2 SIMD acceleration.
///
/// # Safety
///
/// The caller must ensure that the current CPU supports AVX2 before calling this function.
#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
pub unsafe fn cosine_distance_avx2(a: &[f32], b: &[f32]) -> f32 {
    assert_eq!(a.len(), b.len());
    let n = a.len();
    let chunks = n / 8;
    let remainder = n % 8;

    let mut dot = _mm256_setzero_ps();
    let mut na = _mm256_setzero_ps();
    let mut nb = _mm256_setzero_ps();

    for i in 0..chunks {
        // SAFETY: i is bounded by chunks; chunks*8 <= n; both vectors have len n.
        let va = unsafe { _mm256_loadu_ps(a.as_ptr().add(i * 8)) };
        // SAFETY: same bound argument as above.
        let vb = unsafe { _mm256_loadu_ps(b.as_ptr().add(i * 8)) };
        dot = _mm256_add_ps(dot, _mm256_mul_ps(va, vb));
        na = _mm256_add_ps(na, _mm256_mul_ps(va, va));
        nb = _mm256_add_ps(nb, _mm256_mul_ps(vb, vb));
    }

    // SAFETY: `hsum_avx` requires AVX vectors; `dot/na/nb` are AVX registers.
    let mut dot_sum = unsafe { hsum_avx(dot) };
    // SAFETY: same as above.
    let mut na_sum = unsafe { hsum_avx(na) };
    // SAFETY: same as above.
    let mut nb_sum = unsafe { hsum_avx(nb) };

    let offset = chunks * 8;
    for i in 0..remainder {
        let ai = a[offset + i];
        let bi = b[offset + i];
        dot_sum += ai * bi;
        na_sum += ai * ai;
        nb_sum += bi * bi;
    }

    let denom = na_sum.sqrt() * nb_sum.sqrt();
    if denom < 1e-10 {
        1.0
    } else {
        1.0 - dot_sum / denom
    }
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "avx2")]
unsafe fn hsum_avx(v: __m256) -> f32 {
    let hi = _mm256_extractf128_ps(v, 1);
    let lo = _mm256_castps256_ps128(v);
    let sum = _mm_add_ps(lo, hi);
    let shuf = _mm_movehdup_ps(sum);
    let sums = _mm_add_ps(sum, shuf);
    let shuf2 = _mm_movehl_ps(sums, sums);
    let result = _mm_add_ss(sums, shuf2);
    _mm_cvtss_f32(result)
}

/// Fallback scalar implementation.
pub fn cosine_distance_scalar(a: &[f32], b: &[f32]) -> f32 {
    let mut dot = 0.0f32;
    let mut na = 0.0f32;
    let mut nb = 0.0f32;
    for i in 0..a.len().min(b.len()) {
        dot += a[i] * b[i];
        na += a[i] * a[i];
        nb += b[i] * b[i];
    }
    let denom = na.sqrt() * nb.sqrt();
    if denom < 1e-10 {
        1.0
    } else {
        1.0 - dot / denom
    }
}

/// Product quantization for memory-efficient storage.
pub struct ProductQuantizer {
    pub num_subspaces: usize,
    pub codebook_size: usize,
    pub codebooks: Vec<Vec<Vec<f32>>>, // [subspace][centroid][dims]
}

impl ProductQuantizer {
    pub fn new(dim: usize, num_subspaces: usize, codebook_size: usize) -> Self {
        let subspaces = num_subspaces.max(1);
        let sub_dim = dim.max(1) / subspaces;
        let codebooks = (0..subspaces)
            .map(|_| {
                (0..codebook_size.max(1))
                    .map(|_| vec![0.0f32; sub_dim])
                    .collect()
            })
            .collect();
        Self {
            num_subspaces: subspaces,
            codebook_size: codebook_size.max(1),
            codebooks,
        }
    }

    pub fn encode(&self, vector: &[f32]) -> Vec<u8> {
        if self.num_subspaces == 0 || vector.is_empty() {
            return Vec::new();
        }
        let sub_dim = vector.len() / self.num_subspaces.max(1);
        (0..self.num_subspaces)
            .map(|s| {
                let start = s * sub_dim;
                let end = ((s + 1) * sub_dim).min(vector.len());
                let sub = &vector[start..end];
                let mut best_idx = 0usize;
                let mut best_dist = f32::MAX;
                for (i, centroid) in self.codebooks[s].iter().enumerate() {
                    let d = cosine_distance_scalar(sub, centroid);
                    if d < best_dist {
                        best_dist = d;
                        best_idx = i;
                    }
                }
                u8::try_from(best_idx).unwrap_or(u8::MAX)
            })
            .collect()
    }

    pub fn decode(&self, codes: &[u8]) -> Vec<f32> {
        let mut result = Vec::new();
        for (s, &code) in codes.iter().enumerate() {
            if s >= self.codebooks.len() {
                break;
            }
            let idx = usize::from(code).min(self.codebooks[s].len().saturating_sub(1));
            result.extend_from_slice(&self.codebooks[s][idx]);
        }
        result
    }
}
