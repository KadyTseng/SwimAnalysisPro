import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'analysis_progress_screen.dart';

class UploadScreen extends StatefulWidget {
  @override
  _UploadScreenState createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  PlatformFile? _selectedFile;

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
              ],
            ),
          ),
        ),
      ),
    );
  }
}
