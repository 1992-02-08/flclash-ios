package core

import (
    "encoding/json"
    "net/http"
    "testing"
)

func TestIOSHTTPProbeWireResponse(t *testing.T) {
    var userAgent string
    server := probeServer(t, func(w http.ResponseWriter, r *http.Request) {
        userAgent = r.UserAgent()
        w.WriteHeader(http.StatusForbidden)
        _, _ = w.Write([]byte("0123456789"))
    })
    withProbeProxies(t, "ios-probe")
    arguments, err := json.Marshal(HTTPProbeParams{
        URL: server.URL,
        ProxyName: "ios-probe",
        Headers: map[string]string{"User-Agent": "ios-wire-test"},
        Timeout: 2000,
        MaxBody: 5,
    })
    if err != nil { t.Fatal(err) }
    wire := handleMethodCall(&MethodCall{ID: "probe-test", Method: probeHTTPMethod, Arguments: arguments})
    var response struct {
        ID string `json:"id"`
        Error *MethodError `json:"error"`
        Result struct {
            StatusCode int `json:"status-code"`
            Body string `json:"body"`
            Error string `json:"error"`
        } `json:"result"`
    }
    if err := json.Unmarshal(wire, &response); err != nil { t.Fatal(err) }
    if response.ID != "probe-test" || response.Error != nil || response.Result.Error != "" {
        t.Fatalf("unexpected wire response: %s", wire)
    }
    if response.Result.StatusCode != 403 || response.Result.Body != "01234" {
        t.Fatalf("status/body/cap mismatch: %s", wire)
    }
    if userAgent != "ios-wire-test" { t.Fatalf("user-agent = %q", userAgent) }
}

func TestIOSHTTPProbeRejectsInvalidArguments(t *testing.T) {
    wire := handleMethodCall(&MethodCall{Method: probeHTTPMethod, Arguments: json.RawMessage(`{"timeout":"bad"}`)})
    var response MethodResponse
    if err := json.Unmarshal(wire, &response); err != nil { t.Fatal(err) }
    if response.Error == nil || response.Error.Code != "invalid_arguments" {
        t.Fatalf("expected invalid_arguments: %s", wire)
    }
}
