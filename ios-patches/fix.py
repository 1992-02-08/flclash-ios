from pathlib import Path
from subprocess import run
from tempfile import TemporaryDirectory
import shutil

for name, old, new in [
 ('core/lib.go','//go:build android','//go:build android || ios'),
 ('core/tun/tun.go','//go:build android','//go:build android || ios'),
 ('core/server.go','//go:build !android','//go:build !android && !ios'),
]:
 p=Path('up')/name; text=p.read_text(); assert text.startswith(old), name; p.write_text(text.replace(old,new,1))
p=Path('up/core/lib.go'); s=p.read_text().replace('dns.UpdateSystemDNS(addr)\n\t\tdns.FlushCacheWithDefaultResolver()', 'applySystemDns(addr)').replace('\n\t"github.com/metacubex/mihomo/dns"', ''); p.write_text(s)
p=Path('up/lib/providers/actions/setup.dart'); s=p.read_text().replace('final inputsApplied = await _inputsApplied();','final applied = await inputsApplied();').replace('&& !inputsApplied)', '&& !applied)').replace('_inputsApplied()', 'inputsApplied()'); p.write_text(s)
p=Path('up/lib/manager/app_manager.dart'); s=p.read_text().replace('ref.read(proxiesActionProvider.notifier).invalidateForResume();','// Group refresh below uses the upstream lifecycle.').replace('final blur = ref.watch(windowBlurProvider);','final backdropOpacity = ref.watch(windowBlurProvider);').replace('color: blur ? Colors.transparent : page,','color: backdropOpacity != null ? Colors.transparent : page,'); p.write_text(s)
shutil.copy2('lib/common/ip_quality.dart','up/lib/common/ip_quality.dart')
prism=Path('up/plugins/prism_ui')
with TemporaryDirectory() as tmp:
 a=Path(tmp)/'prism.tgz'; run(['curl','-fL','--retry','4','https://codeload.github.com/chen08209/prism_ui/tar.gz/6c47901cc80b5325bdb9650579ca2e000a60b39e','-o',str(a)],check=True); shutil.rmtree(prism); prism.mkdir(); run(['tar','xzf',str(a),'-C',str(prism),'--strip-components=1'],check=True)
# The 0.9.4 UI needs the speed-test entry point from the port.
run(['python3','ios-patches/fix_speed_min.py'], check=True)
# v0.9.4 has no downloadSpeedTest localization key; keep the port label stable.
p=Path('up/lib/providers/actions/proxies.dart')
s=p.read_text()
s=s.replace("          '${currentAppLocalizations.downloadSpeedTest} '\n          '${currentAppLocalizations.serviceFailed}',", "          '下载测速 ${currentAppLocalizations.serviceFailed}',")
s=s.replace("          '${currentAppLocalizations.downloadSpeedTest} '\n          '${currentAppLocalizations.done}: ${fastest.formatted}',", "          '下载测速 ${currentAppLocalizations.done}: ${fastest.formatted}',")
p.write_text(s)
