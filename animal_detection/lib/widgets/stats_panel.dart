import 'package:flutter/material.dart';

class StatsPanel extends StatelessWidget {
  final Map<String, dynamic> stats;
  const StatsPanel({super.key, required this.stats});

  @override
  Widget build(BuildContext context) {
    final entries = stats.entries.toList()..sort((a,b)=>b.value.compareTo(a.value));
    return Align(
      alignment: Alignment.topLeft,
      child: Container(
        margin: const EdgeInsets.all(8),
        padding: const EdgeInsets.all(8),
        color: const Color(0x80000000),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: entries.take(6).map((e) =>
              Text("${e.key}: ${e.value}", style: const TextStyle(color: Colors.white, fontSize: 12))
          ).toList(),
        ),
      ),
    );
  }
}
