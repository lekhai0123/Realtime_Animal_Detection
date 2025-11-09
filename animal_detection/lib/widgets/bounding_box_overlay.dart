import 'dart:math' as math;
import 'package:flutter/material.dart';

class BoundingBoxOverlay extends StatelessWidget {
  final List detections;
  final double imageW; // ví dụ 720
  final double imageH; // ví dụ 480

  const BoundingBoxOverlay({
    super.key,
    required this.detections,
    required this.imageW,
    required this.imageH,
  });

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter: _BoxPainter(detections, imageW, imageH),
      child: const SizedBox.expand(),
    );
  }
}

class _BoxPainter extends CustomPainter {
  final List dets;
  final double srcW, srcH;
  _BoxPainter(this.dets, this.srcW, this.srcH);

  @override
  void paint(Canvas c, Size size) {
    final p = Paint()
      ..color = const Color(0xFFFF0000)
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;

    final textPainter = TextPainter(
      textDirection: TextDirection.ltr,
      textAlign: TextAlign.left,
    );

    c.save();
    c.translate(size.width, 0);
    c.rotate(math.pi / 2);

    final rotW = size.height;
    final rotH = size.width;

    final fitted = applyBoxFit(BoxFit.contain, Size(srcW, srcH), Size(rotW, rotH));
    final drawW = fitted.destination.width;
    final drawH = fitted.destination.height;

    final sx = drawW / srcW;
    final sy = drawH / srcH;
    final offX = (rotW - drawW) / 2.0;
    final offY = (rotH - drawH) / 2.0;

    for (final d in dets) {
      final b = d["bbox_xyxy"];
      if (b == null || b.length != 4) continue;
      final x1 = b[0] * sx + offX;
      final y1 = b[1] * sy + offY;
      final x2 = b[2] * sx + offX;
      final y2 = b[3] * sy + offY;

      // vẽ khung
      c.drawRect(Rect.fromLTRB(x1, y1, x2, y2), p);

      // vẽ track_id + class_name
      final cls = d["cls_name"] ?? "";
      final tid = d["track_id"] != null ? "#${d["track_id"]}" : "";
      final label = "$cls $tid";

      textPainter.text = TextSpan(
        text: label,
        style: const TextStyle(
          color: Colors.red,
          fontSize: 12,
          backgroundColor: Colors.white70,
        ),
      );
      textPainter.layout();
      textPainter.paint(c, Offset(x1, y1 - 14));
    }

    c.restore();
  }

  @override
  bool shouldRepaint(covariant _BoxPainter o) =>
      o.dets != dets || o.srcW != srcW || o.srcH != srcH;
}

