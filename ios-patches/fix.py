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
