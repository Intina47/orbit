package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

type ingestRequest struct {
	Content   string `json:"content"`
	EventType string `json:"event_type"`
	EntityID  string `json:"entity_id"`
}

type ingestResponse struct {
	MemoryID string `json:"memory_id"`
}

type memoryItem struct {
	Content string `json:"content"`
}

type retrieveResponse struct {
	Memories []memoryItem `json:"memories"`
}

func main() {
	baseURL := requiredEnv("ORBIT_API_BASE_URL")
	apiKey := requiredEnv("ORBIT_API_KEY")
	entityID := envOrDefault("ORBIT_ENTITY_ID", "alice")

	ingestPayload := ingestRequest{
		Content:   "I keep overcomplicating my first draft implementation.",
		EventType: "user_question",
		EntityID:  entityID,
	}

	var ingest ingestResponse
	if err := orbitRequest(baseURL, apiKey, http.MethodPost, "/v1/ingest", ingestPayload, &ingest); err != nil {
		exitWithError(err)
	}

	query := url.QueryEscape(fmt.Sprintf("What should I know about %s?", entityID))
	entity := url.QueryEscape(entityID)
	var retrieve retrieveResponse
	retrievePath := fmt.Sprintf("/v1/retrieve?query=%s&entity_id=%s&limit=5", query, entity)
	if err := orbitRequest(baseURL, apiKey, http.MethodGet, retrievePath, nil, &retrieve); err != nil {
		exitWithError(err)
	}

	fmt.Println("ingest.memory_id =", ingest.MemoryID)
	fmt.Println("retrieved =", len(retrieve.Memories), "memories")
	for _, m := range retrieve.Memories {
		fmt.Println("-", m.Content)
	}
}

func orbitRequest(baseURL, apiKey, method, path string, payload any, out any) error {
	fullURL := strings.TrimRight(baseURL, "/") + path
	var body io.Reader
	if payload != nil {
		encoded, err := json.Marshal(payload)
		if err != nil {
			return err
		}
		body = bytes.NewReader(encoded)
	}

	req, err := http.NewRequest(method, fullURL, body)
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Accept", "application/json")
	if payload != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return err
	}
	if resp.StatusCode >= 400 {
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(respBody)))
	}
	if len(respBody) == 0 || out == nil {
		return nil
	}
	return json.Unmarshal(respBody, out)
}

func requiredEnv(name string) string {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		exitWithError(fmt.Errorf("missing environment variable: %s", name))
	}
	return value
}

func envOrDefault(name, fallback string) string {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return fallback
	}
	return value
}

func exitWithError(err error) {
	fmt.Fprintln(os.Stderr, err.Error())
	os.Exit(1)
}
