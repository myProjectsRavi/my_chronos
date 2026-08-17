#[cfg(test)]
mod tests {
    use chronos_core::crdt::lww_register::LWWRegister;
    use chronos_core::crdt::or_set::ORSet;

    #[test]
    fn test_lww_higher_timestamp_wins() {
        let r1 = LWWRegister::new("old".to_string(), 100, "alice".to_string());
        let r2 = LWWRegister::new("new".to_string(), 200, "bob".to_string());
        let merged = r1.merge(&r2);
        assert_eq!(merged.value, "new");
    }

    #[test]
    fn test_lww_tie_breaks_by_did() {
        let r1 = LWWRegister::new("a".to_string(), 100, "alice".to_string());
        let r2 = LWWRegister::new("b".to_string(), 100, "bob".to_string());
        let merged = r1.merge(&r2);
        assert_eq!(merged.value, "b");
    }

    #[test]
    fn test_or_set_add_contains() {
        let mut s = ORSet::new();
        s.add("hello", "alice");
        assert!(s.contains("hello"));
        assert!(!s.contains("world"));
    }

    #[test]
    fn test_or_set_remove() {
        let mut s = ORSet::new();
        s.add("hello", "alice");
        s.remove("hello");
        assert!(!s.contains("hello"));
    }

    #[test]
    fn test_or_set_concurrent_add_survives_remove() {
        let mut s1 = ORSet::new();
        let mut s2 = ORSet::new();
        s1.add("x", "alice");
        s2.add("x", "bob");
        s1.remove("x");
        s1.merge(&s2);
        assert!(s1.contains("x"));
    }
}
