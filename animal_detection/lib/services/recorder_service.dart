import 'dart:typed_data';
import 'dart:io';
import 'package:path_provider/path_provider.dart';

class RecorderService {
  Future<String> saveJpeg(Uint8List jpg) async {
    final dir = await getApplicationDocumentsDirectory();
    final path = "${dir.path}/snap_${DateTime.now().millisecondsSinceEpoch}.jpg";
    final f = File(path);
    await f.writeAsBytes(jpg);
    return path;
  }
}
