import 'package:flutter/material.dart';

class SwitchCameraButton extends StatelessWidget {
  final VoidCallback onTap;
  final bool isFront;
  const SwitchCameraButton({super.key, required this.onTap, required this.isFront});

  @override
  Widget build(BuildContext context) {
    return FloatingActionButton.small(
      onPressed: onTap,
      child: Icon(isFront ? Icons.flip_camera_android : Icons.flip_camera_ios),
    );
  }
}
