from pathlib import Path
import sys
r=Path(sys.argv[1] if len(sys.argv)>1 else 'up')
def rep(p,a,b):
 q=r/p;s=q.read_text();assert s.count(a)==1,(p,s.count(a));q.write_text(s.replace(a,b,1))
(r/'lib/providers/proxy_speed.dart').write_text('''import 'package:fl_clash/common/common.dart';
import 'package:fl_clash/core/core.dart';
import 'package:fl_clash/models/models.dart';
import 'package:fl_clash/providers/core.dart';
import 'package:fl_clash/providers/state.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
const speedTestMaxBytes=8*1024*1024;
const speedTestTimeoutMs=15000;
const speedTestUrl='https://speed.cloudflare.com/__down?bytes=$speedTestMaxBytes';
class ProxySpeedEntry{const ProxySpeedEntry(this.proxyName,this.mbps);final String proxyName;final double mbps;String get formatted=>'${mbps.toStringAsFixed(1)} MB/s';}
class SpeedTestingGroups extends Notifier<Set<String>>{@override Set<String> build()=>const {};bool start(String n){if(state.contains(n))return false;state={...state,n};return true;}void stop(String n){if(state.contains(n))state={...state}..remove(n);}}
final speedTestingGroupsProvider=NotifierProvider<SpeedTestingGroups,Set<String>>(SpeedTestingGroups.new);
class ProxySpeedTest extends Notifier<Map<String,ProxySpeedEntry>>{@override Map<String,ProxySpeedEntry> build()=>const {};ProxySpeedEntry? best(Iterable<String> ns){ProxySpeedEntry? b;for(final n in ns){final e=state[n];if(e!=null&&(b==null||e.mbps>b.mbps))b=e;}return b;}Future<ProxySpeedEntry?> test(Proxy p)async{try{final x=computeRealSelectedProxyState(p.name,groups:ref.read(groupsProvider),selectedMap:ref.read(selectedMapProvider));if(x.proxyName.isEmpty)return null;final y=await ref.read(coreHandlerProvider).probe(ProbeParams(url:speedTestUrl,proxyName:x.proxyName,timeout:speedTestTimeoutMs,maxBody:speedTestMaxBytes));if(y.error?.isNotEmpty??false)return null;final ms=y.duration>0?y.duration:y.delay;if(y.bytes<=0||ms<=0)return null;final e=ProxySpeedEntry(p.name,y.bytes/(1024*1024)/(ms/1000));state={...state,p.name:e};return e;}catch(e){commonPrint.log('speed test ${p.name}: $e');return null;}}}
final proxySpeedProvider=NotifierProvider<ProxySpeedTest,Map<String,ProxySpeedEntry>>(ProxySpeedTest.new);
''')
rep('lib/providers/providers.dart',"export 'route_state.dart';\n","export 'route_state.dart';\nexport 'proxy_speed.dart';\n")
rep('lib/providers/actions/proxies.dart','  final TaskPool _delayTestPool = TaskPool(maxConcurrentDelayTests);\n','  final TaskPool _delayTestPool = TaskPool(maxConcurrentDelayTests);\n  final _speedTestPool=TaskPool(4);\n')
rep('lib/providers/actions/proxies.dart','\n  List<_DelayTestTarget> _resolveDelayTestTargets(','''\n  Future<void> speedTestPageGroup(String name,{bool matchSearch=true}) async {final g=ref.read(groupsProvider).getGroup(name);if(g==null)return;final t=ref.read(speedTestingGroupsProvider.notifier);if(!t.start(name))return;try{final q=SearchQuery(matchSearch?ref.read(queryProvider(QueryTag.proxies)):'');final ps=g.all.whereMatches(q,(p)=>p.searchFields).toList();await Future.wait(ps.map((p)=>_speedTestPool.run(()=>ref.read(proxySpeedProvider.notifier).test(p))));final b=ref.read(proxySpeedProvider.notifier).best(ps.map((p)=>p.name));dialogs.showBanner(b==null?'下载测速失败':'下载测速完成：${b.formatted}',level:b==null?BannerLevel.error:BannerLevel.success);}finally{t.stop(name);}}

  List<_DelayTestTarget> _resolveDelayTestTargets(''')
rep('lib/views/proxies/tab.dart','\n  Group? get currentGroup {','''
  Future<void> speedTestCurrentGroup() async {final g=currentGroup;if(g==null)return;await ref.read(proxiesActionProvider.notifier).speedTestPageGroup(g.name);}

  Group? get currentGroup {''')
rep('lib/views/proxies/proxies.dart','\n  void _onSearch(String value) {',"""
  IconButtonData? _buildSpeedAction(){if(!_isTab)return null;return IconButtonData(glyph:AppGlyphs.speed,onPressed:()=>_proxiesTabKey.currentState?.speedTestCurrentGroup(),tooltip:'下载测速',isLoading:ref.watch(speedTestingGroupsProvider).isNotEmpty);}

  void _onSearch(String value) {""")
rep('lib/views/proxies/proxies.dart','      iconActions: [\n        if (_isTab && !picker)','      iconActions: [\n        ?_buildSpeedAction(),\n        if (_isTab && !picker)')
print('speed patch applied')