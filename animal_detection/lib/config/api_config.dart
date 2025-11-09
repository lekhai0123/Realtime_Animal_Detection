class ApiConfig {
  static const String baseIp = "192.168.1.133"; // IP máy backend
  static const int port = 8000;

  static String get httpBase => "http://$baseIp:$port";
  static String get wsBase => "ws://$baseIp:$port";
}
