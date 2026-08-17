package chronos

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

const maxErrorBodyBytes int64 = 4096

type Client struct {
	baseURL    string
	httpClient *http.Client
	apiKey     string
}

type Memory struct {
	ID          string         `json:"id"`
	Content     string         `json:"content"`
	Summary     string         `json:"summary"`
	Importance  float64        `json:"importance"`
	Source      string         `json:"source"`
	DecayWeight float64        `json:"decay_weight"`
	MemoryTier  string         `json:"memory_tier"`
	Metadata    map[string]any `json:"metadata"`
	CreatedAt   int64          `json:"created_at"`
	AccessCount int            `json:"access_count"`
}

type RecallResult struct {
	Memory Memory  `json:"memory"`
	Score  float64 `json:"score"`
}

type TQLResult struct {
	Results []map[string]any `json:"results"`
	Count   int              `json:"count"`
}

func NewClient(baseURL string) *Client {
	return NewClientWithAPIKey(baseURL, "")
}

func NewClientWithAPIKey(baseURL string, apiKey string) *Client {
	return &Client{
		baseURL:    baseURL,
		httpClient: &http.Client{Timeout: 30 * time.Second},
		apiKey:     apiKey,
	}
}

func (c *Client) Remember(ctx context.Context, content string, importance float64) (*Memory, error) {
	body := map[string]any{"content": content, "importance": importance}
	var mem Memory
	err := c.post(ctx, "/api/v4/memories", body, &mem)
	return &mem, err
}

func (c *Client) Recall(ctx context.Context, query string, topK int) ([]RecallResult, error) {
	body := map[string]any{"query": query, "top_k": topK}
	var results []RecallResult
	err := c.post(ctx, "/api/v4/recall", body, &results)
	return results, err
}

func (c *Client) TQL(ctx context.Context, query string) (*TQLResult, error) {
	body := map[string]any{"query": query}
	var result TQLResult
	err := c.post(ctx, "/api/v4/tql", body, &result)
	return &result, err
}

func (c *Client) Checkpoint(ctx context.Context, message string) error {
	body := map[string]any{"message": message}
	return c.post(ctx, "/api/v4/checkpoints", body, nil)
}

func (c *Client) Forget(ctx context.Context, memoryID string) error {
	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodDelete,
		fmt.Sprintf("%s/api/v4/memories/%s", c.baseURL, url.PathEscape(memoryID)),
		nil,
	)
	if err != nil {
		return err
	}
	c.addHeaders(req, false)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return fmt.Errorf("HTTP %d", resp.StatusCode)
	}
	return nil
}

func (c *Client) post(ctx context.Context, path string, body any, result any) error {
	jsonBody, err := json.Marshal(body)
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		c.baseURL+path,
		bytes.NewReader(jsonBody),
	)
	if err != nil {
		return err
	}
	c.addHeaders(req, true)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		b, _ := io.ReadAll(io.LimitReader(resp.Body, maxErrorBodyBytes))
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, string(b))
	}
	if result != nil {
		return json.NewDecoder(resp.Body).Decode(result)
	}
	return nil
}

func (c *Client) addHeaders(req *http.Request, jsonBody bool) {
	if jsonBody {
		req.Header.Set("Content-Type", "application/json")
	}
	if c.apiKey != "" {
		req.Header.Set("X-API-Key", c.apiKey)
	}
}
