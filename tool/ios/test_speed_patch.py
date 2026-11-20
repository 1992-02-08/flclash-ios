from pathlib import Path

root = Path(__file__).resolve().parents[2] / 'up'

checks = {
    'speed provider': [
        ('lib/providers/proxy_speed.dart', 'coreHandlerProvider).probe('),
        ('lib/providers/proxy_speed.dart', 'speed.cloudflare.com/__down?bytes=$speedTestMaxBytes'),
        ('lib/providers/proxy_speed.dart', 'speedTestMaxBytes = 8 * 1024 * 1024'),
        ('lib/providers/proxy_speed.dart', 'result.bytes'),
        ('lib/providers/proxy_speed.dart', 'result.duration'),
    ],
    'speed action': [
        ('lib/providers/actions/proxies.dart', 'speedTestPageGroup'),
        ('lib/providers/actions/proxies.dart', 'speedTestingGroupsProvider'),
        ('lib/providers/actions/proxies.dart', '_speedTestPool'),
        ('lib/providers/actions/proxies.dart', '下载测速开始'),
    ],
    'menu callback': [
        ('lib/views/proxies/proxies.dart', "label: '下载测速'"),
        ('lib/views/proxies/proxies.dart', 'onPressed: _startDownloadSpeedTest'),
        ('lib/views/proxies/proxies.dart', 'speedTestPageGroup(groupName)'),
        ('lib/views/proxies/proxies.dart', '下载测速开始'),
    ],
    'tab fallback': [
        ('lib/views/proxies/tab.dart', 'speedTestCurrentGroup'),
        ('lib/views/proxies/tab.dart', 'return state.groups.isEmpty ? null : state.groups.first;'),
    ],
}

missing = []
for group, items in checks.items():
    for rel, needle in items:
        path = root / rel
        if not path.exists() or needle not in path.read_text():
            missing.append(f'{group}: {rel}: {needle}')

proxies = (root / 'lib/views/proxies/proxies.dart').read_text()
if 'IconButtonData? _buildSpeedAction' in proxies:
    missing.append('menu callback: unexpected toolbar speed action')

if missing:
    raise SystemExit('Speed patch wiring failed:\n' + '\n'.join(missing))
print('Speed patch wiring: PASS')
