class ApiConfig {
  // Cloudflare Tunnel domain
  static const String baseUrl = "https://detect.ltk.id.vn";

  // HTTP base (FastAPI REST)
  static String get httpBase => baseUrl;

  // WebSocket endpoint
  static String get wsDetect => "wss://detect.ltk.id.vn/ws/detect";
}
