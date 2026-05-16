import 'dart:async';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:html' as html;
import '../api_service.dart';
import 'result_screen.dart';

class AnalysisProgressScreen extends StatefulWidget {
  final String? videoId;
  final dynamic uploadFile;

  const AnalysisProgressScreen({
    Key? key, 
    this.videoId, 
    this.uploadFile
  }) : super(key: key);

  @override
  _AnalysisProgressScreenState createState() => _AnalysisProgressScreenState();
}

class _AnalysisProgressScreenState extends State<AnalysisProgressScreen> with TickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  Timer? _timer;
  
  String? _activeVideoId;
  double _displayProgress = 0.0;    
  String _statusMessage = '0%';
  String _currentStep = 'INITIALIZING...';
  bool _hasError = false;

  late AnimationController _frameController; 
  late AnimationController _smoothProgressController; 
  final int _frameCount = 16;

  @override
  void initState() {
    super.initState();
    _activeVideoId = widget.videoId;
    _initAnimations();
    
    // 【核心邏輯】一旦進入此頁面，立刻啟動分析流程
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _startAnalysisFlow();
    });
  }

  void _initAnimations() {
    _frameController = AnimationController(vsync: this, duration: const Duration(milliseconds: 800))..repeat();
    _smoothProgressController = AnimationController(vsync: this, duration: const Duration(milliseconds: 500));
    _smoothProgressController.addListener(() {
      setState(() {
        _displayProgress = _smoothProgressController.value;
        _statusMessage = '${(_displayProgress * 100).toInt()}%';
      });
    });
  }

  void _startAnalysisFlow() {
    if (_activeVideoId != null) {
      _startPolling();
    } else if (widget.uploadFile != null) {
      _uploadAndAnalyze();
    }
  }

  Future<void> _uploadAndAnalyze() async {
    setState(() { _currentStep = 'PREPARING FOR UPLOAD...'; });
    // 先讓進度條從 0 緩慢跑到 5%，營造從 0 開始的視覺感
    _smoothProgressController.animateTo(0.05, duration: const Duration(seconds: 2));

    try {
      String? videoId;
      if (widget.uploadFile is PlatformFile) {
        final res = await _apiService.uploadVideo(widget.uploadFile as PlatformFile);
        videoId = res.videoId;
      } else if (widget.uploadFile is html.Blob) {
        videoId = await _apiService.uploadBlob(widget.uploadFile as html.Blob);
      }

      if (videoId != null) {
        _activeVideoId = videoId;
        _startPolling();
      }
    } catch (e) {
      setState(() {
        _hasError = true;
        _currentStep = 'ERROR: $e';
      });
    }
  }

  void _startPolling() {
    _timer?.cancel();
    _checkStatus();
    _timer = Timer.periodic(const Duration(seconds: 2), (timer) => _checkStatus());
  }

  Future<void> _checkStatus() async {
    if (_activeVideoId == null) return;
    try {
      final status = await _apiService.checkStatus(_activeVideoId!);
      print('[F12 ANALYSIS] ID: ${_activeVideoId!.substring(0, 5)} | Progress: ${status.progress}% | Step: ${status.currentStep}');
      
      if (!mounted) return;
      
      double backendProgress = (status.progress ?? 0) / 100.0;
      double currentUiProgress = _smoothProgressController.value;
      
      // 最多只能比後端實際進度「偷跑」 15%，避免第一步還沒跑完就跑到 99%
      double maxAllowedFakeProgress = backendProgress + 0.15;

      // 如果後端傳來了新的進度，我們花 1.5 秒快速且平滑地跟上
      if (backendProgress > currentUiProgress) {
        _smoothProgressController.animateTo(
          backendProgress,
          duration: const Duration(milliseconds: 1500),
          curve: Curves.linear,
        );
      } else if (status.status == 'processing' && currentUiProgress < maxAllowedFakeProgress && currentUiProgress < 0.95) {
        // 如果後端卡在某個進度，且 UI 還沒超過偷跑上限
        _smoothProgressController.animateTo(
          currentUiProgress + 0.03, // 每次小步推進 3%
          duration: const Duration(seconds: 4),
          curve: Curves.linear,
        );
      }
      
      setState(() { _currentStep = status.currentStep ?? 'ANALYZING...'; });

      if (status.status == 'completed') {
        _timer?.cancel();
        _fetchResultAndNavigate();
      } else if (status.status == 'failed') {
        _timer?.cancel();
        setState(() { _hasError = true; _currentStep = status.errorMessage ?? 'FAILED'; });
      }
    } catch (e) {
      print('[F12] Polling Error: $e');
    }
  }

  Future<void> _fetchResultAndNavigate() async {
    try {
      final result = await _apiService.getResult(_activeVideoId!);
      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (context) => ResultScreen(result: result)),
        );
      }
    } catch (e) {
      setState(() { _hasError = true; _currentStep = 'RESULT FETCH FAILED: $e'; });
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _frameController.dispose();
    _smoothProgressController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.blue.shade50,
      appBar: AppBar(backgroundColor: Colors.transparent, elevation: 0),
      body: Container(
        width: double.infinity,
        decoration: BoxDecoration(gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Colors.blue.shade100, Colors.white])),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Stack(
              alignment: Alignment.center,
              children: [
                SizedBox(width: 360, height: 360, child: CircularProgressIndicator(value: _displayProgress, strokeWidth: 10, backgroundColor: Colors.blue.shade200.withOpacity(0.3), valueColor: AlwaysStoppedAnimation<Color>(_hasError ? Colors.red : Colors.blue.shade700))),
                AnimatedBuilder(
                  animation: _frameController,
                  builder: (context, child) {
                    int frameIndex = (_frameController.value * _frameCount).floor();
                    if (frameIndex >= _frameCount) frameIndex = _frameCount - 1;
                    return Image.asset('assets/swimming/${frameIndex + 1}.png', width: 280, height: 280, fit: BoxFit.contain);
                  },
                ),
                Positioned(bottom: 40, child: Text(_statusMessage, style: TextStyle(color: _hasError ? Colors.red : Colors.blue.shade900, fontSize: 38, fontWeight: FontWeight.bold))),
              ],
            ),
            const SizedBox(height: 60),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40),
              child: Text(_currentStep.toUpperCase(), textAlign: TextAlign.center, style: TextStyle(color: _hasError ? Colors.red : Colors.blue.shade800, letterSpacing: 2.0, fontWeight: FontWeight.bold, fontSize: 16)),
            ),
            if (_hasError) ...[
              const SizedBox(height: 32),
              ElevatedButton(onPressed: () => Navigator.of(context).pop(), child: const Text('BACK')),
            ]
          ],
        ),
      ),
    );
  }
}
