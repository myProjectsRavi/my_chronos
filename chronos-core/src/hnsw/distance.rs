pub fn cosine_distance(a: &[f32], b: &[f32]) -> f32 {
    #[cfg(target_arch = "x86_64")]
    {
        if a.len() == b.len() && std::arch::is_x86_feature_detected!("avx2") {
            // SAFETY: AVX2 is checked at runtime and vectors have equal length.
            return unsafe { super::simd::cosine_distance_avx2(a, b) };
        }
    }
    super::simd::cosine_distance_scalar(a, b)
}

pub fn euclidean_distance(a: &[f32], b: &[f32]) -> f32 {
    a.iter()
        .zip(b.iter())
        .map(|(x, y)| (x - y).powi(2))
        .sum::<f32>()
        .sqrt()
}
