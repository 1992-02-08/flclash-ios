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
(root / 'core/probe_http.go').write_text('''package core

import "context"

// Keep IP-quality requests on the same tunnel route as outbound-IP probes.
type HTTPProbeParams struct {
    URL       string            `json:"url"`
    ProxyName string            `json:"proxy-name"`
    Headers   map[string]string `json:"headers"`
    Timeout   int64             `json:"timeout"`
    MaxBody   int64             `json:"max-body"`
}

func handleHTTPProbe(params *HTTPProbeParams) map[string]any {
    result := runProbe(context.Background(), probeRequest{
        url: params.URL,
        proxyName: params.ProxyName,
        headers: params.Headers,
        timeout: timeoutFromMillis(params.Timeout, defaultProbeTimeout),
        maxBody: params.MaxBody,
    })
    if result == nil {
        return map[string]any{"error": probeErrorTimeout}
    }
    return map[string]any{
        "status-code": result.StatusCode,
        "delay": result.Delay,
        "body": result.Body,
        "url": result.Url,
        "chains": result.Chains,
        "error": result.Error,
        "message": result.Message,
    }
}
''')
print('Patched IP-quality models and probe.http on Dart and Go sides')
