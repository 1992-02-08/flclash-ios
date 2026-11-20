#!/usr/bin/env python3
"""Patch the assembled v0.9.4 source before Flutter Native Assets builds."""
from pathlib import Path
import re
import sys

IOS_ENVIRONMENT = r'''
// QuickJS bindgen must load Xcode's libclang and the selected iOS SDK.
Map<String, String> _iosEnvironment(BuildInput input) {
  if (!input.config.buildCodeAssets || input.config.code.targetOS != OS.iOS) {
    return const {};
  }
  if (!Platform.isMacOS) {
    throw StateError('The iOS Rust build requires macOS with full Xcode');
  }
  final code = input.config.code;
  final sdk = code.iOS.targetSdk == IOSSdk.iPhoneOS
      ? 'iphoneos'
      : code.iOS.targetSdk == IOSSdk.iPhoneSimulator
      ? 'iphonesimulator'
      : throw StateError('Unknown iOS SDK: ${code.iOS.targetSdk}');
  String xcrun(List<String> arguments) {
    final result = Process.runSync('xcrun', arguments);
    final value = (result.stdout as String).trim();
    if (result.exitCode != 0 || value.isEmpty) {
      throw StateError('xcrun ${arguments.join(" ")}: ${result.stderr}');
    }
    return value;
  }
  final sdkRoot = xcrun(['--sdk', sdk, '--show-sdk-path']);
  final clang = File(xcrun(['--find', 'clang']));
  final libclang = Directory(
    '${clang.parent.parent.path}${Platform.pathSeparator}lib',
  );
  if (!libclang.existsSync() || !libclang.listSync().any(_isLibclang)) {
    throw StateError('No Xcode libclang in ${libclang.path}');
  }
  var version = code.iOS.targetVersion < 15 ? 15 : code.iOS.targetVersion;
  for (final key in const ['IPHONEOS_DEPLOYMENT_TARGET', 'DEPLOY_TARGET']) {
    final requested = int.tryParse(
      (Platform.environment[key] ?? '').split('.').first,
    );
    if (requested != null && requested > version) version = requested;
  }
  final triple = rustTargetTriple(code);
  final target = triple.replaceAll('-', '_');
  final arch = code.targetArchitecture == Architecture.arm64 ? 'arm64' : 'x86_64';
  final clangTarget = '$arch-apple-ios$version.0'
      '${sdk == "iphonesimulator" ? "-simulator" : ""}';
  final bindgenKey = 'BINDGEN_EXTRA_CLANG_ARGS_$target';
  final previous = Platform.environment[bindgenKey] ??
      Platform.environment['BINDGEN_EXTRA_CLANG_ARGS'] ?? '';
  final escapedSdk = sdkRoot.replaceAll('"', r'\"');
  return {
    'IPHONEOS_DEPLOYMENT_TARGET': '$version.0',
    'SDKROOT': sdkRoot,
    'LIBCLANG_PATH': libclang.path,
    bindgenKey: '$previous --target=$clangTarget -isysroot "$escapedSdk"',
  };
}
'''

def apply(root):
    root = Path(root).resolve()
    assert (root / 'pubspec.yaml').is_file(), f'Not an assembled source root: {root}'
    staged = {}

    def read(relative):
        path = root / relative
        assert path.is_file(), f'Missing {relative}'
        text = path.read_text(encoding='utf-8')
        assert '<<<<<<< ' not in text, f'Conflict markers in {relative}'
        return text

    def once(text, old, new, name):
        if new in text:
            assert text.count(new) == 1, f'{name}: duplicate patched block'
            return text
        assert text.count(old) == 1, f'{name}: expected exactly one anchor {old!r}'
        return text.replace(old, new, 1)

    def stage(relative, text):
        if text != read(relative):
            staged[relative] = text

    rel = 'plugins/setup/setup_hooks/lib/src/target.dart'
    text = read(rel)
    assert "import 'package:code_assets/code_assets.dart';" in text
    anchor = "    OS.macOS => '$arch-apple-darwin',"
    ios = """    OS.iOS when arch == 'aarch64' &&
        code.iOS.targetSdk == IOSSdk.iPhoneOS => 'aarch64-apple-ios',
    OS.iOS when arch == 'aarch64' &&
        code.iOS.targetSdk == IOSSdk.iPhoneSimulator => 'aarch64-apple-ios-sim',
    OS.iOS when arch == 'x86_64' &&
        code.iOS.targetSdk == IOSSdk.iPhoneSimulator => 'x86_64-apple-ios',
"""
    text = once(text, anchor, ios + anchor, rel)
    stage(rel, text)

    base = 'plugins/rust_api/'
    rel = base + 'rust/rust-toolchain.toml'
    text = read(rel)
    channel = re.search(r'^channel\s*=\s*"([^"]+)"', text, re.M)
    assert channel and re.fullmatch(r'\d+\.\d+\.\d+', channel[1]), 'Require pinned Rust'
    missing = [t for t in ('aarch64-apple-ios', 'aarch64-apple-ios-sim',
                           'x86_64-apple-ios') if f'"{t}"' not in text]
    if missing:
        anchor = '  "x86_64-apple-darwin",\n'
        text = once(text, anchor, anchor + ''.join(f'  "{t}",\n' for t in missing), rel)
    stage(rel, text)

    rel = base + 'rust/Cargo.toml'
    text = read(rel)
    for old, new in [
        ('[target.\'cfg(not(target_os = "android"))\'.dependencies]',
         '[target.\'cfg(all(not(target_os = "android"), not(target_os = "ios")))\'.dependencies]'),
        ('[target.\'cfg(all(unix, not(target_os = "android")))\'.dependencies]',
         '[target.\'cfg(all(unix, not(target_os = "android"), not(target_os = "ios")))\'.dependencies]'),
        ('[target.\'cfg(target_os = "android")\'.dependencies]',
         '[target.\'cfg(any(target_os = "android", target_os = "ios"))\'.dependencies]'),
    ]:
        text = once(text, old, new, rel)
    pin = '[target.\'cfg(target_os = "ios")\'.dependencies]\nlibc = "=0.2.189"\n\n'
    if pin not in text:
        assert '[target.\'cfg(target_os = "ios")\'.dependencies]' not in text
        anchor = '[target.\'cfg(target_os = "macos")\'.dependencies]'
        text = once(text, anchor, '# backtrace 0.3.76 needs dyld APIs hidden on iOS by libc 0.2.190.\n' + pin + anchor, rel)
    assert 'features = ["bindgen"]' in text
    stage(rel, text)

    for module in ('hotkey', 'ipc'):
        rel = base + f'rust/src/{module}/mod.rs'
        text = read(rel)
        old = 'target_os = "android"'
        new = 'any(target_os = "android", target_os = "ios")'
        if 'target_os = "ios"' not in text:
            expected = 6 if module == 'hotkey' else 8
            assert text.count(old) == expected, f'Unexpected guards in {rel}'
            text = text.replace(old, new)
        assert '#[cfg(any(target_os = "android", target_os = "ios"))]\nmod unsupported;' in text
        assert f'mod {"service" if module == "hotkey" else "server"};' in text
        stage(rel, text)

    rel = base + 'hook/build.dart'
    text = read(rel)
    assert 'FlutterRustBridgeNativeAssetsBuilder(' in text
    assert '..._bindgenEnvironment(input),' in text
    assert '..._trimmedPathEnvironment(input),' in text
    text = once(text, '        ..._bindgenEnvironment(input),\n',
                '        ..._bindgenEnvironment(input),\n        ..._iosEnvironment(input),\n', rel)
    if 'Map<String, String> _iosEnvironment(BuildInput input)' not in text:
        text = text.rstrip() + '\n' + IOS_ENVIRONMENT
    assert text.count('Map<String, String> _iosEnvironment(BuildInput input)') == 1
    assert text.count('await FlutterRustBridgeNativeAssetsBuilder(') == 1
    stage(rel, text)

    rel = base + 'rust/Cargo.lock'
    text = read(rel)
    old = ('name = "libc"\nversion = "0.2.190"\n'
           'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
           'checksum = "ce5d3ddc6d3fa000eb1536d85e147bfe31aacaba692ed6a876f95cb7c855be78"')
    new = ('name = "libc"\nversion = "0.2.189"\n'
           'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
           'checksum = "3eaf3ede3fee6db1a4c2ee091bf8a8b4dccdc6d17f656fb07896ee72867612f2"')
    text = once(text, old, new, rel)
    assert text.count('name = "libc"\n') == 1
    assert 'name = "bindgen"\n' in text
    stage(rel, text)

    assert len(staged) in (0, 7), f'Partial prior patch: review {sorted(staged)}'
    for relative, text in staged.items():
        (root / relative).write_text(text, encoding='utf-8')
        print('patched', relative)
    print(f'Rust iOS fixes verified ({len(staged)} files changed; Rust {channel[1]})')
    return sorted(staged)

if __name__ == '__main__':
    assert len(sys.argv) == 2, 'usage: python3 fix_rust_ios.py ASSEMBLED_SOURCE_ROOT'
    apply(sys.argv[1])
