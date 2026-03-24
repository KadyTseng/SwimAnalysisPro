import 'package:flutter/material.dart';

class ScreenShareView extends StatelessWidget {
  final VoidCallback onStop;
  const ScreenShareView({super.key, required this.onStop});
  @override
  Widget build(BuildContext context) => const Center(child: Text("Screen share not supported on this platform"));
}
