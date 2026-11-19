from pathlib import Path
for name, old, new in [
 ('core/lib.go','//go:build android','//go:build android || ios'),
 ('core/tun/tun.go','//go:build android','//go:build android || ios'),
 ('core/server.go','//go:build !android','//go:build !android && !ios'),
]:
 p=Path('up')/name
 text=p.read_text()
 assert text.startswith(old), name
 p.write_text(text.replace(old,new,1))
 print('iOS build tag:',name)
p=Path('up/lib/providers/actions/setup.dart')
s=p.read_text().replace('final inputsApplied = await _inputsApplied();','final applied = await inputsApplied();').replace('&& !inputsApplied)', '&& !applied)').replace('_inputsApplied()', 'inputsApplied()')
p.write_text(s)
p=Path('up/lib/manager/app_manager.dart')
s=p.read_text().replace('ref.read(proxiesActionProvider.notifier).invalidateForResume();','// Group refresh below uses the upstream lifecycle.').replace('final blur = ref.watch(windowBlurProvider);','final backdropOpacity = ref.watch(windowBlurProvider);').replace('color: blur ? Colors.transparent : page,','color: backdropOpacity != null ? Colors.transparent : page,')
p.write_text(s)
