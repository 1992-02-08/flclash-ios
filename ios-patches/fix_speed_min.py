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
import 'package:fl_clash/state.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Proven working payload and timeout from the user's FlClash 0.9.3 IPA.
const int speedTestMaxBytes = 8 * 1024 * 1024;
const int speedTestTimeoutMs = 15000;
const String speedTestUrl =
    'https://speed.cloudflare.com/__down?bytes=$speedTestMaxBytes';

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
        commonPrint.log('Speed test skipped for $name: no effective proxy');
        return null;
      }
      final result = await ref.read(coreHandlerProvider).probe(
            ProbeParams(
              url: speedTestUrl,
              proxyName: effectiveProxyName,
              timeout: speedTestTimeoutMs,
              maxBody: speedTestMaxBytes,
            ),
          );
      if (result == null || (result.error?.isNotEmpty ?? false)) {
        commonPrint.log(
          'Speed test failed for $name: '
          '${result?.error ?? 'empty result'} ${result?.message ?? ''}',
        );
        return null;
      }
      final duration = result.duration > 0 ? result.duration : result.delay;
      if (result.bytes <= 0 || duration <= 0) {
        commonPrint.log(
          'Speed test failed for $name: '
          'bytes=${result.bytes}, duration=$duration',
        );
        return null;
      }
      final entry = ProxySpeedEntry(
        proxyName: name,
        mbps: result.bytes / (1024 * 1024) / (duration / 1000),
        bytes: result.bytes,
        durationMs: duration,
        statusCode: result.statusCode,
        testUrl: speedTestUrl,
        testedAt: DateTime.now(),
      );
      state = {...state, name: entry};
      return entry;
    } catch (error, stackTrace) {
      commonPrint.log(
        'Speed test failed for $name: $error\\n$stackTrace',
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
      dialogs.showBanner('下载测速开始：${proxies.length} 个节点');
      final speed = ref.read(proxySpeedProvider.notifier);
      await Future.wait([
        for (final proxy in proxies)
          _speedTestPool.run(() => speed.test(proxy)),
      ]);
      final fastest = speed.fastestAmong(proxies.map((proxy) => proxy.name));
      if (fastest == null) {
        dialogs.showBanner(
          '下载测速 ${currentAppLocalizations.serviceFailed}',
          level: BannerLevel.error,
        );
      } else {
        dialogs.showBanner(
          '下载测速 ${currentAppLocalizations.done}: ${fastest.formatted}',
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
  void _startDownloadSpeedTest() {
    final state = ref.read(proxiesTabStateProvider);
    final groupName = state.currentGroupName ??
        (state.groups.isEmpty ? null : state.groups.first.name);
    if (groupName == null) {
      dialogs.showBanner('下载测速：没有可用节点', level: BannerLevel.error);
      return;
    }
    final group = state.groups.firstWhere(
      (item) => item.name == groupName,
      orElse: () => state.groups.first,
    );
    dialogs.showBanner('下载测速开始：${group.all.length} 个节点');
    ref.read(proxiesActionProvider.notifier).speedTestPageGroup(groupName);
  }

  void _onSearch(String value) {''',
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
          label: '下载测速',
          section: const PopupMenuSection(),
          onPressed: _startDownloadSpeedTest,
        ),''',
)
print('Patched proven 0.9.3 speed implementation into current iOS port')
