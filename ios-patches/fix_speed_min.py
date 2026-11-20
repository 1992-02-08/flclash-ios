from pathlib import Path
import sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'up')


def rep(path, old, new):
    file = root / path
    source = file.read_text()
    count = source.count(old)
    assert count == 1, (path, count, old)
    file.write_text(source.replace(old, new, 1))


(root / 'lib/providers/proxy_speed.dart').write_text(
    '''import 'package:fl_clash/common/common.dart';
import 'package:fl_clash/core/core.dart';
import 'package:fl_clash/models/models.dart';
import 'package:fl_clash/providers/app.dart';
import 'package:fl_clash/providers/core.dart';
import 'package:fl_clash/providers/state.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

// Cloud download simulation: every node downloads the same bounded payload
// through the selected proxy. Fallback sources handle regional blocking.
const int speedTestMaxBytes = 2 * 1024 * 1024;
const int speedTestTimeoutMs = 20000;
const String speedTestUrl =
    'https://speed.cloudflare.com/__down?bytes=$speedTestMaxBytes';

List<String> _cloudSpeedTestUrls() {
  final cacheBust = DateTime.now().microsecondsSinceEpoch;
  return [
    'https://speed.cloudflare.com/__down?bytes=$speedTestMaxBytes&cache=$cacheBust',
    speedTestUrl,
    'https://proof.ovh.net/files/10Mb.dat',
  ];
}

class ProxySpeedEntry {
  const ProxySpeedEntry({
    required this.proxyName,
    required this.mbps,
    required this.bytes,
    required this.durationMs,
    required this.statusCode,
    required this.testUrl,
    required this.testedAt,
  });

  final String proxyName;
  final double mbps;
  final int bytes;
  final int durationMs;
  final int statusCode;
  final String testUrl;
  final DateTime testedAt;

  String get formatted => '${mbps.toStringAsFixed(1)} MB/s';
}

class SpeedTestingGroups extends Notifier<Set<String>> {
  @override
  Set<String> build() => const {};

  bool start(String groupName) {
    if (state.contains(groupName)) return false;
    state = {...state, groupName};
    return true;
  }

  void stop(String groupName) {
    if (state.contains(groupName)) state = {...state}..remove(groupName);
  }
}

final speedTestingGroupsProvider =
    NotifierProvider<SpeedTestingGroups, Set<String>>(
  SpeedTestingGroups.new,
);

class ProxySpeedTest extends Notifier<Map<String, ProxySpeedEntry>> {
  @override
  Map<String, ProxySpeedEntry> build() => const {};

  ProxySpeedEntry? fastestAmong(Iterable<String> proxyNames) {
    ProxySpeedEntry? fastest;
    for (final name in proxyNames) {
      final entry = state[name];
      if (entry != null && (fastest == null || entry.mbps > fastest.mbps)) {
        fastest = entry;
      }
    }
    return fastest;
  }

  Future<ProxySpeedEntry?> _probeCloudUrl(
    String nodeName,
    String effectiveProxyName,
    String url,
  ) async {
    final result = await ref.read(coreHandlerProvider).probe(
          ProbeParams(
            url: url,
            proxyName: effectiveProxyName,
            headers: const {
              'Accept': '*/*',
              'Accept-Encoding': 'identity',
              'Cache-Control': 'no-cache',
            },
            timeout: speedTestTimeoutMs,
            maxBody: speedTestMaxBytes,
          ),
        );
    if (result == null) {
      commonPrint.log('Cloud speed test empty result for $nodeName: $url');
      return null;
    }
    if (result.error?.isNotEmpty ?? false) {
      commonPrint.log(
        'Cloud speed test failed for $nodeName: ${result.error} ${result.message}',
      );
      return null;
    }
    if (result.statusCode < 200 || result.statusCode >= 300) {
      commonPrint.log(
        'Cloud speed test HTTP ${result.statusCode} for $nodeName: $url',
      );
      return null;
    }

    final duration = result.duration > 0 ? result.duration : result.delay;
    if (result.bytes <= 0 || duration <= 0) {
      commonPrint.log(
        'Cloud speed test has no metrics for $nodeName: '
        'bytes=${result.bytes}, duration=$duration',
      );
      return null;
    }
    return ProxySpeedEntry(
      proxyName: nodeName,
      mbps: result.bytes / (1024 * 1024) / (duration / 1000),
      bytes: result.bytes,
      durationMs: duration,
      statusCode: result.statusCode,
      testUrl: url,
      testedAt: DateTime.now(),
    );
  }

  Future<ProxySpeedEntry?> test(Proxy proxy) async {
    final name = proxy.name;
    try {
      final realState = computeRealSelectedProxyState(
        name,
        groups: ref.read(groupsProvider),
        selectedMap: ref.read(selectedMapProvider),
      );
      final effectiveProxyName = realState.proxyName;
      if (effectiveProxyName.isEmpty) {
        commonPrint.log('Cloud speed test skipped for $name: no effective proxy');
        return null;
      }

      for (final url in _cloudSpeedTestUrls()) {
        try {
          final entry = await _probeCloudUrl(name, effectiveProxyName, url);
          if (entry != null) {
            state = {...state, name: entry};
            return entry;
          }
        } catch (error) {
          commonPrint.log('Cloud speed source failed for $name: $url: $error');
        }
      }
      commonPrint.log('All cloud speed sources failed for $name');
      return null;
    } catch (error, stackTrace) {
      commonPrint.log(
        'Cloud speed test failed for $name: $error\\n$stackTrace',
        logLevel: coreFailureLogLevel(error),
      );
      return null;
    }
  }
}

final proxySpeedProvider =
    NotifierProvider<ProxySpeedTest, Map<String, ProxySpeedEntry>>(
  ProxySpeedTest.new,
);
'''
)

rep(
    'lib/providers/providers.dart',
    "export 'route_state.dart';\n",
    "export 'route_state.dart';\nexport 'proxy_speed.dart';\n",
)
rep(
    'lib/providers/actions/proxies.dart',
    '  final TaskPool _delayTestPool = TaskPool(maxConcurrentDelayTests);\n',
    '  final TaskPool _delayTestPool = TaskPool(maxConcurrentDelayTests);\n'
    '  final TaskPool _speedTestPool = TaskPool(4);\n',
)
rep(
    'lib/providers/actions/proxies.dart',
    '\n  List<_DelayTestTarget> _resolveDelayTestTargets(',
    '''
  Future<void> speedTestPageGroup(
    String groupName, {
    bool matchSearch = true,
  }) async {
    final group = ref.read(groupsProvider).getGroup(groupName);
    if (group == null) return;
    final testing = ref.read(speedTestingGroupsProvider.notifier);
    if (!testing.start(groupName)) return;
    try {
      final query = SearchQuery(
        matchSearch ? ref.read(queryProvider(QueryTag.proxies)) : '',
      );
      final proxies = group.all
          .whereMatches(query, (proxy) => proxy.searchFields)
          .toList();
      final speed = ref.read(proxySpeedProvider.notifier);
      await Future.wait([
        for (final proxy in proxies)
          _speedTestPool.run(() => speed.test(proxy)),
      ]);
      final fastest = speed.fastestAmong(proxies.map((proxy) => proxy.name));
      if (fastest == null) {
        dialogs.showBanner(
          '云端测速 ${currentAppLocalizations.serviceFailed}',
          level: BannerLevel.error,
        );
      } else {
        dialogs.showBanner(
          '云端测速 ${currentAppLocalizations.done}: ${fastest.formatted}',
          level: BannerLevel.success,
        );
      }
    } finally {
      testing.stop(groupName);
    }
  }

  List<_DelayTestTarget> _resolveDelayTestTargets(''',
)
rep(
    'lib/views/proxies/tab.dart',
    '\n  Group? get currentGroup {',
    '''
  Future<void> speedTestCurrentGroup() async {
    final group = currentGroup;
    if (group == null) return;
    await ref
        .read(proxiesActionProvider.notifier)
        .speedTestPageGroup(group.name);
  }

  Group? get currentGroup {''',
)
rep(
    'lib/views/proxies/proxies.dart',
    '\n  void _onSearch(String value) {',
    '''
  IconButtonData? _buildSpeedAction() {
    if (!_isTab || widget.picker) return null;
    final groupName = _proxiesTabKey.currentState?.currentGroup?.name;
    final isTesting = groupName != null &&
        ref.watch(
          speedTestingGroupsProvider.select(
            (state) => state.contains(groupName),
          ),
        );
    return IconButtonData(
      glyph: AppGlyphs.speed,
      onPressed: () {
        _proxiesTabKey.currentState?.speedTestCurrentGroup();
      },
      tooltip: '云端测速',
      isLoading: isTesting,
    );
  }

  void _onSearch(String value) {''',
)
rep(
    'lib/views/proxies/proxies.dart',
    '''      iconActions: [
        if (_isTab && !picker)''',
    '''      iconActions: [
        ?_buildSpeedAction(),
        if (_isTab && !picker)''',
)
rep(
    'lib/views/proxies/proxies.dart',
    '''      _optionsMenuItem(
        glyph: AppGlyphs.textSize,
        label: appLocalizations.size,
        options: ProxyCardType.values,
        value: style.cardType,
        textOf: (type) => type.label,
        onSelected: (type) =>
            _updateStyle((state) => state.copyWith(cardType: type)),
      ),''',
    '''      _optionsMenuItem(
        glyph: AppGlyphs.textSize,
        label: appLocalizations.size,
        options: ProxyCardType.values,
        value: style.cardType,
        textOf: (type) => type.label,
        onSelected: (type) =>
            _updateStyle((state) => state.copyWith(cardType: type)),
      ),
      if (style.type == ProxiesType.tab)
        PopupMenuItem(
          glyph: AppGlyphs.speed,
          label: '云端测速',
          section: const PopupMenuSection(),
          onPressed: () {
            _proxiesTabKey.currentState?.speedTestCurrentGroup();
          },
        ),''',
)
print('Patched cloud download simulation with fallback sources')
