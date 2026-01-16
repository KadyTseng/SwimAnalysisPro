import 'dart:convert';
import 'package:http/http.dart' as http;
import 'models.dart';
import 'package:file_picker/file_picker.dart';

class ApiService {
  final String baseUrl;

  ApiService({this.baseUrl = 'http://127.0.0.1:9000'}); // Update with your actual IP if running on device

  /// Uploads a video file to the backend
  Future<AnalysisUploadResponse> uploadVideo(PlatformFile file) async {
    var uri = Uri.parse('$baseUrl/analysis/upload');
    var request = http.MultipartRequest('POST', uri);
    
    if (file.bytes != null) {
      // Web: use bytes
      request.files.add(
        http.MultipartFile.fromBytes(
          'file',
          file.bytes!,
          filename: file.name,
        ),
      );
    } else if (file.path != null) {
      // Mobile/Desktop: use path
      request.files.add(
        await http.MultipartFile.fromPath(
          'file',
          file.path!,
          filename: file.name,
        ),
      );
    } else {
      throw Exception('File path and bytes are both null');
    }

    var streamedResponse = await request.send();
    var response = await http.Response.fromStream(streamedResponse);

    if (response.statusCode == 202) {
      return AnalysisUploadResponse.fromJson(jsonDecode(response.body));
    } else {
      throw Exception('Failed to upload video: ${response.statusCode} ${response.body}');
    }
  }

  /// Checks the status of the analysis
  Future<AnalysisStatusResponse> checkStatus(String videoId) async {
    var uri = Uri.parse('$baseUrl/analysis/$videoId/status');
    var response = await http.get(uri);

    print("[Frontend API] Checking Status... Code: ${response.statusCode}");
    if (response.statusCode == 200) {
      var body = jsonDecode(response.body);
      var currentStep = body['current_step'] ?? '';
      print("[Frontend API] Status/Progress: ${body['status']} (${body['progress']}%) $currentStep");
      
      if (body['status'] == 'failed') {
          // Fix: Backend sends 'error_message', not 'error'
          var errorMsg = body['error_message'] ?? body['error'] ?? 'Unknown Error';
          print("[Frontend API] ❌ ANALYSIS FAILED: $errorMsg");
      }
      return AnalysisStatusResponse.fromJson(body);
    } else {
      print("[Frontend API] Check Status Failed: ${response.body}");
      throw Exception('Failed to check status');
    }
  }

  /// Retrieves the final analysis result
  Future<FullAnalysisResult> getResult(String videoId) async {
    var uri = Uri.parse('$baseUrl/analysis/$videoId/result');
    var response = await http.get(uri);

    print("[Frontend API] Fetching Result... Code: ${response.statusCode}");

    if (response.statusCode == 200) {
      // Decode with UTF-8 to handle any special chars if needed, though usually jsonDecode handles it
      var json = jsonDecode(utf8.decode(response.bodyBytes));
      print("[Frontend API] Result Received. Keys: ${json.keys.toList()}");
      return FullAnalysisResult.fromJson(json);
    } else {
      print("[Frontend API] Get Result Failed: ${response.body}");
      throw Exception('Failed to get results: ${response.statusCode}');
    }
  }

  /// Helper to get the download URL
  String getDownloadUrl(String videoId) {
    return '$baseUrl/analysis/$videoId/download';
  }

  /// Helper to get the full video URL for streaming/playback
  String getVideoUrl(String relativePath) {
    // Assuming backend serves files or we use the download endpoint
    // If relativePath is "data/processed_videos/..." we might need a static file serving endpoint
    // Or simpler: just use the download endpoint for the processed video
    return '$baseUrl/$relativePath'; 
  }
}
