import 'dart:async';

import 'package:fl_clash/common/common.dart';
import 'package:fl_clash/enum/enum.dart';
import 'package:fl_clash/models/models.dart';
import 'package:fl_clash/pages/scan.dart';
import 'package:fl_clash/providers/providers.dart';
import 'package:fl_clash/state.dart';
import 'package:fl_clash/ui/icons/icons.dart';
import 'package:fl_clash/views/profiles/custom/custom.dart';
import 'package:fl_clash/features/form/form.dart';
import 'package:fl_clash/widgets/widgets.dart';
import 'package:material_ui/material_ui.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

const _customOpenPause = Duration(milliseconds: 150);

void showAddProfilePage(BuildContext origin) {
  final context = globalState.navigatorKey.currentState!.context;
  showExtend(
    context,
    builder: (context) => CommonScaffold(
      title: context.appLocalizations.addProfile,
      body: AddProfileView(context: context, origin: origin),
    ),
  );
}

class AddProfileView extends ConsumerWidget {
  final BuildContext context;

  /// Where a page the add page leads to opens: the desktop sheet is on the root.
  final BuildContext origin;

  const AddProfileView({
    super.key,
    required this.context,
    required this.origin,
  });

  Future<void> _handleAddProfileFormFile(WidgetRef ref) async {
    unawaited(ref.read(profilesActionProvider.notifier).addProfileFormFile());
  }

  Future<void> _toScan(WidgetRef ref) async {
    final profilesAction = ref.read(profilesActionProvider.notifier);
    if (system.isDesktop) {
      unawaited(profilesAction.addProfileFormQrCode());
      return;
    }
    final url = await BaseNavigator.push(context, const ScanPage());
    if (url != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        unawaited(profilesAction.addProfileFromLink(url));
      });
    }
  }

  Future<void> _toAdd(WidgetRef ref) async {
    final profilesAction = ref.read(profilesActionProvider.notifier);
    final appLocalizations = context.appLocalizations;
    final res = await showNamedUrlsForm(
      context,
      title: appLocalizations.importFromLink,
      urlLabel: appLocalizations.link,
      batchTip: appLocalizations.batchLinkInputTip,
      urlValidator: (value) {
        if (value == null || value.isEmpty) {
          return appLocalizations.emptyTip(appLocalizations.link);
        }
        if (!value.isUrl && !value.isShareLink) {
          return appLocalizations.invalidLinkTip;
        }
        return null;
      },
      existingUrls: {
        for (final profile in ref.read(profilesProvider))
          if (profile.url.isNotEmpty) profile.url,
      },
      withAgeSecretKey: true,
    );
    switch (res) {
      case null:
        return;
      case [final single]:
        unawaited(
          profilesAction.addProfileFromLink(
            single.url,
            label: single.label,
            ageSecretKey: single.ageSecretKey,
          ),
        );
      default:
        unawaited(
          profilesAction.addProfilesFromLinks([
            for (final item in res) item.url,
          ]),
        );
    }
  }

  Future<void> _toAddCustom(BuildContext context, WidgetRef ref) async {
    final profilesAction = ref.read(profilesActionProvider.notifier);
    final label = context.appLocalizations.unnamed;
    Widget editor() => CustomProfileView(
      profileId: profilesAction.addCustomProfile(label),
      isNew: true,
    );
    final navigator = Navigator.of(context);
    if (!origin.mounted || Navigator.of(origin) == navigator) {
      unawaited(BaseNavigator.pushReplacement(context, editor()));
      return;
    }
    // The sheet sits above origin's navigator: a page opened there before the
    // sheet has gone fades in beneath it.
    navigator.pop();
    await whenRouteSettled(context);
    await Future<void>.delayed(_customOpenPause);
    if (origin.mounted) {
      unawaited(BaseNavigator.push(origin, editor()));
    }
  }

  void _toMerge(BuildContext context) {
    showExtend(
      context,
      builder: (context) => CommonScaffold(
        title: '聚合订阅',
        body: _MergeSubscriptionForm(origin: origin),
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final appLocalizations = context.appLocalizations;
    return ListView(
      padding: EdgeInsets.only(top: context.contentTopPadding, bottom: 16),
      children: [
        ListItem(
          leading: const GlyphIcon(AppGlyphs.qrCode),
          title: Text(appLocalizations.qrcode),
          subtitle: Text(appLocalizations.qrcodeDesc),
          onTap: () => _toScan(ref),
        ),
        ListItem(
          leading: const GlyphIcon(AppGlyphs.importFile),
          title: Text(appLocalizations.file),
          subtitle: Text(appLocalizations.fileDesc),
          onTap: () => _handleAddProfileFormFile(ref),
        ),
        ListItem(
          leading: const GlyphIcon(AppGlyphs.cloudDownload),
          title: Text(appLocalizations.link),
          subtitle: Text(appLocalizations.linkDesc),
          onTap: () => _toAdd(ref),
        ),
        ListItem(
          leading: const GlyphIcon(AppGlyphs.customize),
          title: Text(appLocalizations.customProfile),
          subtitle: Text(appLocalizations.customProfileDesc),
          onTap: () => _toAddCustom(context, ref),
        ),
        ListItem(
          leading: const GlyphIcon(AppGlyphs.layers),
          title: const Text('聚合订阅'),
          subtitle: const Text('把多个机场订阅合并成一个配置'),
          onTap: () => _toMerge(context),
        ),
      ],
    );
  }
}

class _MergeSubscriptionForm extends ConsumerStatefulWidget {
  final BuildContext origin;

  const _MergeSubscriptionForm({required this.origin});

  @override
  ConsumerState<_MergeSubscriptionForm> createState() =>
      _MergeSubscriptionFormState();
}

class _MergeSubscriptionFormState
    extends ConsumerState<_MergeSubscriptionForm> {
  final _groupName = TextEditingController();
  final _selected = <int>{};
  var _busy = false;

  @override
  void dispose() {
    _groupName.dispose();
    super.dispose();
  }

  Future<void> _submit(BuildContext context) async {
    final groupName = _groupName.text.trim();
    if (groupName.isEmpty || _selected.isEmpty) {
      dialogs.showMessage(
        context: context,
        title: '信息不完整',
        message: const TextSpan(text: '请填写组名，并勾选至少一个订阅'),
      );
      return;
    }
    setState(() {
      _busy = true;
    });
    try {
      final profile = await ref
          .read(profilesActionProvider.notifier)
          .createMergedSubscription(
        groupName: groupName,
        profileIds: _selected.toList(),
      );
      if (!mounted) {
        return;
      }
      final navigator = Navigator.of(context);
      navigator.pop();
      if (widget.origin.mounted) {
        unawaited(BaseNavigator.push(
          widget.origin,
          CustomProfileView(profileId: profile.id),
        ));
      }
    } catch (e) {
      if (mounted) {
        dialogs.showMessage(
          context: context,
          title: '创建失败',
          message: TextSpan(text: compactError(e)),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final profiles = ref.watch(profilesProvider);
    final subscriptions = [
      for (final profile in profiles)
        if (profile.type != ProfileType.custom) profile,
    ];
    return ListView(
      padding: EdgeInsets.only(
        top: context.contentTopPadding,
        left: 16,
        right: 16,
        bottom: 16,
      ),
      children: [
        TextField(
          controller: _groupName,
          decoration: const InputDecoration(labelText: '聚合组名称'),
        ),
        const SizedBox(height: 8),
        Text(
          '选择要合并的订阅（${_selected.length} 个）',
          style: const TextStyle(fontSize: 12, color: Colors.grey),
        ),
        const SizedBox(height: 4),
        if (subscriptions.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 24),
            child: Text(
              '还没有订阅，请先在配置页添加机场订阅',
              textAlign: TextAlign.center,
            ),
          )
        else
          ...subscriptions.map(
            (profile) => ListItem.toggle(
              key: ValueKey(profile.id),
              title: Text(profile.realLabel),
              subtitle: profile.subscriptionInfo == null
                  ? null
                  : Text(
                      '${profile.subscriptionInfo!.upload.traffic.show} ↑ / '
                      '${profile.subscriptionInfo!.download.traffic.show} ↓ · '
                      '${profile.subscriptionInfo!.expire == 0 ? '长期' : DateTime.fromMillisecondsSinceEpoch(profile.subscriptionInfo!.expire * 1000).show}',
                    ),
              value: _selected.contains(profile.id),
              onChanged: (value) {
                setState(() {
                  if (value) {
                    _selected.add(profile.id);
                  } else {
                    _selected.remove(profile.id);
                  }
                });
              },
            ),
          ),
        const SizedBox(height: 16),
        FilledButton(
          onPressed: _busy ? null : () => _submit(context),
          child: Text(_busy ? '创建中…' : '创建聚合订阅'),
        ),
        const SizedBox(height: 8),
        const Text(
          '将从已勾选的订阅中合并全部节点到一个组',
          style: TextStyle(fontSize: 12, color: Colors.grey),
        ),
      ],
    );
  }
}
