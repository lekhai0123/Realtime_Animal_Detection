import 'package:flutter/material.dart';

class FpsDisplay extends StatelessWidget {
  final double fps;
  final int latencyMs;
  const FpsDisplay({super.key, required this.fps, required this.latencyMs});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.topRight,
      child: Container(
        margin: const EdgeInsets.all(8),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        color: const Color(0x80000000),
        child: Text("FPS: ${fps.toStringAsFixed(1)} | ${latencyMs}ms",
            style: const TextStyle(color: Color(0xFF00FFC8), fontSize: 12)),
      ),
    );
  }
}
