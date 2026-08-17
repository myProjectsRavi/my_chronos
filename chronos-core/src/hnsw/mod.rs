pub mod distance;
pub mod layer;
pub mod simd;

use serde::{Deserialize, Serialize};
use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashMap, HashSet};

#[derive(Clone, Serialize, Deserialize)]
pub struct HNSWIndex {
    dim: usize,
    m: usize,
    ef_construction: usize,
    max_level: usize,
    entry_point: Option<u64>,
    nodes: HashMap<u64, HNSWNode>,
}

#[derive(Clone, Serialize, Deserialize)]
struct HNSWNode {
    id: u64,
    vector: Vec<f32>,
    level: usize,
    neighbors: Vec<Vec<u64>>,
}

#[derive(Clone, Copy, Debug)]
struct Candidate {
    id: u64,
    dist: f32,
}

impl PartialEq for Candidate {
    fn eq(&self, other: &Self) -> bool {
        self.cmp(other) == Ordering::Equal
    }
}

impl Eq for Candidate {}

impl PartialOrd for Candidate {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for Candidate {
    fn cmp(&self, other: &Self) -> Ordering {
        // Reverse distance ordering so BinaryHeap pops the nearest candidate first.
        // Break equal-distance ties by ID for deterministic traversal.
        other
            .dist
            .total_cmp(&self.dist)
            .then_with(|| other.id.cmp(&self.id))
    }
}

impl HNSWIndex {
    pub fn new(dim: usize, m: usize, ef_construction: usize) -> Self {
        Self {
            dim,
            m: m.max(2),
            ef_construction: ef_construction.max(8),
            max_level: 0,
            entry_point: None,
            nodes: HashMap::new(),
        }
    }

    pub fn insert(&mut self, id: u64, vector: &[f32]) {
        assert_eq!(vector.len(), self.dim, "vector dimension mismatch");

        let level = self.random_level();
        let mut node = HNSWNode {
            id,
            vector: vector.to_vec(),
            level,
            neighbors: (0..=level).map(|_| Vec::new()).collect(),
        };

        if let Some(entry) = self.entry_point {
            let mut ep = entry;

            if level < self.max_level {
                for l in ((level + 1)..=self.max_level).rev() {
                    ep = self.greedy_closest(ep, vector, l);
                }
            }

            let connect_level = level.min(self.max_level);
            for l in (0..=connect_level).rev() {
                let neighbors = self.search_layer(ep, vector, self.ef_construction, l);
                let selected: Vec<u64> = neighbors.iter().take(self.m).map(|c| c.id).collect();

                if l < node.neighbors.len() {
                    node.neighbors[l] = selected.clone();
                }

                for nid in selected {
                    if let Some(existing) = self.nodes.get_mut(&nid) {
                        if l < existing.neighbors.len() {
                            existing.neighbors[l].push(id);
                            if existing.neighbors[l].len() > self.m * 2 {
                                existing.neighbors[l].truncate(self.m * 2);
                            }
                        }
                    }
                }

                if let Some(next_ep) = node.neighbors[l].first().copied() {
                    ep = next_ep;
                }
            }
        }

        self.nodes.insert(id, node);
        if self.entry_point.is_none() || level > self.max_level {
            self.entry_point = Some(id);
            self.max_level = level;
        }
    }

    pub fn search(&self, query: &[f32], k: usize, ef: usize) -> Vec<(u64, f32)> {
        if query.len() != self.dim {
            return Vec::new();
        }
        let Some(mut ep) = self.entry_point else {
            return Vec::new();
        };
        for l in (1..=self.max_level).rev() {
            ep = self.greedy_closest(ep, query, l);
        }

        let candidates = self.search_layer(ep, query, ef.max(k).max(1), 0);
        candidates.into_iter().take(k).map(|c| (c.id, c.dist)).collect()
    }

    pub fn len(&self) -> usize {
        self.nodes.len()
    }

    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }

    fn search_layer(&self, entry: u64, query: &[f32], ef: usize, layer: usize) -> Vec<Candidate> {
        let mut visited: HashSet<u64> = HashSet::new();
        let mut queue: BinaryHeap<Candidate> = BinaryHeap::new();

        let dist = self.distance(entry, query);
        queue.push(Candidate { id: entry, dist });
        visited.insert(entry);

        let mut results: Vec<Candidate> = vec![Candidate { id: entry, dist }];

        while let Some(current) = queue.pop() {
            if results.len() >= ef {
                let worst = results
                    .iter()
                    .map(|candidate| candidate.dist)
                    .fold(0.0f32, f32::max);
                if current.dist > worst {
                    break;
                }
            }

            if let Some(node) = self.nodes.get(&current.id) {
                if layer < node.neighbors.len() {
                    for &nid in &node.neighbors[layer] {
                        if visited.insert(nid) {
                            let d = self.distance(nid, query);
                            queue.push(Candidate { id: nid, dist: d });
                            results.push(Candidate { id: nid, dist: d });
                        }
                    }
                }
            }
        }

        results.sort_by(|a, b| a.dist.total_cmp(&b.dist).then_with(|| a.id.cmp(&b.id)));
        results.truncate(ef);
        results
    }

    fn greedy_closest(&self, start: u64, query: &[f32], layer: usize) -> u64 {
        let mut best_id = start;
        let mut best_dist = self.distance(start, query);
        let mut improved = true;

        while improved {
            improved = false;
            if let Some(node) = self.nodes.get(&best_id) {
                if layer < node.neighbors.len() {
                    for &nid in &node.neighbors[layer] {
                        let d = self.distance(nid, query);
                        if d < best_dist {
                            best_dist = d;
                            best_id = nid;
                            improved = true;
                        }
                    }
                }
            }
        }

        best_id
    }

    fn distance(&self, node_id: u64, query: &[f32]) -> f32 {
        self.nodes
            .get(&node_id)
            .map(|node| distance::cosine_distance(&node.vector, query))
            .unwrap_or(f32::MAX)
    }

    fn random_level(&self) -> usize {
        let p = 1.0f64 / self.m as f64;
        let mut level = 0usize;
        while rand::random::<f64>() < p && level < 16 {
            level += 1;
        }
        level
    }
}

#[cfg(test)]
mod tests {
    use super::HNSWIndex;

    #[test]
    fn basic_insert_search() {
        let mut index = HNSWIndex::new(3, 8, 64);
        index.insert(1, &[1.0, 0.0, 0.0]);
        index.insert(2, &[0.0, 1.0, 0.0]);
        index.insert(3, &[0.0, 0.0, 1.0]);

        let hits = index.search(&[1.0, 0.0, 0.0], 2, 10);
        assert!(!hits.is_empty());
        assert_eq!(hits[0].0, 1);
    }
}
