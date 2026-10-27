import 'package:fl_clash/common/common.dart';
import 'package:fl_clash/core/core.dart';
import 'package:fl_clash/models/models.dart';
import 'package:fl_clash/providers/app.dart';
import 'package:fl_clash/providers/core.dart';
import 'package:fl_clash/providers/state.dart';
import 'package:fl_clash/state.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The fixed-size resource used for throughput measurements.
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
    if (state.contains(groupName)) {
      return false;
    }
    state = {...state, groupName};
    return true;
  }

  void stop(String groupName) {
    if (state.contains(groupName)) {
      state = {...state}..remove(groupName);
    }
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
      final groups = ref.read(groupsProvider);
      final selectedMap = ref.read(selectedMapProvider);
      final realState = computeRealSelectedProxyState(
        name,
        groups: groups,
        selectedMap: selectedMap,
      );
      final effectiveProxyName = realState.proxyName;
      if (effectiveProxyName.isEmpty) {
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
        return null;
      }
      final duration = result.duration > 0 ? result.duration : result.delay;
      if (result.bytes <= 0 || duration <= 0) {
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
        'Speed test failed for $name: $error\n$stackTrace',
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
