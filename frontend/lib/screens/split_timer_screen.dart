import 'package:flutter/material.dart';
import 'dart:html' as html;
import 'dart:ui' as ui;
import 'dart:convert';
import 'dart:async';
import '../api_service.dart';

class SplitTimerScreen extends StatefulWidget {
  final Function(int, {String? videoId, dynamic uploadFile})? onNavigate;

  const SplitTimerScreen({Key? key, this.onNavigate}) : super(key: key);

  @override
  _SplitTimerScreenState createState() => _SplitTimerScreenState();
}

class _SplitTimerScreenState extends State<SplitTimerScreen> with AutomaticKeepAliveClientMixin {
  @override
  bool get wantKeepAlive => true;

  final ApiService _apiService = ApiService();

  html.VideoElement? _videoElement;
  List<html.MediaDeviceInfo> _cameras = [];

  int _selectedCameraIndex = 0;
  bool _isInit = false;

  final String _viewType = "cameraVideo_split";

  html.WebSocket? _obsSocket;
  bool _obsConnected = false;
  bool _obsRecording = false;
  bool _vcamActive = false;

  // Browser-side recording
  html.MediaRecorder? _mediaRecorder;
  List<html.Blob> _recordedChunks = [];
  bool _isAutoUploading = false;
  String? _completionStatus;
  DateTime? _recordingStartTime;

  int _countdownValue = 0;
  bool _isCountingDown = false;
  Timer? _countdownTimer;

  @override
  void initState() {
    super.initState();
    _getAllCameras();
    _connectObs();
  }

  void _connectObs() {
    try {
      _obsSocket = html.WebSocket('ws://127.0.0.1:4455');
      _obsSocket!.onOpen.listen((e) {
        print('OBS WebSocket connection opened.');
      });

      _obsSocket!.onMessage.listen((e) {
        final data = jsonDecode(e.data);
        final op = data['op'];

        if (op == 0) { // Hello
          // Send Identify (no auth for now)
          _obsSocket!.sendString(jsonEncode({
            'op': 1,
            'd': {
              'rpcVersion': 1,
              'eventSubscriptions': (1 << 6) // Outputs (Recording, Virtual Cam, etc.)
            }
          }));
        } else if (op == 2) { // Identified
          setState(() {
            _obsConnected = true;
          });
          print('OBS WebSocket Identified successfully!');

          // Check Virtual Camera status
          _obsSocket!.sendString(jsonEncode({
            'op': 6,
            'd': {
              'requestType': 'GetVirtualCamStatus',
              'requestId': 'get_vcam'
            }
          }));

          // Check current Recording status
          _obsSocket!.sendString(jsonEncode({
            'op': 6,
            'd': {
              'requestType': 'GetRecordStatus',
              'requestId': 'get_record_status'
            }
          }));

        } else if (op == 7) { // RequestResponse
          final d = data['d'];
          final requestId = d['requestId'];
            if (requestId == 'get_vcam') {
              final responseData = d['responseData'] ?? {};
              setState(() {
                _vcamActive = responseData['virtualCamIsActive'] ?? false;
              });
            } else if (requestId == 'get_record_status') {
            final responseData = d['responseData'] ?? {};
            setState(() {
              _obsRecording = responseData['outputActive'] ?? false;
            });
          }
        } else if (op == 5) { // Event
          final d = data['d'];
          final eventType = d['eventType'];
          final eventData = d['eventData'] ?? {};

          if (eventType == 'RecordStateChanged') {
            final bool isActive = eventData['outputActive'] ?? false;
            setState(() {
              _obsRecording = isActive;
            });
            print('OBS Recording State Changed: $_obsRecording');

            if (!isActive) {
               // Stop browser recording if it was started from OBS
              if (_mediaRecorder != null && _mediaRecorder!.state == 'recording') {
                _mediaRecorder!.stop();
              }
            } else {
              // Started from OBS
              if (_mediaRecorder == null || _mediaRecorder!.state != 'recording') {
                _startBrowserRecording();
              }
            }
          } else if (eventType == 'VirtualCamStateChanged') {
            setState(() {
              _vcamActive = eventData['outputActive'] ?? false;
            });
            if (_vcamActive) {
              _getAllCameras(); // VCam 開啟時自動重新掃描相機列表
            }
          }
        }
      });

      _obsSocket!.onClose.listen((e) {
        setState(() {
          _obsConnected = false;
          _obsRecording = false;
        });
        print('OBS WebSocket closed. Retrying in 5s...');
        Future.delayed(const Duration(seconds: 5), () {
          if (mounted) _connectObs();
        });
      });

      _obsSocket!.onError.listen((e) {
        print('OBS WebSocket error.');
      });
    } catch (e) {
      print('OBS connect exception: $e');
    }
  }

  void _startCountdownAndRecord() {
    if (_isCountingDown || _obsRecording) return;
    
    setState(() {
      _isCountingDown = true;
      _countdownValue = 5;
    });

    _countdownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      setState(() {
        _countdownValue--;
      });
      if (_countdownValue <= 0) {
        timer.cancel();
        setState(() {
          _isCountingDown = false;
        });
        _startObsRecording();
      }
    });
  }

  void _cancelCountdown() {
    if (_countdownTimer != null && _countdownTimer!.isActive) {
      _countdownTimer!.cancel();
    }
    setState(() {
      _isCountingDown = false;
    });
  }

  void _startObsRecording() {
    if (_obsConnected && _obsSocket != null) {
      // 先發送 OBS 指令
      try {
        _obsSocket!.sendString(jsonEncode({
          'op': 6,
          'd': {
            'requestType': 'StartRecord',
            'requestId': 'start_record_req'
          }
        }));
      } catch (e) {
        print('Error sending OBS start request: $e');
      }
      
      // 同步更新 UI 狀態
      setState(() {
        _obsRecording = true;
      });

      // 嘗試啟動瀏覽器端錄影（不影響 OBS）
      _startBrowserRecording();
    }
  }

  void _startBrowserRecording() {
    if (_videoElement?.srcObject == null) return;
    
    try {
      _recordedChunks = [];
      final stream = _videoElement!.srcObject as html.MediaStream;
      
      // 優先嘗試常見格式，失敗則由瀏覽器決定
      String mimeType = 'video/webm;codecs=vp8,opus';
      if (!html.MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'video/webm';
      }
      
      _mediaRecorder = html.MediaRecorder(stream, {
        'mimeType': mimeType,
        'videoBitsPerSecond': 1200000, // 再降到 1.2 Mbps，減輕極大負擔
      });
      
      _mediaRecorder!.on['dataavailable'].listen((event) {
        final html.Blob? blob = (event as dynamic).data;
        if (blob != null && blob.size > 0) {
          _recordedChunks.add(blob);
        }
      });

      _mediaRecorder!.on['stop'].listen((event) {
        _uploadRecordedVideo();
      });

      _mediaRecorder!.start();
      _recordingStartTime = DateTime.now();
      print('Browser-side recording started with $mimeType');
    } catch (e) {
      print('Browser-side recording failed to start: $e');
      // 這裡不彈出視窗，以免干擾使用者，但會在後台紀錄
    }
  }

  void _stopObsRecording() {
    if (_obsConnected && _obsSocket != null) {
      _obsSocket!.sendString(jsonEncode({
        'op': 6,
        'd': {
          'requestType': 'StopRecord',
          'requestId': 'stop_record_req'
        }
      }));
      
      if (_mediaRecorder != null && _mediaRecorder!.state == 'recording') {
        _mediaRecorder!.stop();
      }

      setState(() {
        _obsRecording = false;
      });
    }
  }

  Future<void> _uploadRecordedVideo() async {
    // 檢查錄影時間，小於 1 秒視為啟動失敗或誤觸，不進行自動上傳與分析
    if (_recordingStartTime != null) {
      final duration = DateTime.now().difference(_recordingStartTime!);
      if (duration.inSeconds < 1) {
        print('Recording was too short, skipping auto-upload.');
        return;
      }
    }

    if (_recordedChunks.isEmpty) return;

    setState(() {
      _isAutoUploading = true;
      _completionStatus = '影片錄製完成！正在上傳至平台...';
    });

    final blob = html.Blob(_recordedChunks, 'video/webm');

    final uploadFuture = _apiService.uploadBlob(blob, skipAnalysis: true);
    final delayFuture = Future.delayed(const Duration(seconds: 3));

    try {
      await Future.wait([uploadFuture, delayFuture]);
    } catch (e) {
      print('Upload failed: $e');
      setState(() {
        _completionStatus = '上傳失敗: $e';
      });
      await Future.delayed(const Duration(seconds: 2));
    }

    if (mounted) {
      setState(() {
        _isAutoUploading = false;
        _completionStatus = null;
      });

      // 2. 直接跳轉到分析頁面(UploadScreen)
      if (widget.onNavigate != null) {
        widget.onNavigate!(2); 
      }
    }
  }

  String _getDynamicBaseUrl() {
    final origin = html.window.location.origin;
    if (origin.startsWith('https://')) {
      return 'https://catslab.ee.ncku.edu.tw/swimming_analysis/api'; 
    }
    if (origin.contains(':19191')) {
      return origin.replaceAll(':19191', ':18181');
    }
    return 'http://127.0.0.1:18181';
  }

  /// 取得所有 camera
  Future<void> _getAllCameras() async {
    try {
      // 先用一個 dummy try 去要權限，如果預設相機被鎖會失敗，但不影響 enumerateDevices 取標籤 (若先前已授權)
      try {
        final dummyStream = await html.window.navigator.mediaDevices!.getUserMedia({
          'video': true,
          'audio': false,
        });
        // 立即停止這個 dummy stream 來釋放系統硬體相機
        for (var track in dummyStream.getTracks()) {
          track.stop();
        }
      } catch (e) {
        print("Initial permission grab failed, could be in use: $e");
      }

      final devices =
          await html.window.navigator.mediaDevices?.enumerateDevices();
      _cameras = devices!.where((device) => device.kind == 'videoinput').cast<html.MediaDeviceInfo>().toList();

      if (_cameras.isNotEmpty) {
        // 特別偏好尋找 OBS Virtual Camera
        int obsIndex = _cameras.indexWhere((c) => (c.label ?? '').toLowerCase().contains('obs'));
        if (obsIndex != -1) {
          bool success = await _initCamera(obsIndex);
          if (success) return;
        }

        // 如果沒有 OBS，或是 OBS 初始化失敗，就一個個嘗試，不要盲目報錯
        bool anySuccess = false;
        for (int i = 0; i < _cameras.length; i++) {
          if (i == obsIndex) continue; // 前面試過了
          anySuccess = await _initCamera(i);
          if (anySuccess) break;
        }

        if (!anySuccess) {
          print("No cameras could be initialized.");
        }
      } else {
        print("No cameras found.");
      }
    } catch (e) {
      print("Camera enumerate error: $e");
    }
  }

  /// 初始化 camera
  Future<bool> _initCamera(int index) async {
    try {
      final camera = _cameras[index];

      final constraints = {
        'video': {
          'deviceId': camera.deviceId,
          'width': {'ideal': 1280},
          'height': {'ideal': 720},
        },
        'audio': false,
      };

      final stream = await html.window.navigator.mediaDevices!
          .getUserMedia(constraints);

      _videoElement = html.VideoElement()
        ..srcObject = stream
        ..autoplay = true
        ..muted = true
        ..style.width = '100%'
        ..style.height = '100%'
        ..style.objectFit = 'cover';

      // ignore: undefined_prefixed_name
      ui.platformViewRegistry.registerViewFactory(
        _viewType,
        (int viewId) => _videoElement!,
      );

      if (mounted) {
        setState(() {
          _selectedCameraIndex = index;
          _isInit = true;

        });
      }
      return true;
    } catch (e) {
      print("Camera init error: $e");
      return false;
    }
  }

  /// 切換 camera
  void _switchCamera() async {
    if (_cameras.length < 2) return;

    // 先停止現有相機鎖定
    _stopCamera();

    int newIndex = (_selectedCameraIndex + 1) % _cameras.length;

    setState(() {
      _isInit = false;
    });

    bool success = await _initCamera(newIndex);
    // 如果切換失敗，可以嘗試下一個，為簡單起見這裡直接印出錯誤
    if (!success) {
       print("Failed to switch to camera $newIndex");
       // fallback to screen share
       setState(() {
          print("Camera init failed.");
       });
    }
  }


  /// 停止 camera stream
  void _stopCamera() {
    final stream = _videoElement?.srcObject as html.MediaStream?;

    if (stream != null) {
      for (var track in stream.getTracks()) {
        track.stop();
      }
    }
  }

  @override
  void dispose() {
    _cancelCountdown();
    _stopCamera();
    _obsSocket?.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    super.build(context); // Required for AutomaticKeepAliveClientMixin
    if (_cameras.isEmpty) {
      return const Center(
        child: Text('No cameras found. Please check permissions.'),
      );
    }

    return Scaffold(
      body: Stack(
        children: [
          /// Camera / ScreenShare 畫面
          if (_isInit && !_isAutoUploading && !_isCountingDown)
            Center(
              child: HtmlElementView(viewType: _viewType),
            )
          else if (!_isAutoUploading && !_isCountingDown)
            const Center(child: CircularProgressIndicator()),

          /// 錄製完成提示 Overlay
          if (_isAutoUploading)
            Container(
              color: Colors.black54,
              child: Center(
                child: Card(
                  elevation: 8,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 30),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const CircularProgressIndicator(),
                        const SizedBox(height: 24),
                        Text(
                          _completionStatus ?? '處理中...',
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),

          /// 倒數計時 Overlay
          if (_isCountingDown)
            Container(
              color: Colors.black45,
              child: Center(
                child: Text(
                  '$_countdownValue',
                  style: const TextStyle(
                    fontSize: 250,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                    shadows: [
                      Shadow(color: Colors.black, blurRadius: 15)
                    ],
                  ),
                ),
              ),
            ),

          /// OBS Recording Controls
          Positioned(
            bottom: 20,
            left: 0,
            right: 0,
            child: Center(
              child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: Colors.black54,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    (_cameras.isNotEmpty && (_cameras[_selectedCameraIndex].label ?? '').toLowerCase().contains('obs')) 
                      ? 'OBS Ready' 
                      : 'OBS Disconnected', 
                    style: TextStyle(
                      color: (_cameras.isNotEmpty && (_cameras[_selectedCameraIndex].label ?? '').toLowerCase().contains('obs')) ? Colors.white : Colors.redAccent, 
                      fontWeight: FontWeight.bold
                    )
                  ),
                  if (_cameras.isNotEmpty && (_cameras[_selectedCameraIndex].label ?? '').toLowerCase().contains('obs')) ...[
                    const SizedBox(width: 16),
                    if (!_obsRecording)
                      if (_isCountingDown)
                        ElevatedButton.icon(
                          onPressed: _cancelCountdown,
                          icon: const Icon(Icons.cancel, color: Colors.white, size: 18),
                          label: Text('Cancel ($_countdownValue)'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.orange[700],
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                          ),
                        )
                      else
                        ElevatedButton.icon(
                          onPressed: _startCountdownAndRecord,
                          icon: const Icon(Icons.radio_button_checked, color: Colors.white, size: 18),
                          label: const Text('Start Recording'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.green[600],
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                          ),
                        )
                    else
                      ElevatedButton.icon(
                        onPressed: _stopObsRecording,
                        icon: const Icon(Icons.stop, color: Colors.white, size: 18),
                        label: const Text('Stop Recording'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.red[700],
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                        ),
                      ),
                  ],
                ],
              ),
            ),
          ),
        ),

          /// Camera 切換 & 重新整理
          if (_cameras.length > 1)
            Positioned(
              bottom: 10,
              right: 20,
              child: Row(
                children: [
                  FloatingActionButton(
                    heroTag: 'refreshCamSplit',
                    onPressed: () {
                      _getAllCameras();
                      if (_obsConnected) {
                         _obsSocket!.sendString(jsonEncode({
                          'op': 6,
                          'd': {
                            'requestType': 'GetVirtualCamStatus',
                            'requestId': 'get_vcam'
                          }
                        }));
                      }
                    },
                    child: const Icon(Icons.refresh),
                    backgroundColor: Colors.white,
                    foregroundColor: Colors.black,
                    mini: true,
                  ),
                  const SizedBox(width: 8),
                  FloatingActionButton(
                    heroTag: 'cameraSwitcherSplit',
                    onPressed: _switchCamera,
                    child: const Icon(Icons.cameraswitch),
                    backgroundColor: Colors.white,
                    foregroundColor: Colors.black,
                    mini: true,
                  ),
                ],
              ),
            ),

        ],
      ),
    );
  }
}
