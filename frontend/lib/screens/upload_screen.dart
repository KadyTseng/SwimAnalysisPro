import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'analysis_progress_screen.dart';
import '../api_service.dart';
import '../models.dart';
import 'result_screen.dart';

class UploadScreen extends StatefulWidget {
  @override
  _UploadScreenState createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  PlatformFile? _selectedFile;
  final ApiService _apiService = ApiService();
  List<VideoInfoSummary> _completedVideos = [];
  bool _isLoadingHistory = false;

  @override
  void initState() {
    super.initState();
    _fetchHistory();
  }

  Future<void> _fetchHistory() async {
    setState(() {
      _isLoadingHistory = true;
    });
    try {
      final listResp = await _apiService.listAllAnalyses();
      setState(() {
        // Only display fully completed analyses
        _completedVideos = listResp.videos.where((v) => v.status == 'completed').toList();
      });
    } catch (e) {
      print('Failed to fetch video list history: $e');
    } finally {
      setState(() {
        _isLoadingHistory = false;
      });
    }
  }

  Future<void> _openResult(String videoId) async {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => Center(child: CircularProgressIndicator(color: Colors.blueAccent)),
    );
    try {
      final result = await _apiService.getResult(videoId);
      Navigator.of(context).pop(); // Dismiss loading dialog
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (context) => ResultScreen(result: result),
        ),
      );
    } catch (e) {
      Navigator.of(context).pop(); // Dismiss loading
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('讀取分析結果失敗: $e')),
      );
    }
  }

  Future<void> _pickFile() async {
    FilePickerResult? result = await FilePicker.platform.pickFiles(
      type: FileType.video,
      allowMultiple: false,
      withData: true,
    );

    if (result != null) {
      setState(() {
        _selectedFile = result.files.single;
      });
    }
  }

  void _onAnalyzePressed() {
    if (_selectedFile == null) return;

    // 【重要修復】先用區域變數抓取檔案，避免被下方的 setState 歸零
    final fileToUpload = _selectedFile;

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => AnalysisProgressScreen(uploadFile: fileToUpload),
      ),
    );

    // 重置選取狀態
    setState(() {
      _selectedFile = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Colors.blue.shade50, Colors.white],
          ),
        ),
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: SingleChildScrollView(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.analytics_outlined, size: 80, color: Colors.blueAccent),
                  const SizedBox(height: 24),
                  Text(
                    'Analysis & Playback',
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                      color: Colors.blue[900],
                    ),
                  ),
                  const SizedBox(height: 40),
                  if (_selectedFile != null) ...[
                    Card(
                      elevation: 4,
                      child: Padding(
                        padding: const EdgeInsets.all(16.0),
                        child: Row(
                          children: [
                            Icon(Icons.video_file, color: Colors.blue),
                            const SizedBox(width: 16),
                            Expanded(
                              child: Text(
                                _selectedFile!.name,
                                style: const TextStyle(fontSize: 16),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                            IconButton(
                              icon: const Icon(Icons.close),
                              onPressed: () => setState(() => _selectedFile = null),
                            )
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                  ],
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      ElevatedButton.icon(
                        onPressed: _pickFile,
                        icon: const Icon(Icons.folder_open),
                        label: Text(_selectedFile == null ? 'Select Video' : 'Change Video'),
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                        ),
                      ),
                      const SizedBox(width: 16),
                      ElevatedButton.icon(
                        onPressed: _selectedFile != null ? _onAnalyzePressed : null,
                        icon: const Icon(Icons.play_circle_filled),
                        label: const Text('Start Analysis'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.blueAccent,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 48),
                  Container(
                    width: 600,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              '歷史分析結果列表 (Completed Analyses)',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: Colors.blueGrey[800],
                              ),
                            ),
                            IconButton(
                              icon: Icon(Icons.refresh, color: Colors.blueAccent),
                              onPressed: _fetchHistory,
                              tooltip: 'Refresh List',
                            )
                          ],
                        ),
                        const SizedBox(height: 12),
                        _isLoadingHistory
                            ? Center(child: Padding(
                                padding: const EdgeInsets.all(16.0),
                                child: CircularProgressIndicator(color: Colors.blueAccent),
                              ))
                            : _completedVideos.isEmpty
                                ? Center(
                                    child: Padding(
                                      padding: const EdgeInsets.all(16.0),
                                      child: Text(
                                        '目前沒有已完成的分析紀錄',
                                        style: TextStyle(color: Colors.grey[600]),
                                      ),
                                    ),
                                  )
                                : Container(
                                    constraints: BoxConstraints(maxHeight: 280),
                                    child: ListView.builder(
                                      shrinkWrap: true,
                                      itemCount: _completedVideos.length,
                                      itemBuilder: (context, index) {
                                        final v = _completedVideos[index];
                                        return Card(
                                          margin: const EdgeInsets.symmetric(vertical: 6.0),
                                          elevation: 2,
                                          child: ListTile(
                                            leading: CircleAvatar(
                                              backgroundColor: Colors.blue[50],
                                              child: Icon(Icons.check_circle, color: Colors.blueAccent),
                                            ),
                                            title: Text(v.filename, style: TextStyle(fontWeight: FontWeight.bold, color: Colors.blueGrey[900])),
                                            subtitle: Text('ID: ${v.videoId}'),
                                            trailing: Icon(Icons.arrow_forward_ios, size: 16, color: Colors.blueAccent),
                                            onTap: () => _openResult(v.videoId),
                                          ),
                                        );
                                      },
                                    ),
                                  ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
