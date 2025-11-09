import 'dart:convert';
import 'dart:typed_data';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;

typedef OnDataCallback = void Function(List dets, double fps, int latency, Map? raw);
typedef OnBinaryDataCallback = void Function(List dets, double fps, int latency, Map? raw);

class WebSocketService {
  final String url;
  WebSocketChannel? _channel;
  bool _connected = false;

  OnDataCallback? onData;
  OnBinaryDataCallback? onBinaryData;

  WebSocketService(this.url);

  // ==============================
  // JSON mode (cũ)
  // ==============================
  void connect() {
    if (_connected) return;
    _channel = WebSocketChannel.connect(Uri.parse(url));
    _connected = true;

    _channel!.stream.listen((event) {
      try {
        final data = jsonDecode(event);
        final dets = (data['detections'] ?? []) as List;
        final fps = (data['fps'] ?? 0).toDouble();
        final latency = (data['latency_ms'] ?? 0).toInt();
        onData?.call(dets, fps, latency, data);
      } catch (_) {}
    }, onError: (_) {
      _connected = false;
    }, onDone: () {
      _connected = false;
    });
  }

  void sendJson(Map<String, dynamic> data) {
    if (!_connected) return;
    _channel?.sink.add(jsonEncode(data));
  }

  // ==============================
  // Binary mode (mới)
  // ==============================
  void connectBinary() {
    if (_connected) return;
    _channel = WebSocketChannel.connect(Uri.parse(url));
    _connected = true;

    _channel!.stream.listen((event) {
      // event có thể là text (JSON) hoặc binary (bytes)
      if (event is String) {
        try {
          final data = jsonDecode(event);
          final dets = (data['detections'] ?? []) as List;
          final fps = (data['fps'] ?? 0).toDouble();
          final latency = (data['latency_ms'] ?? 0).toInt();
          onBinaryData?.call(dets, fps, latency, data);
        } catch (_) {}
      }
    }, onError: (_) {
      _connected = false;
    }, onDone: () {
      _connected = false;
    });
  }

  /// Gửi ảnh binary: header JSON trước, rồi bytes ảnh
  void sendBinary(String headerJson, Uint8List bytes) {
    if (!_connected) return;
    _channel?.sink.add(headerJson);
    _channel?.sink.add(bytes);
  }

  // ==============================
  // Đóng kết nối
  // ==============================
  void close() {
    try {
      _channel?.sink.close(status.goingAway);
    } catch (_) {}
    _connected = false;
  }
}
