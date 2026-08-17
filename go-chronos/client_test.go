package chronos

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func newTestClient(t *testing.T, handler http.HandlerFunc) *Client {
	t.Helper()
	server := httptest.NewServer(handler)
	t.Cleanup(server.Close)

	client := NewClient(server.URL)
	client.httpClient = server.Client()
	return client
}

func TestRemember(t *testing.T) {
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Fatalf("expected method POST, got %s", r.Method)
		}
		if r.URL.Path != "/api/v4/memories" {
			t.Fatalf("expected path /api/v4/memories, got %s", r.URL.Path)
		}

		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("decode request body: %v", err)
		}
		if got := body["content"]; got != "hello world" {
			t.Fatalf("unexpected content: %v", got)
		}
		if got := body["importance"]; got != 0.9 {
			t.Fatalf("unexpected importance: %v", got)
		}

		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"id":"mem-1","content":"hello world","importance":0.9}`))
	})

	memory, err := client.Remember(context.Background(), "hello world", 0.9)
	if err != nil {
		t.Fatalf("remember failed: %v", err)
	}
	if memory.ID != "mem-1" {
		t.Fatalf("expected ID mem-1, got %s", memory.ID)
	}
}

func TestRecall(t *testing.T) {
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Fatalf("expected method POST, got %s", r.Method)
		}
		if r.URL.Path != "/api/v4/recall" {
			t.Fatalf("expected path /api/v4/recall, got %s", r.URL.Path)
		}

		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("decode request body: %v", err)
		}
		if got := body["query"]; got != "meeting notes" {
			t.Fatalf("unexpected query: %v", got)
		}
		if got := body["top_k"]; got != float64(3) {
			t.Fatalf("unexpected top_k: %v", got)
		}

		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`[{"memory":{"id":"mem-2","content":"meeting notes"},"score":0.88}]`))
	})

	results, err := client.Recall(context.Background(), "meeting notes", 3)
	if err != nil {
		t.Fatalf("recall failed: %v", err)
	}
	if len(results) != 1 {
		t.Fatalf("expected 1 result, got %d", len(results))
	}
	if results[0].Memory.ID != "mem-2" {
		t.Fatalf("unexpected memory ID: %s", results[0].Memory.ID)
	}
}

func TestTQL(t *testing.T) {
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Fatalf("expected method POST, got %s", r.Method)
		}
		if r.URL.Path != "/api/v4/tql" {
			t.Fatalf("expected path /api/v4/tql, got %s", r.URL.Path)
		}

		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"results":[{"content":"note"}],"count":1}`))
	})

	result, err := client.TQL(context.Background(), "SELECT * FROM memories")
	if err != nil {
		t.Fatalf("tql failed: %v", err)
	}
	if result.Count != 1 {
		t.Fatalf("expected count 1, got %d", result.Count)
	}
}

func TestCheckpoint(t *testing.T) {
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Fatalf("expected method POST, got %s", r.Method)
		}
		if r.URL.Path != "/api/v4/checkpoints" {
			t.Fatalf("expected path /api/v4/checkpoints, got %s", r.URL.Path)
		}
		w.WriteHeader(http.StatusNoContent)
	})

	if err := client.Checkpoint(context.Background(), "snapshot 1"); err != nil {
		t.Fatalf("checkpoint failed: %v", err)
	}
}

func TestForget(t *testing.T) {
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodDelete {
			t.Fatalf("expected method DELETE, got %s", r.Method)
		}
		if r.URL.Path != "/api/v4/memories/mem-3" {
			t.Fatalf("expected path /api/v4/memories/mem-3, got %s", r.URL.Path)
		}
		w.WriteHeader(http.StatusNoContent)
	})

	if err := client.Forget(context.Background(), "mem-3"); err != nil {
		t.Fatalf("forget failed: %v", err)
	}
}

func TestForgetHTTPError(t *testing.T) {
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
	})

	err := client.Forget(context.Background(), "mem-4")
	if err == nil {
		t.Fatal("expected error for bad status code")
	}
	if !strings.Contains(err.Error(), "HTTP 400") {
		t.Fatalf("expected HTTP 400 in error, got: %v", err)
	}
}

func TestPostIncludesErrorBody(t *testing.T) {
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "invalid request", http.StatusBadRequest)
	})

	_, err := client.Remember(context.Background(), "bad", 0.1)
	if err == nil {
		t.Fatal("expected error from remember")
	}
	if !strings.Contains(err.Error(), "HTTP 400") {
		t.Fatalf("expected status code in error, got: %v", err)
	}
	if !strings.Contains(err.Error(), "invalid request") {
		t.Fatalf("expected response body in error, got: %v", err)
	}
}

func TestAPIKeyHeaderOnPost(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("X-API-Key"); got != "test-secret" {
			t.Fatalf("expected X-API-Key header, got %q", got)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"id":"mem-auth"}`))
	}))
	t.Cleanup(server.Close)
	client := NewClientWithAPIKey(server.URL, "test-secret")
	client.httpClient = server.Client()
	if _, err := client.Remember(context.Background(), "secure", 0.5); err != nil {
		t.Fatalf("remember failed: %v", err)
	}
}

func TestNewClientWithAPIKey(t *testing.T) {
	client := NewClientWithAPIKey("http://example.test", "secret")
	if client.apiKey != "secret" {
		t.Fatalf("expected configured api key")
	}
}

func TestForgetEscapesMemoryIDAndSendsAPIKey(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.RequestURI != "/api/v4/memories/alpha%2Fbeta%3Fx=1" {
			t.Fatalf("unexpected request URI: %s", r.RequestURI)
		}
		if got := r.Header.Get("X-API-Key"); got != "test-secret" {
			t.Fatalf("expected X-API-Key header, got %q", got)
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	t.Cleanup(server.Close)
	client := NewClientWithAPIKey(server.URL, "test-secret")
	client.httpClient = server.Client()
	if err := client.Forget(context.Background(), "alpha/beta?x=1"); err != nil {
		t.Fatalf("forget failed: %v", err)
	}
}

func TestPostErrorBodyIsBounded(t *testing.T) {
	payload := strings.Repeat("X", 20000)
	client := newTestClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte(payload))
	})
	_, err := client.Remember(context.Background(), "bad", 0.1)
	if err == nil {
		t.Fatal("expected error")
	}
	if got := len(err.Error()); got > 4200 {
		t.Fatalf("error body was not bounded: %d bytes", got)
	}
}

func TestInvalidBaseURLReturnsError(t *testing.T) {
	client := NewClient("://invalid")
	if _, err := client.Remember(context.Background(), "x", 0.5); err == nil {
		t.Fatal("expected invalid URL error")
	}
}
