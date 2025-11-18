import 'dart:convert';
import 'dart:typed_data';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:image/image.dart' as img;
import 'package:native_device_orientation/native_device_orientation.dart';
import '../config/api_config.dart';
import '../services/websocket_service.dart';
import '../widgets/bounding_box_overlay.dart';

class CameraLiveScreen extends StatefulWidget {
  const CameraLiveScreen({super.key});

  @override
  State<CameraLiveScreen> createState() => _CameraLiveScreenState();
}

class _CameraLiveScreenState extends State<CameraLiveScreen> {
  CameraController? _cam;
  late Future<void> _initFuture;
  bool _streaming = false;
  bool _sending = false;
  bool _awaitingResponse = false;
  WebSocketService? _ws; // ✅ để có thể reconnect
  double _imageW = 1, _imageH = 1;

  List _detections = [];
  double _fps = 0.0;
  int _latency = 0;
  final Duration _interval = const Duration(milliseconds: 100);
  DateTime _lastSend = DateTime.now();

  @override
  void initState() {
    super.initState();
    _initFuture = _initCam();
  }

  Future<void> _initCam() async {
    final cams = await availableCameras();
    final desc = cams.firstWhere(
      (c) => c.lensDirection == CameraLensDirection.back,
      orElse: () => cams.first,
    );
    _cam = CameraController(desc, ResolutionPreset.medium, enableAudio: false);
    await _cam!.initialize();
    print("📸 Camera sensorOrientation=${desc.sensorOrientation}");
    print("📸 Preview size=${_cam!.value.previewSize}");
  }

  void _startStream() {
    if (_streaming || _cam == null) return;

    setState(() {
      _streaming = true;
      _detections = [];
      _awaitingResponse = false;
    });

    // ✅ reconnect nếu đã đóng
    _ws ??= WebSocketService(ApiConfig.wsDetect);
    _ws!.onData = (dets, fps, latency, data) {
      final tRecv = DateTime.now().millisecondsSinceEpoch;
      final tSend = data?['t_client_send'] ?? 0;
      final tBackend = data?['t_backend'] ?? 0;
      final tBackendDone = data?['t_backend_done'] ?? tRecv;

      final rtt = tRecv - tSend; // ms
      final up = tBackendDone - tSend; // encode → server
      final down = tRecv - tBackendDone; // server → client

      print(
        "📊 RTT=$rtt ms | Up=$up ms | Down=$down ms | Backend=$tBackend ms",
      );

      setState(() {
        _detections = dets;
        _fps = fps;
        _latency = latency;
        _awaitingResponse = false;
        _imageW = (data?['image_width'] ?? 1).toDouble();
        _imageH = (data?['image_height'] ?? 1).toDouble();
      });
    };

    _ws!.connect();
    print("🟢 WebSocket connected");

    _cam!.startImageStream((image) async {
      if (!_streaming || _sending || _awaitingResponse) return;
      final t0 = DateTime.now().millisecondsSinceEpoch;
      final now = DateTime.now();
      if (now.difference(_lastSend) < _interval) return;
      _lastSend = now;
      _sending = true;

      try {
        final t1 = DateTime.now().millisecondsSinceEpoch;
        final jpg = await _yuv420ToJpegFast(image);
        final t2 = DateTime.now().millisecondsSinceEpoch;

        _awaitingResponse = true;
        final angle = _cam!.description.sensorOrientation;
        String orientation = "portraitUp";
        try {
          final deviceOri = await NativeDeviceOrientationCommunicator()
              .orientation(useSensor: true);
          orientation = deviceOri.name;
        } catch (_) {}

        _ws!.sendJson({
          "angle": angle,
          "device_orientation": orientation,
          "width": image.width,
          "height": image.height,
          "image": base64Encode(jpg),
          "t_client_send": t2, // gửi timestamp client
        });

        print("Encode: ${(t2 - t1) / 1000} ms");
      } catch (e) {
        debugPrint("Encode error: $e");
      } finally {
        _sending = false;
      }
    });
  }

  Future<Uint8List> _yuv420ToJpegFast(CameraImage image) async {
    final w = image.width;
    final h = image.height;
    final yPlane = image.planes[0];
    final uPlane = image.planes[1];
    final vPlane = image.planes[2];
    final yRowStride = yPlane.bytesPerRow;
    final uvRowStride = uPlane.bytesPerRow;
    final uvPixelStride = uPlane.bytesPerPixel!;
    final out = img.Image(width: w, height: h);

    for (int y = 0; y < h; y++) {
      final yRow = y * yRowStride;
      final uvRow = (y >> 1) * uvRowStride;
      for (int x = 0; x < w; x++) {
        final Y = yPlane.bytes[yRow + x];
        final uvIndex = uvRow + (x >> 1) * uvPixelStride;
        final U = uPlane.bytes[uvIndex];
        final V = vPlane.bytes[uvIndex];
        double r = Y + 1.402 * (V - 128);
        double g = Y - 0.344136 * (U - 128) - 0.714136 * (V - 128);
        double b = Y + 1.772 * (U - 128);
        out.setPixelRgba(
          x,
          y,
          r.clamp(0, 255).toInt(),
          g.clamp(0, 255).toInt(),
          b.clamp(0, 255).toInt(),
          255,
        );
      }
    }
    return Uint8List.fromList(img.encodeJpg(out, quality: 85));
  }

  Future<void> _stopStream() async {
    if (!_streaming || _cam == null) return;
    print("🛑 Stopping stream...");

    setState(() {
      _streaming = false;
      _detections = [];
      _awaitingResponse = false;
    });

    try {
      if (_cam!.value.isStreamingImages) {
        await _cam!.stopImageStream();
      }
    } catch (_) {}

    try {
      _ws?.close();
      _ws = null; // ✅ reset để reconnect lại lần sau
      print("🔌 WebSocket closed");
    } catch (_) {}
  }

  @override
  void dispose() {
    _stopStream();
    _cam?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<void>(
      future: _initFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }

        final previewSize = _cam!.value.previewSize!;
        final isPortrait =
            MediaQuery.of(context).orientation == Orientation.portrait;
        final previewAspect = isPortrait
            ? (previewSize.height / previewSize.width)
            : (previewSize.width / previewSize.height);

        return Scaffold(
          appBar: AppBar(title: const Text("Realtime Detection")),
          body: Center(
            child: AspectRatio(
              aspectRatio: previewAspect,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  CameraPreview(_cam!),
                  BoundingBoxOverlay(
                    detections: _detections,
                    imageW: _imageW,
                    imageH: _imageH,
                  ),
                ],
              ),
            ),
          ),
          floatingActionButton: FloatingActionButton(
            backgroundColor: _streaming ? Colors.red : Colors.teal,
            onPressed: _streaming ? _stopStream : _startStream,
            child: Icon(_streaming ? Icons.stop : Icons.play_arrow),
          ),
        );
      },
    );
  }
}
