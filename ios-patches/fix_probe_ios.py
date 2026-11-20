from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'up')

def replace(name, old, new):
    path = root / name
    source = path.read_text()
    assert source.count(old) == 1, (name, old)
    path.write_text(source.replace(old, new, 1))

fork = Path(sys.argv[2] if len(sys.argv) > 2 else '.')
models = (fork / 'lib/models/core.dart').read_text()
start = models.index('@freezed\nabstract class ProbeParams ')
end = models.index('@freezed\nabstract class OutboundIpParams ', start)
replace('lib/models/core.dart', '@freezed\nabstract class OutboundIpParams ', models[start:end] + '@freezed\nabstract class OutboundIpParams ')
replace('lib/core/method.dart', "  probeOutboundIp('probe.outboundIp'),", "  probeHttp('probe.http'),\n  probeOutboundIp('probe.outboundIp'),")
replace('lib/core/interface.dart', '  Future<OutboundIpResult> outboundIp(OutboundIpParams params) {', '''  Future<ProbeResult> probe(ProbeParams params) {
    return _query(
      CoreMethod.probeHttp,
      _model(ProbeResult.fromJson),
      arguments: params.toJson(),
      timeout: coreGuardFor(params.timeout),
    );
  }

  Future<OutboundIpResult> outboundIp(OutboundIpParams params) {''')
replace('core/protocol.go', '\tprobeOutboundIPMethod CoreMethod = "probe.outboundIp"', '\tprobeHTTPMethod       CoreMethod = "probe.http"\n\tprobeOutboundIPMethod CoreMethod = "probe.outboundIp"')
replace('core/method.go', '\tprobeOutboundIPMethod: withArguments(handleOutboundIp),', '\tprobeHTTPMethod:       withArguments(handleHTTPProbe),\n\tprobeOutboundIPMethod: withArguments(handleOutboundIp),')
probe = root / 'core/probe.go'
s = probe.read_text()
old_type = '''\tError        string
\tMessage      string
\tCoreEpoch    uint64
'''
new_type = '''\tError        string
\tMessage      string
\tBytes        int64 `json:"bytes"`
\tDuration     int64 `json:"duration"`
\tCoreEpoch    uint64
'''
assert s.count(old_type) == 1
s = s.replace(old_type, new_type, 1)
old_read = '''\tif req.maxBody > 0 {
\t\tresult.Body = readProbeBody(response.Body, req.maxBody, req.until)
\t}
'''
new_read = '''\tif req.maxBody > 0 {
\t\treadStart := time.Now()
\t\tresult.Body, result.Bytes = readProbeBodyWithCount(response.Body, req.maxBody, req.until)
\t\tresult.Duration = time.Since(readStart).Milliseconds()
\t}
'''
assert s.count(old_read) == 1
s = s.replace(old_read, new_read, 1)
old_func = '''func readProbeBody(body io.Reader, maxBody int64, until func(string) bool) string {
\tlimited := io.LimitReader(body, maxBody)
\tif until == nil {
\t\tpayload, _ := io.ReadAll(limited)
\t\treturn string(payload)
\t}
\tvar buffer bytes.Buffer
\tchunk := make([]byte, probeScanChunk)
\tfor {
\t\tn, err := limited.Read(chunk)
\t\tif n > 0 {
\t\t\tstart := max(0, buffer.Len()-probeScanOverlap)
\t\t\tbuffer.Write(chunk[:n])
\t\t\tif until(string(buffer.Bytes()[start:])) {
\t\t\t\tbreak
\t\t\t}
\t\t}
\t\tif err != nil {
\t\t\tbreak
\t\t}
\t}
\treturn buffer.String()
}
'''
new_func = '''func readProbeBody(body io.Reader, maxBody int64, until func(string) bool) string {
\tcontent, _ := readProbeBodyWithCount(body, maxBody, until)
\treturn content
}

func readProbeBodyWithCount(body io.Reader, maxBody int64, until func(string) bool) (string, int64) {
\tlimited := io.LimitReader(body, maxBody)
\tif until == nil {
\t\tpayload, _ := io.ReadAll(limited)
\t\treturn string(payload), int64(len(payload))
\t}
\tvar buffer bytes.Buffer
\ttotal := int64(0)
\tchunk := make([]byte, probeScanChunk)
\tfor {
\t\tn, err := limited.Read(chunk)
\t\tif n > 0 {
\t\t\ttotal += int64(n)
\t\t\tstart := max(0, buffer.Len()-probeScanOverlap)
\t\t\tbuffer.Write(chunk[:n])
\t\t\tif until(string(buffer.Bytes()[start:])) {
\t\t\t\tbreak
\t\t\t}
\t\t}
\t\tif err != nil {
\t\t\tbreak
\t\t}
\t}
\treturn buffer.String(), total
}
'''
assert s.count(old_func) == 1
s = s.replace(old_func, new_func, 1)
probe.write_text(s)
(root / 'core/probe_http.go').write_text('''package core

import "context"

type HTTPProbeParams struct {
    URL string `json:"url"`
    ProxyName string `json:"proxy-name"`
    Headers map[string]string `json:"headers"`
    Timeout int64 `json:"timeout"`
    MaxBody int64 `json:"max-body"`
}

func handleHTTPProbe(params *HTTPProbeParams) map[string]any {
    result := runProbe(context.Background(), probeRequest{url: params.URL, proxyName: params.ProxyName, headers: params.Headers, timeout: timeoutFromMillis(params.Timeout, defaultProbeTimeout), maxBody: params.MaxBody})
    if result == nil { return map[string]any{"error": probeErrorTimeout} }
    return map[string]any{"status-code": result.StatusCode, "delay": result.Delay, "body": result.Body, "url": result.Url, "chains": result.Chains, "error": result.Error, "message": result.Message, "bytes": result.Bytes, "duration": result.Duration}
}
''')
print('Patched IP-quality models and probe.http on Dart and Go sides')