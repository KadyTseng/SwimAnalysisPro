import 'dart:html' as html;
import 'dart:ui_web' as ui_web;
import 'dart:math' as math;
import 'dart:js_util' as js_util;
import 'package:flutter/material.dart';

class ScreenShareView extends StatefulWidget {
  final VoidCallback onStop;

  const ScreenShareView({super.key, required this.onStop});

  @override
  State<ScreenShareView> createState() => _ScreenShareViewState();
}

class _ScreenShareViewState extends State<ScreenShareView> {
  html.VideoElement? _videoElement;
  late String _viewType;
  bool _isSharing = false;
  String? _error;
  html.MediaStream? _mediaStream;

  @override
  void initState() {
    super.initState();
    _viewType = 'screen-share-view-${math.Random().nextInt(10000)}';
    _startSharing();
  }

  Future<void> _startSharing() async {
    try {
      final mediaDevices = html.window.navigator.mediaDevices;
      if (mediaDevices == null) throw Exception("MediaDevices not supported");

      final mediaStream = await js_util.promiseToFuture<html.MediaStream>(
        js_util.callMethod(mediaDevices, 'getDisplayMedia', [
          js_util.jsify({'video': true, 'audio': false})
        ])
      );

      _videoElement = html.VideoElement()
        ..srcObject = mediaStream
        ..autoplay = true
        ..style.border = 'none'
        ..style.width = '100%'
        ..style.height = '100%';

      _mediaStream = mediaStream;

      // Listen for the stream ending (e.g., user clicked "Stop sharing" in browser UI)
      if (mediaStream.getVideoTracks().isNotEmpty) {
        mediaStream.getVideoTracks().first.onEnded.listen((_) {
          if (mounted) widget.onStop();
        });
      }

      ui_web.platformViewRegistry.registerViewFactory(
        _viewType,
        (int viewId) => _videoElement!,
      );

      if (mounted) {
        setState(() {
          _isSharing = true;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
        });
      }
    }
  }

  @override
  void dispose() {
    if (_mediaStream != null) {
      for (var track in _mediaStream!.getTracks()) {
        track.stop();
      }
    }
    _videoElement?.removeAttribute('srcObject');
    _videoElement?.remove();
    _videoElement = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, color: Colors.red, size: 48),
            const SizedBox(height: 16),
            Text("Failed to share screen: $_error", style: const TextStyle(color: Colors.white)),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: widget.onStop,
              child: const Text("Go back"),
            )
          ],
        )
      );
    }

    if (!_isSharing) {
      return const Center(child: CircularProgressIndicator());
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        return SizedBox(
          width: constraints.hasBoundedWidth ? constraints.maxWidth : 800,
          height: constraints.hasBoundedHeight ? constraints.maxHeight : 600,
          child: HtmlElementView(viewType: _viewType),
        );
      }
    );
  }
}
