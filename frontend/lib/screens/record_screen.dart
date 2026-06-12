// import 'package:flutter/material.dart';
// import 'package:camera/camera.dart';
// import 'screen_share.dart';

// class RecordScreen extends StatefulWidget {
//   final List<CameraDescription> cameras;

//   const RecordScreen({Key? key, required this.cameras}) : super(key: key);

//   @override
//   _RecordScreenState createState() => _RecordScreenState();
// }

// class _RecordScreenState extends State<RecordScreen> {
//   CameraController? _controller;
//   int _selectedCameraIndex = 0;
//   bool _isInit = false;
//   bool _useScreenShare = false;

//   @override
//   void initState() {
//     super.initState();
//     if (widget.cameras.isNotEmpty) {
//       _initCamera(_selectedCameraIndex);
//     }
//   }

//   Future<void> _initCamera(int index) async {
//     final camera = widget.cameras[index];
//     _controller = CameraController(
//       camera,
//       ResolutionPreset.high,
//       enableAudio: false,
//     );

//     try {
//       await _controller!.initialize();
//       if (mounted) {
//         setState(() {
//           _isInit = true;
//           _useScreenShare = false; // Successfully initialized camera
//         });
//       }
//     } catch (e) {
//       print("Camera init error: $e");
//       if (mounted) {
//         setState(() {
//           _useScreenShare = true; // Fallback to screen share
//           _isInit = false;
//         });
//       }
//     }
//   }

//   @override
//   void dispose() {
//     _controller?.dispose();
//     super.dispose();
//   }

//   void _switchCamera() {
//     if (widget.cameras.length < 2) return;
//     setState(() {
//       _isInit = false;
//       _selectedCameraIndex = (_selectedCameraIndex + 1) % widget.cameras.length;
//     });
//     _initCamera(_selectedCameraIndex);
//   }

//   @override
//   Widget build(BuildContext context) {
//     if (widget.cameras.isEmpty && !_useScreenShare) {
//       return Center(
//         child: Column(
//           mainAxisSize: MainAxisSize.min,
//           children: [
//             Text('No cameras found. Please check your device settings.'),
//             SizedBox(height: 16),
//             ElevatedButton(
//               onPressed: () {
//                 setState(() {
//                   _useScreenShare = true;
//                 });
//               },
//               child: Text("Try Screen Sharing"),
//             )
//           ],
//         )
//       );
//     }

//     return Scaffold(
//       body: Stack(
//         children: [
//           // Content Area
//           if (_useScreenShare)
//             ScreenShareView(
//               onStop: () {
//                 setState(() {
//                   _useScreenShare = false;
//                 });
//               },
//             )
//           else if (_isInit && _controller != null && _controller!.value.isInitialized)
//             Center(child: CameraPreview(_controller!))
//           else
//             Center(child: CircularProgressIndicator()),

//           // Overlays
//           Positioned(
//             top: 20,
//             left: 20,
//             child: Container(
//               padding: EdgeInsets.symmetric(horizontal: 12, vertical: 6),
//               decoration: BoxDecoration(
//                 color: Colors.black54,
//                 borderRadius: BorderRadius.circular(20),
//               ),
//               child: Row(
//                 children: [
//                   Icon(Icons.circle, color: Colors.red, size: 12),
//                   SizedBox(width: 8),
//                   Text(
//                     'Live Monitor', 
//                     style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)
//                   ),
//                 ],
//               ),
//             ),
//           ),

//           // Mode Switcher (Screen Share vs Camera)
//           Positioned(
//             bottom: 30,
//             right: widget.cameras.length > 1 ? 100 : 30, // Offset if camera switcher exists
//             child: FloatingActionButton(
//               heroTag: 'modeSwitcher',
//               onPressed: () {
//                 if (_useScreenShare) {
//                   setState(() => _useScreenShare = false);
//                   if (!_isInit) _initCamera(_selectedCameraIndex);
//                 } else {
//                   setState(() {
//                     _useScreenShare = true;
//                   });
//                 }
//               },
//               backgroundColor: _useScreenShare ? Colors.red : Colors.blue,
//               foregroundColor: Colors.white,
//               tooltip: _useScreenShare ? 'Stop Screen Share' : 'Start Screen Share',
//               child: Icon(_useScreenShare ? Icons.stop_screen_share : Icons.screen_share),
//             ),
//           ),
            
//           // Camera Switcher
//           if (widget.cameras.length > 1 && !_useScreenShare)
//             Positioned(
//               bottom: 30,
//               right: 30,
//               child: FloatingActionButton(
//                 heroTag: 'cameraSwitcher',
//                 onPressed: _switchCamera,
//                 child: Icon(Icons.cameraswitch),
//                 backgroundColor: Colors.white,
//                 foregroundColor: Colors.black,
//               ),
//             ),
            
//           Positioned(
//             bottom: 30,
//             left: 0,
//             right: 0,
//             child: Center(
//               child: Text(
//                 'Monitoring Stream (OBS Virtual Camera)',
//                 style: TextStyle(
//                   color: Colors.white,
//                   shadows: [Shadow(color: Colors.black, blurRadius: 4)],
//                   fontSize: 16
//                 ),
//               ),
//             ),
//           )
//         ],
//       ),
//     );
//   }
// }






import 'package:flutter/material.dart';
// import 'screen_share.dart';
import 'dart:html' as html;
import 'dart:ui' as ui;
import 'dart:convert';

class RecordScreen extends StatefulWidget {
  final Function(int, {String? videoId, dynamic uploadFile})? onNavigate;
  final bool isActive;

  const RecordScreen({Key? key, this.onNavigate, this.isActive = true}) : super(key: key);


  @override
  _RecordScreenState createState() => _RecordScreenState();
}

class _RecordScreenState extends State<RecordScreen> with AutomaticKeepAliveClientMixin {
  @override
  bool get wantKeepAlive => true;

  html.VideoElement? _videoElement;
  List<html.MediaDeviceInfo> _cameras = [];

  int _selectedCameraIndex = 0;
  bool _isInit = false;


  final String _viewType = "cameraVideo";

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
            final bool isRecording = responseData['outputActive'] ?? false;
            if (isRecording) {
              _obsSocket!.sendString(jsonEncode({
                'op': 6,
                'd': {
                  'requestType': 'StopRecord',
                  'requestId': 'stop_record_on_init'
                }
              }));
              print("OBS was recording on init/refresh. Stopped it to reset to idle state.");
            }
            setState(() {
              _obsRecording = false;
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

            if (!widget.isActive) {
              print('RecordScreen (Background): Sync _obsRecording state only.');
              return;
            }

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

    // 1. 先顯示錄製完成的狀態 (Rule 4: 停留 3 秒)
    setState(() {
      _isAutoUploading = true;
      _completionStatus = '影片錄製完成！正在上傳至平台...';
    });

    final blob = html.Blob(_recordedChunks, 'video/webm');

    // 確保顯示 3 秒
    await Future.delayed(const Duration(seconds: 3));

    if (mounted) {
      setState(() {
        _isAutoUploading = false;
        _completionStatus = null;
      });

      // 2. 直接跳轉到進度頁面，並傳入 Blob
      // 注意：這裡我們需要確保 AnalysisProgressScreen 能處理 Blob
      if (widget.onNavigate != null) {
        widget.onNavigate!(2, uploadFile: blob); // 修改參數傳遞
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
          'width': {'ideal': 3840},
          'height': {'ideal': 1080},
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
        ..style.objectFit = 'fill';

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
      backgroundColor: Colors.white, // Pure white background to match split timer screen
      body: Stack(
        children: [
          /// Camera / ScreenShare 畫面
          if (_isInit && !_isAutoUploading)
            Center(
              child: AspectRatio(
                aspectRatio: 3840.0 / 1080.0,
                child: HtmlElementView(viewType: _viewType),
              ),
            )
          else if (!_isAutoUploading)
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
                    _obsConnected 
                      ? 'OBS Ready' 
                      : 'OBS Disconnected', 
                    style: TextStyle(
                      color: _obsConnected ? Colors.white : Colors.redAccent, 
                      fontWeight: FontWeight.bold
                    )
                  ),
                  if (_obsConnected) ...[
                    const SizedBox(width: 16),
                    if (!_obsRecording)
                      ElevatedButton.icon(
                        onPressed: _startObsRecording,
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
                    heroTag: 'refreshCam',
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
                    heroTag: 'cameraSwitcher',
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